"""Durable command outbox with mTLS and telemetry readback confirmation."""

import json
import logging
import os
import queue
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from iot_protocol.headers import build_headers, verify_envelope
from iot_protocol.mqtt5 import make_publish_properties
from iot_protocol.northbound_payload import build_envelope, derive_gateway_key
from iot_protocol.signing import derive_device_key

from .db import connection, secret

LOG = logging.getLogger(__name__)


def command_packet(row, signing_secret):
    cid = str(row["command_id"])
    payload = {"command_id": cid, "actor": str(row["user_id"]), "action": "DIM",
               "requested_value": row["brightness"], "expires_at": int(row["expires_at"].timestamp())}
    field, dtype, code = row["field_site"], row["device_type"], row["device_code"]
    mode = row["command_mode"]
    if mode == "legacy":
        topic = "pccom/lighting/" + field + "/" + code + "/command"
        key = derive_device_key(signing_secret, field, dtype, code)
    elif mode == "northbound":
        topic = "pccom/v1/" + row["tenant_code"] + "/" + row["cloud_site"] + "/" + row["gateway_code"] + "/command"
        payload = build_envelope(
            tenant_id=row["tenant_code"], site_id=row["cloud_site"], gateway_id=row["gateway_code"],
            source_site_id=field, device_type=dtype, device_id=code, category="command", data=payload,
        )
        payload["correlation_id"] = cid
        key = derive_gateway_key(signing_secret, row["tenant_code"], row["cloud_site"], row["gateway_code"])
    else:
        topic = "commands/v1/" + field + "/" + dtype + "/" + code + "/dim"
        key = derive_device_key(signing_secret, field, dtype, code)
    encoded = json.dumps(payload, separators=(",", ":"))
    headers, _, _ = build_headers(key, topic, encoded, correlation_id=cid)
    props = make_publish_properties(headers, message_expiry_interval=max(
        1, int((row["expires_at"] - datetime.now(timezone.utc)).total_seconds())),
        correlation_data=cid.encode())
    return topic, encoded, props


