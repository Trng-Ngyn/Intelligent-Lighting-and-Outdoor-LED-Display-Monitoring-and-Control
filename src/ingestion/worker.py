"""MQTT 5 worker for the approved W3-DE Draft-07 telemetry contracts."""

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
import queue
import signal
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from jsonschema import Draft7Validator, FormatChecker, ValidationError


LOGGER = logging.getLogger("w5-ingestion")
APP_DIR = Path(__file__).resolve().parent
READY_FILE = Path("/tmp/w5-ingestion-ready")
KEY_COLUMNS = ("tenant_id", "site_id", "asset_id", "message_id")
VALUE_COLUMNS = (
    "power_w", "energy_interval_wh", "energy_register_wh", "voltage_v",
    "current_a", "power_factor", "illuminance_lx", "temperature_c",
)
ROW_COLUMNS = (
    "tenant_id", "site_id", "asset_id", "device_id", "kind", "message_id",
    "schema_version", "source_time", "received_time", "sequence", "firmware",
    "clock_quality", "power_w", "energy_interval_wh", "energy_interval_start",
    "energy_register_wh", "counter_epoch", "voltage_v", "current_a",
    "power_factor", "illuminance_lx", "temperature_c", "metric_quality", "details",
)
KIND_BY_MESSAGE = {"telemetry.lighting": "lighting", "telemetry.led": "led"}


