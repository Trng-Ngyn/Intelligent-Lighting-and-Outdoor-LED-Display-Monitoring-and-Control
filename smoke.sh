#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

compose=(docker compose --env-file compose.env -f docker-compose.lab.yml)
api=https://edge-api.dev.pccom.test:8443/v1/edge/health
pki=generated/test-clients
request=(curl --noproxy '*' --silent --show-error --max-time 5
  --cacert "$pki/server-ca.crt"
  --resolve edge-api.dev.pccom.test:8443:127.0.0.1)

retry_health() {
  local attempt
  for attempt in {1..25}; do
    if "${request[@]}" --fail --cert "$pki/gw-001.crt" --key "$pki/gw-001.key" \
        "$api" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  "${compose[@]}" logs edge-api mqtt >&2
  return 1
}

api_code() {
  "${request[@]}" -o /dev/null -w '%{http_code}' "$@" "$api" 2>/dev/null || true
}

mqtt_pub() {
  local certificate=$1 port=$2 topic=$3
  shift 3
  "${compose[@]}" run --rm --no-deps -T mqtt-tools timeout 12 mosquitto_pub -V mqttv5 \
    -h mqtt.dev.pccom.test -p "$port" --cafile /clients/server-ca.crt \
    --cert "/clients/$certificate.crt" --key "/clients/$certificate.key" \
    -t "$topic" -q 1 -m '{"message_id":"lab-smoke-001"}' -d "$@"
}

status="$(retry_health)"
[[ "$status" == '{"status":"ok","device_id":"gw-001"}' ]]
status="$(api_code --cert "$pki/unknown.crt" --key "$pki/unknown.key")"
[[ "$status" == 403 ]]
for status in \
  "$(api_code)" \
  "$(api_code --cert "$pki/dispatcher.crt" --key "$pki/dispatcher.key")" \
  "$(api_code --cert "$pki/revoked.crt" --key "$pki/revoked.key")"; do
  case "$status" in
    000|400|403) ;;
    *) printf 'Unexpected API status: %s\n' "$status" >&2; exit 1 ;;
  esac
done
wrong_host="$("${request[@]}" --resolve wrong.dev.pccom.test:8443:127.0.0.1 \
  --cert "$pki/gw-001.crt" --key "$pki/gw-001.key" \
  -o /dev/null -w '%{http_code}' 'https://wrong.dev.pccom.test:8443/v1/edge/health' \
  2>/dev/null || true)"
[[ "$wrong_host" == 000 ]]
printf '%s\n' 'API: authorized cert; unknown serial, missing/revoked cert, wrong CA and hostname checked.'

own_topic=pccom/v1/t1/s01/gw-001/telemetry
other_topic=pccom/v1/t1/s02/gw-002/telemetry
cmd_topic=pccom/v1/t1/s01/gw-001/cmd
own_result="$(mqtt_pub gw-001 8883 "$own_topic" 2>&1)"
printf '%s\n' "$own_result" | grep -Ei 'PUBACK.*RC:[[:space:]]*(0|16)([^0-9]|$)'
for forbidden_topic in "$other_topic" "$cmd_topic"; do
  denied="$(mqtt_pub gw-001 8883 "$forbidden_topic" 2>&1 || true)"
  printf '%s\n' "$denied" | grep -Ei 'PUBACK.*RC:[[:space:]]*135([^0-9]|$)|Warning: Publish .*not authorized'
done
dispatch_result="$(mqtt_pub dispatcher 8884 "$cmd_topic" -D PUBLISH message-expiry-interval 30 2>&1)"
printf '%s\n' "$dispatch_result" | grep -Ei 'PUBACK.*RC:[[:space:]]*(0|16)([^0-9]|$)'
for bad_identity in revoked dispatcher; do
  if mqtt_pub "$bad_identity" 8883 "$own_topic" > /dev/null 2>&1; then
    printf 'Broker accepted forbidden certificate (%s)\n' "$bad_identity" >&2
    exit 1
  fi
done
bridge_cmd=commands/v1/SITE_01/light/LGT_NODE_001/dim
bridge_status=pccom/v1/t1/s01/gw-001/status
for bridge_topic in "$bridge_cmd" "$bridge_status"; do
  bridge_result="$(mqtt_pub bridge-s01 8883 "$bridge_topic" 2>&1)"
  printf '%s\n' "$bridge_result" | grep -Ei 'PUBACK.*RC:[[:space:]]*(0|16)([^0-9]|$)'
done
for forbidden_topic in \
  telemetry/v1/SITE_01/light/LGT_NODE_001 \
  pccom/v1/t1/s02/gw-002/telemetry; do
  denied="$(mqtt_pub bridge-s01 8883 "$forbidden_topic" 2>&1 || true)"
  printf '%s\n' "$denied" | grep -Ei 'PUBACK.*RC:[[:space:]]*135([^0-9]|$)|Warning: Publish .*not authorized'
done
printf '%s\n' 'MQTT 5: valid publish, command service, bridge ACL, cross-site denial and rejected CA/CRL checked.'

# Field listener 8885: thiết bị southbound có cert riêng, chỉ viết topic của nó.
field_device=dev_SITE_01_LGT_NODE_001
field_bridge=field-bridge-s01
field_telemetry=telemetry/v1/SITE_01/light/LGT_NODE_001
field_status=status/v1/SITE_01/light/LGT_NODE_001
field_cmd=commands/v1/SITE_01/light/LGT_NODE_001/dim
for spec in "$field_device:$field_telemetry:" "$field_device:$field_status:-r" \
  "$field_bridge:$field_cmd:"; do
  IFS=: read -r certificate topic extra <<< "$spec"
  # shellcheck disable=SC2086
  field_result="$(mqtt_pub "$certificate" 8885 "$topic" $extra 2>&1)"
  printf '%s\n' "$field_result" | grep -Ei 'PUBACK.*RC:[[:space:]]*(0|16)([^0-9]|$)'
done
for forbidden_topic in \
  telemetry/v1/SITE_02/light/LGT_NODE_001 \
  commands/v1/SITE_01/light/LGT_NODE_001/dim; do
  denied="$(mqtt_pub "$field_device" 8885 "$forbidden_topic" 2>&1 || true)"
  printf '%s\n' "$denied" | grep -Ei 'PUBACK.*RC:[[:space:]]*135([^0-9]|$)|Warning: Publish .*not authorized'
done
printf '%s\n' 'Field 8885: per-device cert, retained status, cross-site denial and command write checked.'

# Topic alignment + LWT delay/retain được kiểm tra bằng paho trong alignment-tests.
"${compose[@]}" run --rm --no-deps --build -T alignment-tests
