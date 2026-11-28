"""Acceptance on the actual Docker/Timescale/mTLS stack, explicitly synthetic.

Fails instead of printing PASS when a target is not met. No direct aggregate
refresh is used: temporarily accelerate and then restore the hourly jobs.
"""

import json
import os
import ssl
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

import paho.mqtt.client as mqtt
from ingestion.publish_demo import packet, topic_for, encode, run_benchmark, run_demo
from ingestion.worker import database_connection
from iot_protocol.headers import build_headers, verify_envelope
from iot_protocol.mqtt5 import make_publish_properties
from iot_protocol.signing import derive_device_key


def wait(predicate, timeout=60):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if predicate():
            return
        time.sleep(.2)
    raise AssertionError("Timed out waiting for actual stored data or command readback")


def run(after_verified=None):
    if os.getenv("STAGING_DEMO") != "1":
        raise RuntimeError("Synthetic acceptance is allowed only in the explicit --demo environment")
    registry = json.loads(Path(os.getenv("STAGING_REGISTRY_FILE", "/run/config/registry.json")).read_text())
    assets = {a["device_code"]: a for a in registry["assets"]}
    secret_directory = Path(os.getenv("STAGING_SECRET_DIR", "/run/secrets"))
    signing = (secret_directory / "signing").read_text().strip()
    mqtt_host = os.getenv("MQTT_HOST", "mosquitto")
    mqtt_port = int(os.getenv("MQTT_PORT", "8883"))
    connected = threading.Event()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="w5-acceptance-" + uuid4().hex, protocol=mqtt.MQTTv5)
    client.tls_set(os.environ["MQTT_CA_FILE"], os.environ["MQTT_CERT_FILE"], os.environ["MQTT_KEY_FILE"])
    client.max_inflight_messages_set(1000)
    brightness = {a["device_code"]: 50 for a in registry["assets"]}
    callback_errors = []

    def telemetry(a, value, sequence):
        kind = a["kind"]
        p = packet(kind, uuid4(), sequence, datetime.now(timezone.utc), .01, 5)
        p.update(asset_id=a["asset_id"], device_id=a["device_id"])
        p["metrics"]["dimming_pct" if kind == "lighting" else "brightness_pct"] = {
            "value": value, "unit": "%", "quality": "measured"}
        topic = "telemetry/v1/" + a["field_site"] + "/" + ("light" if kind == "lighting" else "led_display") + "/" + a["device_code"]
        return topic, encode(p)

    def on_connect(c, u, f, rc, props):
        if not rc.is_failure:
            c.subscribe("commands/v1/W5_DEMO/+/+/dim", 1)
            connected.set()

    def on_message(c, u, msg):
        try:
            parts = msg.topic.split("/")
            a = assets[parts[4]]
            key = derive_device_key(signing, parts[2], parts[3], parts[4])
            cid, _, _ = verify_envelope(key, msg.topic, msg.payload, msg.properties.UserProperty)
            body = json.loads(msg.payload)
            assert body["command_id"] == cid and body["expires_at"] >= time.time()
            value = body["requested_value"]
            result = json.dumps({"command_id": cid, "status": "EXECUTED", "observed_value": value, "reason": "Synthetic test device"})
            topic = msg.topic + "/result"
            headers, _, _ = build_headers(key, topic, result, correlation_id=cid)
            c.publish(topic, result, qos=1, properties=make_publish_properties(headers))
            brightness[a["device_code"]] = value
        except Exception as exc:
            callback_errors.append(str(exc))

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(os.getenv("MQTT_HOST", "mosquitto"), int(os.getenv("MQTT_PORT", "8883")))
    client.loop_start()
    assert connected.wait(15), "mTLS client could not connect"
    halt = threading.Event()

    def heartbeat():
        sequence = 1
        while not halt.is_set():
            for code, a in assets.items():
                topic, payload = telemetry(a, brightness[code], sequence)
                client.publish(topic, payload, qos=1)
            sequence += 1
            halt.wait(2)

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        with database_connection() as conn:
            run_demo(client, conn)
            run_benchmark(client, conn, 10000)
            jobs = conn.execute("""
                SELECT j.job_id,j.schedule_interval FROM timescaledb_information.jobs j
                WHERE j.proc_name='policy_refresh_continuous_aggregate'
                AND j.hypertable_name IN ('energy_lighting_hourly','energy_led_hourly')
            """).fetchall()
            assert len(jobs) == 2
            try:
                for job, _ in jobs:
                    conn.execute("SELECT alter_job(%s,schedule_interval=>interval '5 seconds',next_start=>now())", (job,))

                def matched():
                    for kind in ("lighting", "led"):
                        mismatch = conn.execute("""
                            WITH raw AS (
                              SELECT tenant_id,site_id,asset_id,
                                time_bucket('1 hour',source_time,interval '1 microsecond') bucket,
                                sum(energy_interval_wh) energy_wh
                              FROM lighting.telemetry_""" + kind + """
                              WHERE source_time<date_trunc('hour',now()) AND clock_quality='synced'
                                AND energy_interval_wh IS NOT NULL
                                AND metric_quality->>'energy_interval_wh' IN ('measured','estimated')
                              GROUP BY 1,2,3,4
                            )
                            SELECT count(*) FROM raw r FULL JOIN lighting.energy_""" + kind + """_hourly h
                              USING(tenant_id,site_id,asset_id,bucket)
                            WHERE coalesce(abs(r.energy_wh-h.energy_wh)>0.000001,true)
                        """).fetchone()[0]
                        if mismatch:
                            return False
                    return True
                wait(matched, 90)
            finally:
                for job, schedule in jobs:
                    conn.execute("SELECT alter_job(%s,schedule_interval=>%s)", (job, schedule))
        base = os.getenv("API_BASE_URL", "http://api:8000/api/v1")

        def request(path, data=None, token=None, idem=None):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            if idem:
                headers["Idempotency-Key"] = idem
            req = Request(base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
            with urlopen(req, timeout=15) as response:
                return json.load(response)
        creds = {"username": "staging-operator", "password": (secret_directory / "operator_password").read_text().strip()}
        token = request("/auth/login", creds)["access_token"]
        actual = request("/console/assets", token=token)["assets"]
        assert len(actual) == len(assets) and all(a["is_demo"] for a in actual)
        light_ids = [a["asset_id"] for a in actual if a["kind"] == "lighting"]
        for ids, value in [([light_ids[0]], 25), (light_ids, 65)]:
            body = {"asset_ids": ids, "brightness": value}
            key = str(uuid4())
            accepted = request("/console/dimming", body, token, key)
            assert request("/console/dimming", body, token, key) == accepted
            wait(lambda: all(c["state"] == "verified" for c in request("/console/commands/" + accepted["batch_id"], token=token)["commands"]), 30)
        assert not callback_errors, callback_errors
        # Server must reject a client presenting no certificate.
        context = ssl.create_default_context(cafile=os.environ["MQTT_CA_FILE"])
        import socket
        refused = False
        try:
            with socket.create_connection((mqtt_host, mqtt_port), timeout=5) as raw:
                with context.wrap_socket(raw, server_hostname=mqtt_host) as secure:
                    secure.sendall(b"\x10\x0e\x00\x04MQTT\x04\x02\x00\x3c\x00\x02no")
                    refused = not secure.recv(4)
        except (ssl.SSLError, ConnectionError, OSError):
            refused = True
        assert refused, "Broker accepted a connection without a client certificate"
        # A valid certificate with the health identity must not publish telemetry.
        denied = threading.Event()
        bad = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="acl-negative", protocol=mqtt.MQTTv5)
        bad.tls_set(os.environ["MQTT_CA_FILE"],
                    os.getenv("MQTT_HEALTH_CERT", "/run/health/client.crt"),
                    os.getenv("MQTT_HEALTH_KEY", "/run/health/client.key"))
        bad.on_publish = lambda c, u, mid, reason, props: denied.set() if reason.is_failure else None
        try:
            bad.connect(mqtt_host, mqtt_port)
            bad.loop_start()
            bad.publish(topic_for("lighting"), encode(packet("lighting", uuid4(), 1,
                        datetime.now(timezone.utc), .01, 5)), qos=1)
            assert denied.wait(10), "Health identity was not denied telemetry publication"
        finally:
            bad.disconnect()
            bad.loop_stop()
        if after_verified:
            after_verified()
        print(json.dumps({"synthetic_acceptance": "PASS", "mqtt_mtls": True, "benchmark_target": ">500/s",
                          "mqtt_acl_negative": True,
                          "automatic_hourly_aggregates": True, "single_and_group_telemetry_readback": True,
                          "real_esp32_tested": False}))
    finally:
        halt.set()
        thread.join(5)
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    run()