def database_connection():
    return psycopg.connect(
        host=os.getenv("PGHOST", "timescaledb"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "pccom_staging"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD", ""),
        connect_timeout=5,
        application_name="pccom-w5-ingestion",
        autocommit=True,
    )


def utc_datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def raw_fingerprint(topic, payload):
    return hashlib.sha256(topic.encode("utf-8") + b"\0" + payload).hexdigest()


def reject_json_constant(value):
    raise ValueError(f"Non-JSON numeric constant: {value}")


@dataclass
class Delivery:
    topic: str
    payload: bytes
    mid: int = 0
    qos: int = 1
    generation: int = 0
    received_time: datetime = None

    def __post_init__(self):
        if self.received_time is None:
            self.received_time = datetime.now(timezone.utc)


@dataclass
class Record:
    delivery: Delivery
    values: dict
    payload_hash: str

    @property
    def key(self):
        return tuple(self.values[name] for name in KEY_COLUMNS)


class PayloadValidator:
    def __init__(self, schema_directory):
        self.validators = {}
        for message_type in KIND_BY_MESSAGE:
            path = schema_directory / f"{message_type}.v1.schema.json"
            schema = json.loads(path.read_text(encoding="utf-8-sig"))
            Draft7Validator.check_schema(schema)
            self.validators[message_type] = Draft7Validator(
                schema, format_checker=FormatChecker()
            )

    def parse(self, delivery):
        if len(delivery.payload) > 16384:
            raise ValueError("Telemetry exceeds the project 16 KiB payload limit")
        payload = json.loads(
            delivery.payload.decode("utf-8"), parse_constant=reject_json_constant
        )
        if not isinstance(payload, dict):
            raise ValueError("Telemetry must be a JSON object")
        message_type = payload.get("message_type")
        if not isinstance(message_type, str) or message_type not in self.validators:
            raise ValueError("message_type must be telemetry.lighting or telemetry.led")
        self.validators[message_type].validate(payload)
        json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")

        values = dict(payload)
        for name in ("tenant_id", "site_id", "asset_id", "device_id", "message_id"):
            values[name] = UUID(payload[name])
        values["kind"] = KIND_BY_MESSAGE[message_type]
        values["source_time"] = utc_datetime(payload["source_time"])
        values["received_time"] = delivery.received_time
        values["energy_interval_start"] = None
        if "energy_interval_start" in payload:
            values["energy_interval_start"] = utc_datetime(payload["energy_interval_start"])
            if values["energy_interval_start"] >= values["source_time"]:
                raise ValueError("energy_interval_start must precede source_time")
        values["counter_epoch"] = None
        if "counter_epoch" in payload:
            values["counter_epoch"] = UUID(payload["counter_epoch"])

        metrics = payload["metrics"]
        for name in VALUE_COLUMNS:
            values[name] = metrics.get(name, {}).get("value")
        values["metric_quality"] = Jsonb({
            name: metric["quality"] for name, metric in metrics.items()
        })
        values["details"] = Jsonb({
            "topic": delivery.topic,
            "input_received_time": payload["received_time"],
            "metrics": {name: value for name, value in metrics.items()
                        if name not in VALUE_COLUMNS},
        })
        # The receiver timestamp may change when the same source message is replayed.
        content = {name: value for name, value in payload.items()
                   if name != "received_time"}
        digest = hashlib.sha256(json.dumps(
            content, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")).hexdigest()
        return Record(delivery, values, digest)


class BatchStore:
    def __init__(self, connection, validator):
        self.connection = connection
        self.validator = validator
        connection.execute((APP_DIR / "w5_ingestion.sql").read_text())
        connection.execute("""
            CREATE TEMP TABLE w5_batch
                (LIKE lighting.telemetry_lighting INCLUDING DEFAULTS,
                 payload_hash text NOT NULL)
                ON COMMIT DELETE ROWS;
            CREATE TEMP TABLE w5_new_keys (
                tenant_id uuid, site_id uuid, asset_id uuid, message_id uuid
            ) ON COMMIT DELETE ROWS;
        """)

    def save_dlq(self, delivery, reason):
        self.connection.execute("""
            INSERT INTO lighting.ingestion_dlq
                (payload_hash, topic, payload, reason, received_time)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (payload_hash) DO NOTHING
        """, (raw_fingerprint(delivery.topic, delivery.payload), delivery.topic,
              delivery.payload, str(reason)[:2000], delivery.received_time))

    def save_batch(self, deliveries):
        records = {}
        invalid = []
        duplicate_count = 0
        for delivery in deliveries:
            try:
                record = self.validator.parse(delivery)
                previous = records.get(record.key)
                if previous is None:
                    records[record.key] = record
                elif previous.payload_hash == record.payload_hash:
                    duplicate_count += 1
                else:
                    invalid.append((delivery, "message_id reused with different content"))
            except (ValueError, UnicodeError, OverflowError, ValidationError) as exc:
                invalid.append((delivery, str(exc)))

        with self.connection.transaction():
            for delivery, reason in invalid:
                self.save_dlq(delivery, reason)
            inserted = self.save_records(list(records.values()))
        duplicate_count += len(records) - inserted[0] - inserted[1]
        return inserted[0], duplicate_count, len(invalid) + inserted[1]

    def save_records(self, records):
        if not records:
            return 0, 0
        columns = (*ROW_COLUMNS, "payload_hash")
        copy_command = sql.SQL("COPY w5_batch ({}) FROM STDIN").format(
            sql.SQL(", ").join(map(sql.Identifier, columns))
        )
        with self.connection.cursor().copy(copy_command) as copy:
            for record in records:
                copy.write_row(tuple(record.values[name] for name in ROW_COLUMNS)
                               + (record.payload_hash,))
        self.connection.execute("""
            WITH added AS (
                INSERT INTO lighting.ingestion_receipts
                    (tenant_id, site_id, asset_id, message_id, source_time, payload_hash)
                SELECT tenant_id, site_id, asset_id, message_id, source_time, payload_hash
                FROM w5_batch
                ON CONFLICT DO NOTHING
                RETURNING tenant_id, site_id, asset_id, message_id
            )
            INSERT INTO w5_new_keys SELECT * FROM added
        """)
        conflicts = set(self.connection.execute("""
            SELECT b.tenant_id, b.site_id, b.asset_id, b.message_id
            FROM w5_batch b JOIN lighting.ingestion_receipts r
                USING (tenant_id, site_id, asset_id, message_id)
            WHERE b.payload_hash <> r.payload_hash
        """).fetchall())
        for record in records:
            if record.key in conflicts:
                self.save_dlq(record.delivery, "message_id reused with different content")

        inserted = 0
        for kind in ("lighting", "led"):
            query = sql.SQL("""
                INSERT INTO lighting.{} ({})
                SELECT {} FROM w5_batch b JOIN w5_new_keys k
                    USING (tenant_id, site_id, asset_id, message_id)
                WHERE b.kind = %s
                ON CONFLICT DO NOTHING
            """).format(
                sql.Identifier("telemetry_" + kind),
                sql.SQL(", ").join(map(sql.Identifier, ROW_COLUMNS)),
                sql.SQL(", ").join(sql.Identifier("b", name) for name in ROW_COLUMNS),
            )
            inserted += self.connection.execute(query, (kind,)).rowcount
        return inserted, len(conflicts)

    def save_with_isolation(self, deliveries):
        try:
            return self.save_batch(deliveries)
        except (psycopg.IntegrityError, psycopg.DataError):
            # Isolate a permanently invalid row while retaining the valid rows.
            totals = [0, 0, 0]
            for delivery in deliveries:
                try:
                    result = self.save_batch([delivery])
                except (psycopg.IntegrityError, psycopg.DataError) as exc:
                    with self.connection.transaction():
                        self.save_dlq(delivery, f"Database rejected record: {exc}")
                    result = (0, 0, 1)
                totals = [left + right for left, right in zip(totals, result)]
            return tuple(totals)

    def publish_dlq(self, client):
        with self.connection.transaction():
            rows = self.connection.execute("""
                SELECT id, topic, payload, reason, received_time
                FROM lighting.ingestion_dlq WHERE published_at IS NULL
                ORDER BY id LIMIT 50 FOR UPDATE SKIP LOCKED
            """).fetchall()
            for row_id, topic, payload, reason, received_time in rows:
                envelope = json.dumps({
                    "dlq_id": row_id, "topic": topic, "reason": reason,
                    "received_time": received_time.isoformat(),
                    "payload_base64": base64.b64encode(bytes(payload)).decode("ascii"),
                })
                publication = client.publish("dlq/v1/telemetry", envelope, qos=1)
                if publication.rc != mqtt.MQTT_ERR_SUCCESS:
                    return
                publication.wait_for_publish(timeout=3)
                if not publication.is_published():
                    return
                self.connection.execute("""
                    UPDATE lighting.ingestion_dlq SET published_at = now() WHERE id = %s
                """, (row_id,))


class IngestionWorker:
    def __init__(self):
        READY_FILE.unlink(missing_ok=True)
        self.stop = threading.Event()
        self.connected = threading.Event()
        self.subscribed = threading.Event()
        self.generation_lock = threading.Lock()
        self.generation = 0
        self.messages = queue.Queue(maxsize=5000)
        self.batch_size = int(os.getenv("BATCH_SIZE", "500"))
        self.flush_seconds = float(os.getenv("FLUSH_SECONDS", "0.2"))
        self.validator = PayloadValidator(APP_DIR / "schemas")
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=os.getenv("MQTT_CLIENT_ID", "pccom-w5-ingestion"),
            protocol=mqtt.MQTTv5, manual_ack=True,
        )
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        if os.getenv("MQTT_USERNAME"):
            self.client.username_pw_set(os.environ["MQTT_USERNAME"],
                                        os.getenv("MQTT_PASSWORD"))
        if os.getenv("MQTT_CA_FILE"):
            self.client.tls_set(
                ca_certs=os.environ["MQTT_CA_FILE"],
                certfile=os.getenv("MQTT_CERT_FILE"),
                keyfile=os.getenv("MQTT_KEY_FILE"),
            )

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            LOGGER.error("MQTT connection refused: %s", reason_code)
            return
        with self.generation_lock:
            self.generation += 1
        self.connected.set()
        client.subscribe(os.getenv("MQTT_TOPIC", "telemetry/v1/#"), qos=1)

    def on_subscribe(self, client, userdata, mid, reason_codes, properties):
        if any(code.is_failure for code in reason_codes):
            LOGGER.error("MQTT subscription refused: %s", reason_codes)
            return
        self.subscribed.set()
        LOGGER.info("MQTT_READY topic=%s", os.getenv("MQTT_TOPIC", "telemetry/v1/#"))

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected.clear()
        self.subscribed.clear()
        READY_FILE.unlink(missing_ok=True)
        LOGGER.warning("MQTT disconnected: %s; reconnecting", reason_code)

    def on_message(self, client, userdata, message):
        with self.generation_lock:
            delivery = Delivery(message.topic, bytes(message.payload), message.mid,
                                message.qos, self.generation)
        try:
            self.messages.put(delivery, timeout=1)
        except queue.Full:
            LOGGER.error("Input queue full; restarting without acknowledging pending messages")
            self.stop.set()

    def acknowledge(self, deliveries):
        with self.generation_lock:
            for delivery in deliveries:
                if delivery.generation == self.generation and self.connected.is_set():
                    self.client.ack(delivery.mid, delivery.qos)

    def get_batch(self):
        try:
            batch = [self.messages.get(timeout=0.5)]
        except queue.Empty:
            return []
        deadline = time.monotonic() + self.flush_seconds
        while len(batch) < self.batch_size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                batch.append(self.messages.get(timeout=remaining))
            except queue.Empty:
                break
        return batch

    def run(self):
        connection = None
        batch = []
        properties = Properties(PacketTypes.CONNECT)
        properties.SessionExpiryInterval = 86400
        properties.ReceiveMaximum = 1000
        self.client.connect_async(
            os.getenv("MQTT_HOST", "mosquitto"),
            int(os.getenv("MQTT_PORT", "1883")), keepalive=60,
            clean_start=False, properties=properties,
        )
        self.client.loop_start()
        try:
            while not self.stop.is_set():
                try:
                    if connection is None:
                        connection = database_connection()
                        store = BatchStore(connection, self.validator)
                        LOGGER.info("DATABASE_READY batch_size=%s", self.batch_size)
                    if not batch:
                        batch = self.get_batch()
                    if batch:
                        result = store.save_with_isolation(batch)
                        self.acknowledge(batch)
                        LOGGER.info("BATCH_COMMITTED inserted=%s duplicates=%s dlq=%s", *result)
                        batch = []
                    else:
                        connection.execute("SELECT 1")
                    if self.connected.is_set():
                        store.publish_dlq(self.client)
                    if self.subscribed.is_set():
                        READY_FILE.touch()
                except psycopg.Error as exc:
                    READY_FILE.unlink(missing_ok=True)
                    LOGGER.warning("Database operation will be retried without MQTT ACK: %s", exc)
                    if connection is not None:
                        connection.close()
                    connection = None
                    self.stop.wait(2)
        finally:
            READY_FILE.unlink(missing_ok=True)
            self.client.disconnect()
            self.client.loop_stop()
            if connection is not None:
                connection.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    worker = IngestionWorker()
    signal.signal(signal.SIGTERM, lambda *_: worker.stop.set())
    signal.signal(signal.SIGINT, lambda *_: worker.stop.set())
    worker.run()
