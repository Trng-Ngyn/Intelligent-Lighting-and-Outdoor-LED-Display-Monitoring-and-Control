"""Send synthetic W3-DE telemetry and verify durable database rows."""

import argparse
import copy
from datetime import datetime, timedelta, timezone
import json
import os
import threading
import time
from uuid import UUID, uuid4, uuid5

import paho.mqtt.client as mqtt

from worker import APP_DIR, database_connection, raw_fingerprint


TENANT = "11111111-1111-4111-8111-111111111111"
SITE = "22222222-2222-4222-8222-222222222222"
ASSETS = {
    "lighting": ("44444444-4444-4444-8444-444444444444",
                 "66666666-6666-4666-8666-666666666666"),
    "led": ("55555555-5555-4555-8555-555555555555",
            "77777777-7777-4777-8777-777777777777"),
}


def timestamp(value):
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def packet(kind, message_id, sequence, source_time, energy_wh, interval_seconds):
    asset_id, device_id = ASSETS[kind]
    return {
        "schema_version": 1,
        "message_type": "telemetry." + kind,
        "tenant_id": TENANT,
        "site_id": SITE,
        "asset_id": asset_id,
        "device_id": device_id,
        "message_id": str(message_id),
        "source_time": timestamp(source_time),
        "received_time": timestamp(datetime.now(timezone.utc)),
        "sequence": sequence,
        "firmware": "1.0.0",
        "clock_quality": "synced",
        "energy_interval_start": timestamp(source_time - timedelta(seconds=interval_seconds)),
        "metrics": {
            "power_w": {"value": energy_wh * 3600 / interval_seconds,
                        "unit": "W", "quality": "measured"},
            "energy_interval_wh": {"value": energy_wh, "unit": "Wh",
                                   "quality": "measured"},
            "voltage_v": {"value": 220, "unit": "V", "quality": "measured"},
        },
    }


def topic_for(kind):
    device_type = "light" if kind == "lighting" else "led_display"
    asset_code = "W5_LIGHT_001" if kind == "lighting" else "W5_LED_001"
    return f"telemetry/v1/W5_DEMO/{device_type}/{asset_code}"


def encode(payload):
    return json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")


def stored_count(connection, message_ids):
    return connection.execute("""
        SELECT COUNT(*) FROM (
            SELECT message_id FROM lighting.telemetry_lighting
            WHERE tenant_id = %s AND site_id = %s AND message_id = ANY(%s::uuid[])
            UNION ALL
            SELECT message_id FROM lighting.telemetry_led
            WHERE tenant_id = %s AND site_id = %s AND message_id = ANY(%s::uuid[])
        ) AS received
    """, (TENANT, SITE, message_ids, TENANT, SITE, message_ids)).fetchone()[0]


def wait_for_rows(connection, message_ids, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        count = stored_count(connection, message_ids)
        if count == len(message_ids):
            return count
        time.sleep(0.1)
    raise RuntimeError(f"Database received {count}/{len(message_ids)} unique records")


def publish_window(client, packets):
    publications = []
    for topic, payload in packets:
        publication = client.publish(topic, payload, qos=1)
        if publication.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed: {publication.rc}")
        publications.append(publication)
    for publication in publications:
        publication.wait_for_publish(timeout=10)
        if not publication.is_published():
            raise RuntimeError("Broker did not acknowledge a published message")


def run_demo(client, connection):
    source_time = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    ) - timedelta(hours=1) + timedelta(minutes=15)
    lighting = packet("lighting", uuid4(), 1, source_time, 2, 60)
    led = packet("led", uuid4(), 1, source_time, 3, 60)
    invalid = copy.deepcopy(lighting)
    invalid["message_id"] = str(uuid4())
    invalid["metrics"]["power_w"]["value"] = -5
    valid_packets = [(topic_for("lighting"), encode(lighting)),
                     (topic_for("led"), encode(led))]
    invalid_packet = (topic_for("lighting"), encode(invalid))
    publish_window(client, valid_packets + [invalid_packet])
    message_ids = [UUID(lighting["message_id"]), UUID(led["message_id"])]
    wait_for_rows(connection, message_ids)

    fingerprint = raw_fingerprint(*invalid_packet)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        dlq_count = connection.execute(
            "SELECT COUNT(*) FROM lighting.ingestion_dlq "
            "WHERE payload_hash = %s AND published_at IS NOT NULL",
            (fingerprint,),
        ).fetchone()[0]
        if dlq_count == 1:
            break
        time.sleep(0.1)
    if dlq_count != 1:
        raise RuntimeError("Invalid telemetry did not reach the durable DLQ")

    publish_window(client, valid_packets)
    time.sleep(0.6)
    count = stored_count(connection, message_ids)
    if count != 2:
        raise RuntimeError(f"Replay produced {count} rows instead of 2")
    print("PASS: 2 valid messages stored, 1 invalid message in DLQ; replay kept 2 rows.")
    print("Sample interval energy: lighting = 2 Wh, LED = 3 Wh.")


def run_benchmark(client, connection, count):
    run_id = uuid4()
    end_time = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    ) - timedelta(hours=2)
    message_ids = [uuid5(run_id, str(index)) for index in range(count)]
    started = time.monotonic()
    for first in range(0, count, 500):
        packets = []
        for index in range(first, min(first + 500, count)):
            kind = "lighting" if index % 2 == 0 else "led"
            source_time = end_time - timedelta(seconds=count - index)
            payload = packet(kind, message_ids[index], index, source_time, 0.001, 1)
            packets.append((topic_for(kind), encode(payload)))
        publish_window(client, packets)
    stored = wait_for_rows(connection, message_ids)
    elapsed = time.monotonic() - started
    rate = stored / elapsed
    print(json.dumps({
        "sent_unique": count,
        "stored_unique": stored,
        "elapsed_seconds": round(elapsed, 3),
        "records_per_second": round(rate, 2),
        "target_over_500": rate > 500,
    }, indent=2))
    if rate <= 500:
        raise SystemExit(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("demo", "benchmark"), default="demo")
    parser.add_argument("--count", type=int, default=10000)
    args = parser.parse_args()
    if args.count <= 0:
        parser.error("--count must be positive")
    connected = threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="w5-demo-" + uuid4().hex,
                         protocol=mqtt.MQTTv5)
    client.max_inflight_messages_set(1000)

    def on_connect(client, userdata, flags, reason_code, properties):
        if not reason_code.is_failure:
            connected.set()

    client.on_connect = on_connect
    if os.getenv("MQTT_USERNAME"):
        client.username_pw_set(os.environ["MQTT_USERNAME"], os.getenv("MQTT_PASSWORD"))
    if os.getenv("MQTT_CA_FILE"):
        client.tls_set(ca_certs=os.environ["MQTT_CA_FILE"],
                       certfile=os.getenv("MQTT_CERT_FILE"),
                       keyfile=os.getenv("MQTT_KEY_FILE"))
    client.connect(os.getenv("MQTT_HOST", "mosquitto"),
                   int(os.getenv("MQTT_PORT", "1883")), keepalive=60)
    client.loop_start()
    try:
        if not connected.wait(15):
            raise RuntimeError("Publisher could not connect to the broker")
        with database_connection() as connection:
            connection.execute((APP_DIR / "w5_demo_assets.sql").read_text())
            if args.mode == "demo":
                run_demo(client, connection)
            else:
                run_benchmark(client, connection, args.count)
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
