"""Collector soak S7: đọc telemetry MQTT 5 trong 4h và kiểm chứng từng bản tin.

Khác với log monitor của bo, collector này kiểm tra.decode payload, jsonschema,
chữ ký HMAC (dùng device key dẫn xuất từ master secret trên host), sequence,
khoảng cách 10s, QoS/retain và LWT retained. Chỉ ghi số liệu tổng hợp ra file;
KHÔNG ghi payload, PEM, private key hay secret vào báo cáo.

Chạy thật (có bo):

    python tools/soak_collector.py --duration-min 240 --secret-file C:\\secure\\master.secret \\
        --out C:\\secure\\soak_result.json

Tự kiểm tra host-side (5 bản tin mẫu, không phải bằng chứng phần cứng):

    python tools/soak_collector.py --self-test 5 --interval-sec 1 \\
        --out C:\\Users\\DELL\\AppData\\Local\\Temp\\opencode\\soak_selftest.json
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import threading
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT / "tools", SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import jsonschema  # noqa: E402
from iot_protocol.headers import USER_PROP_CORRELATION_ID, USER_PROP_SIGNATURE, USER_PROP_TS_MS, verify_envelope  # noqa: E402
from iot_protocol.signing import derive_device_key  # noqa: E402
from paho.mqtt import client as mqtt  # noqa: E402
from paho.mqtt.enums import CallbackAPIVersion  # noqa: E402
from paho.mqtt.properties import PacketTypes, Properties  # noqa: E402

SITE = "SITE_01"
DEVICE_TYPE = "light"
DEVICE_ID = "LGT_NODE_001"
TELEMETRY_TOPIC = f"telemetry/v1/{SITE}/{DEVICE_TYPE}/{DEVICE_ID}"
STATUS_TOPIC = f"status/v1/{SITE}/{DEVICE_TYPE}/{DEVICE_ID}"
SCHEMA_PATH = ROOT / "docs" / "data_contracts" / "schemas.json"
REQUIRED_PROPS = (USER_PROP_CORRELATION_ID, USER_PROP_TS_MS, USER_PROP_SIGNATURE)


def _configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _read_master(path: Optional[str]) -> str:
    if not path:
        raise ValueError("cần --secret-file (hoặc --self-test)")
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("file secret rỗng")
    return text


def _make_client(client_id: str, certfile: Optional[str], keyfile: Optional[str],
                 cafile: str, userdata) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=CallbackAPIVersion.VERSION2,
        client_id=client_id, protocol=mqtt.MQTTv5,
    )
    client.tls_set(
        ca_certs=cafile,
        certfile=certfile, keyfile=keyfile,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )
    client.user_data_set(userdata)
    return client


class Collector:
    def __init__(self, key: bytes, schema: dict, interval_sec: float,
                 tolerance_sec: float, first_sequence: int) -> None:
        self.key = key
        self.schema = schema
        self.interval_sec = interval_sec
        self.tolerance_sec = tolerance_sec
        self.next_sequence = first_sequence
        self.received = 0
        self.schema_ok = 0
        self.signature_ok = 0
        self.sequence_ok = 0
        self.qos_ok = 0
        self.retain_ok = 0
        self.interval_ok = 0
        self.errors: list[str] = []
        self.last_arrival: Optional[float] = None
        self.status_messages = 0
        self.status_retained = 0
        self.lwt_offline = 0

    def on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        del client, userdata, flags, properties
        value = reason_code.value if hasattr(reason_code, "value") else int(reason_code)
        if value >= 0x80:
            self.errors.append(f"connect_rejected:{value}")

    def on_subscribe(self, client, userdata, mid, reason_codes, properties) -> None:
        del client, userdata, mid, properties
        for reason in reason_codes:
            value = reason.value if hasattr(reason, "value") else int(reason)
            if value >= 0x80:
                self.errors.append(f"subscribe_rejected:{value}")

    def on_message(self, client, userdata, message) -> None:
        del client, userdata
        if message.topic == STATUS_TOPIC:
            self.status_messages += 1
            if message.retain:
                self.status_retained += 1
            if message.payload.strip().lower() == b"offline":
                self.lwt_offline += 1
            return
        if message.topic != TELEMETRY_TOPIC:
            self.errors.append("unexpected_topic")
            return

        self.received += 1
        props = dict(getattr(message.properties, "UserProperty", []) or [])
        if any(name not in props for name in REQUIRED_PROPS):
            self.errors.append("missing_user_property")
            return
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.errors.append("bad_json")
            return
        try:
            jsonschema.validate(payload, self.schema)
        except jsonschema.ValidationError:
            self.errors.append("schema_invalid")
            return
        self.schema_ok += 1

        try:
            verify_envelope(self.key, TELEMETRY_TOPIC, message.payload, props)
        except Exception:
            self.errors.append("signature_invalid")
            return
        self.signature_ok += 1

        if payload.get("message_id") != props[USER_PROP_CORRELATION_ID]:
            self.errors.append("correlation_mismatch")
        if payload.get("sequence") != self.next_sequence:
            self.errors.append(f"sequence_gap:expected={self.next_sequence}")
        else:
            self.sequence_ok += 1
        self.next_sequence += 1

        if message.qos == 1:
            self.qos_ok += 1
        else:
            self.errors.append(f"qos:{message.qos}")
        if not message.retain:
            self.retain_ok += 1
        else:
            self.errors.append("telemetry_retained")

        now = time.monotonic()
        if self.last_arrival is not None:
            delta = now - self.last_arrival
            if abs(delta - self.interval_sec) <= self.tolerance_sec:
                self.interval_ok += 1
            else:
                self.errors.append(f"interval:{delta:.2f}")
        self.last_arrival = now

    def summary(self, elapsed_sec: float) -> dict:
        expected = max(1, int(elapsed_sec / self.interval_sec))
        return {
            "elapsed_sec": round(elapsed_sec, 1),
            "interval_sec": self.interval_sec,
            "expected_telemetry": expected,
            "telemetry_received": self.received,
            "coverage_pct": round(100.0 * self.received / expected, 2),
            "schema_ok": self.schema_ok,
            "signature_ok": self.signature_ok,
            "sequence_ok": self.sequence_ok,
            "qos1_ok": self.qos_ok,
            "telemetry_non_retained": self.retain_ok,
            "interval_ok": self.interval_ok,
            "status_messages": self.status_messages,
            "status_retained": self.status_retained,
            "lwt_offline": self.lwt_offline,
            "error_counts": {
                code: sum(1 for item in self.errors if item.split(":")[0] == code)
                for code in sorted({item.split(":")[0] for item in self.errors})
            },
        }


def _connect(client: mqtt.Client, host: str, port: int) -> None:
    client.connect(host, port, keepalive=15)
    client.loop_start()
    deadline = time.monotonic() + 10.0
    while not client.is_connected() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not client.is_connected():
        raise RuntimeError("không kết nối được broker mTLS")


def _subscribe(client: mqtt.Client, topics: list[str]) -> None:
    info, mid = client.subscribe([(topic, 1) for topic in topics])
    if info != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"subscribe lỗi: {info}")
    deadline = time.monotonic() + 10.0
    while mid is None and time.monotonic() < deadline:
        time.sleep(0.05)


def _publish_sample(count: int, interval_sec: float, host: str, port: int,
                    cafile: str, certfile: str, keyfile: str) -> None:
    """Chỉ dùng cho self-test: phát payload mẫu đã ký bằng device key giả."""
    import firmware_payload_sample as sample
    key = derive_device_key(sample.MASTER, SITE, DEVICE_TYPE, DEVICE_ID)
    userdata: list = []
    client = _make_client("soak-selftest-publisher", certfile, keyfile, cafile, userdata)
    _connect(client, host, port)
    try:
        for seq in range(1, count + 1):
            body, props = sample.sample_message(sequence=seq, ts_ms=int(time.time() * 1000))
            publish_props = Properties(PacketTypes.PUBLISH)
            publish_props.UserProperty = list(props.items())
            info = client.publish(
                TELEMETRY_TOPIC,
                json.dumps(body, separators=(",", ":"), ensure_ascii=False),
                qos=1, retain=False, properties=publish_props,
            )
            info.wait_for_publish(timeout=5)
            time.sleep(interval_sec)
        status_props = Properties(PacketTypes.PUBLISH)
        client.publish(STATUS_TOPIC, "online", qos=1, retain=True,
                       properties=status_props).wait_for_publish(timeout=5)
    finally:
        client.disconnect()
        client.loop_stop()


def main(argv: Optional[list[str]] = None) -> int:
    _configure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8885)
    parser.add_argument("--cafile", default=str(ROOT / "generated/test-clients/server-ca.crt"))
    parser.add_argument("--certfile", default=str(ROOT / "generated/test-clients/field-bridge-s01.crt"))
    parser.add_argument("--keyfile", default=str(ROOT / "generated/test-clients/field-bridge-s01.key"))
    parser.add_argument("--publisher-certfile", default=str(ROOT / "generated/test-clients/dev_SITE_01_LGT_NODE_001.crt"))
    parser.add_argument("--publisher-keyfile", default=str(ROOT / "generated/test-clients/dev_SITE_01_LGT_NODE_001.key"))
    parser.add_argument("--secret-file", help="master secret; CHỈ đọc trên host")
    parser.add_argument("--duration-min", type=float, default=240.0)
    parser.add_argument("--interval-sec", type=float, default=10.0)
    parser.add_argument("--tolerance-sec", type=float, default=2.0)
    parser.add_argument("--first-sequence", type=int, default=1)
    parser.add_argument("--out", required=True, help="file JSON tổng hợp (không chứa payload/secret)")
    parser.add_argument("--self-test", type=int, metavar="N",
                        help="phát N bản tin mẫu để kiểm tra collector (KHÔNG phải bằng chứng bo)")
    args = parser.parse_args(argv)

    if args.self_test is not None:
        import firmware_payload_sample as sample
        master = sample.MASTER
        duration_sec = args.self_test * args.interval_sec + 5
    else:
        master = _read_master(args.secret_file)
        duration_sec = args.duration_min * 60

    key = derive_device_key(master, SITE, DEVICE_TYPE, DEVICE_ID)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    collector = Collector(key, schema, args.interval_sec,
                          args.tolerance_sec, args.first_sequence)
    client = _make_client("soak-collector", args.certfile, args.keyfile,
                          args.cafile, collector)
    client.on_connect = collector.on_connect
    client.on_subscribe = collector.on_subscribe
    client.on_message = collector.on_message
    _connect(client, args.host, args.port)
    _subscribe(client, [TELEMETRY_TOPIC, STATUS_TOPIC])
    if args.self_test is not None:
        threading.Thread(
            target=_publish_sample,
            args=(args.self_test, args.interval_sec, args.host, args.port,
                  args.cafile, args.publisher_certfile, args.publisher_keyfile),
            daemon=True,
        ).start()

    started = time.monotonic()
    next_progress = started + 60
    try:
        while time.monotonic() - started < duration_sec:
            now = time.monotonic()
            if now >= next_progress:
                print(f"soak: {int(now - started)}s, telemetry={collector.received}, "
                      f"lỗi={len(collector.errors)}", flush=True)
                next_progress = now + 60
            time.sleep(0.5)
    finally:
        client.disconnect()
        client.loop_stop()

    result = collector.summary(time.monotonic() - started)
    result["self_test"] = args.self_test is not None
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    print(f"Đã ghi tổng hợp vào {out} (không chứa payload/secret)")
    ok = (not collector.errors and collector.received > 0
          and collector.status_retained > 0)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