class Dispatcher:
    def __init__(self):
        self.connected = threading.Event()
        self.halt = threading.Event()
        self.client = None
        self.thread = None
        self.results = queue.Queue(maxsize=1000)

    def start(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="pccom-web-gateway", protocol=mqtt.MQTTv5)
        self.client.tls_set(ca_certs=os.environ["MQTT_CA"], certfile=os.environ["MQTT_CERT"], keyfile=os.environ["MQTT_KEY"])
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = lambda *args: self.connected.clear()
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(1, 30)
        self.client.connect_async(os.getenv("MQTT_HOST", "mosquitto"), int(os.getenv("MQTT_PORT", "8883")))
        self.client.loop_start()
        self.thread = threading.Thread(target=self.run, name="command-outbox", daemon=True)
        self.thread.start()

    def stop(self):
        self.halt.set()
        if self.thread:
            self.thread.join(timeout=10)
        if self.client:
            self.client.disconnect()
            self.client.loop_stop()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            return
        client.subscribe([("commands/v1/+/+/+/dim/result", 1), ("pccom/v1/+/+/+/ack", 1),
                          ("pccom/lighting/+/+/result", 1)])
        self.connected.set()

    def on_message(self, client, userdata, message):
        # The MQTT network thread must keep consuming PUBACKs while a batch of
        # commands is being published. A database UPDATE here can wait on the
        # outbox transaction and deadlock that same transaction's next PUBACK.
        if message.retain or len(message.payload) > 16384:
            return
        try:
            self.results.put_nowait(message)
        except queue.Full:
            LOG.warning("Result queue full; command still requires telemetry confirmation")

    def apply_result(self, message):
        try:
            raw = json.loads(message.payload)
            data = raw.get("data", raw)
            cid = data.get("command_id", raw.get("correlation_id"))
            with connection(dicts=True) as conn:
                row = conn.execute("""
                    SELECT c.*,b.field_site,b.device_type,b.device_code,b.command_mode,
                           b.tenant_code,b.cloud_site,b.gateway_code
                    FROM lighting.staging_commands c JOIN lighting.ingestion_bindings b
                    USING (tenant_id,site_id,asset_id) WHERE command_id=%s
                """, (cid,)).fetchone()
                if not row or row["state"] in ("verified", "rejected", "expired", "failed"):
                    return
                mode = row["command_mode"]
                expected = ("commands/v1/" + row["field_site"] + "/" + row["device_type"] + "/" + row["device_code"] + "/dim/result")
                key = derive_device_key(secret("SIGNING_SECRET"), row["field_site"], row["device_type"], row["device_code"])
                if mode == "legacy":
                    expected = "pccom/lighting/" + row["field_site"] + "/" + row["device_code"] + "/result"
                elif mode == "northbound":
                    expected = "pccom/v1/" + row["tenant_code"] + "/" + row["cloud_site"] + "/" + row["gateway_code"] + "/ack"
                    key = derive_gateway_key(secret("SIGNING_SECRET"), row["tenant_code"], row["cloud_site"], row["gateway_code"])
                if message.topic != expected:
                    return
                if mode != "legacy":
                    header_cid, _, _ = verify_envelope(key, message.topic, message.payload, getattr(message.properties, "UserProperty", []))
                    if header_cid != str(row["command_id"]):
                        return
                state = str(data.get("status", "")).lower()
                if state not in ("executed", "rejected", "expired", "failed", "acknowledged"):
                    return
                conn.execute("""
                    UPDATE lighting.staging_commands SET state=%s,ack_at=clock_timestamp(),
                      result=%s,reason=%s,updated_at=clock_timestamp()
                    WHERE command_id=%s AND state IN ('queued','sent','acknowledged','executed')
                """, (state, json.dumps(data), str(data.get("reason", ""))[:500], cid))
        except Exception:
            LOG.exception("Invalid or uncorrelated command result")

    def tick(self):
        for _ in range(1000):
            try:
                message = self.results.get_nowait()
            except queue.Empty:
                break
            self.apply_result(message)
        with connection(dicts=True) as conn, conn.transaction():
            # Readback only confirms what telemetry reports; is_demo stays visible.
            conn.execute("""
                UPDATE lighting.staging_commands c SET state='verified',verified_at=t.received_time,
                  updated_at=clock_timestamp(),reason='Matched a newer synced measured telemetry report'
                FROM lighting.telemetry_lighting t
                WHERE c.tenant_id=t.tenant_id AND c.site_id=t.site_id AND c.asset_id=t.asset_id
                  AND c.state IN ('sent','acknowledged','executed') AND c.sent_at IS NOT NULL
                  AND t.received_time>=c.sent_at AND t.source_time>=c.sent_at
                  AND t.received_time<=c.expires_at AND t.source_time<=c.expires_at
                  AND t.clock_quality='synced'
                  AND t.details->'metrics'->'dimming_pct'->>'quality'='measured'
                  AND (t.details->'metrics'->'dimming_pct'->>'value')::numeric=c.brightness
                  AND NOT EXISTS (
                    SELECT 1 FROM lighting.staging_commands newer
                    WHERE newer.asset_id=c.asset_id AND newer.tenant_id=c.tenant_id
                      AND newer.created_at>c.created_at AND newer.sent_at IS NOT NULL
                      AND newer.sent_at<=t.source_time)
            """)
            conn.execute("""
                UPDATE lighting.staging_commands SET state='expired',reason='No matching telemetry before deadline',
                    updated_at=clock_timestamp()
                WHERE state IN ('queued','sent','acknowledged','executed') AND expires_at<clock_timestamp()
            """)
            if not self.connected.is_set():
                return
            rows = conn.execute("""
                SELECT c.*,b.field_site,b.device_type,b.device_code,b.command_mode,
                       b.tenant_code,b.cloud_site,b.gateway_code
                FROM lighting.staging_commands c JOIN lighting.ingestion_bindings b
                USING (tenant_id,site_id,asset_id)
                WHERE c.state='queued' AND c.expires_at>clock_timestamp()
                ORDER BY c.created_at LIMIT 50 FOR UPDATE OF c SKIP LOCKED
            """).fetchall()
            for row in rows:
                topic, payload, props = command_packet(row, secret("SIGNING_SECRET"))
                info = self.client.publish(topic, payload, qos=1, retain=False, properties=props)
                info.wait_for_publish(timeout=5)
                if not info.is_published():
                    raise RuntimeError("Command publish not acknowledged; outbox stays queued")
                conn.execute("""
                    UPDATE lighting.staging_commands SET state='sent',sent_at=clock_timestamp(),
                       attempts=attempts+1,updated_at=clock_timestamp()
                    WHERE command_id=%s
                """, (row["command_id"],))

    def run(self):
        while not self.halt.is_set():
            try:
                self.tick()
            except Exception:
                LOG.exception("Command outbox retry")
            self.halt.wait(1)
