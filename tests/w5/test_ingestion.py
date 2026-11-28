import copy
from datetime import datetime, timedelta, timezone
import json
import time
from uuid import uuid4
import pytest
from ingestion.adapters import TopicAdapter
from ingestion.worker import BatchStore, Delivery, PayloadValidator, SCHEMA_DIR
from ingestion.publish_demo import packet, encode, topic_for
from ingestion.fixtures import demo_registry


def native(seq=1):
    return packet("lighting", uuid4(), seq, datetime.now(timezone.utc), .01, 5)


def store(db, enforce=True):
    return BatchStore(db, PayloadValidator(SCHEMA_DIR, TopicAdapter(enforce=enforce)))


def test_valid_invalid_dedup_and_conflicting_replay(db):
    s = store(db)
    p = native()
    d = Delivery(topic_for("lighting"), encode(p))
    assert s.save_batch([d, Delivery(d.topic, b"invalid-json")]) == (1, 0, 1)
    assert s.save_batch([d]) == (0, 1, 0)
    p["metrics"]["power_w"]["value"] = 999
    assert s.save_batch([Delivery(d.topic, encode(p))]) == (0, 0, 1)
    assert db.execute("SELECT count(*) FROM lighting.telemetry_lighting").fetchone()[0] == 1
    assert db.execute("SELECT count(*) FROM lighting.ingestion_dlq").fetchone()[0] == 2


def test_schema_bounds_identity_and_invalid_quality(db):
    s = store(db)
    p = native()
    p["metrics"]["power_w"]["value"] = -1
    assert s.save_batch([Delivery(topic_for("lighting"), encode(p))])[2] == 1
    p = native()
    p["asset_id"] = str(uuid4())
    assert s.save_batch([Delivery(topic_for("lighting"), encode(p))])[2] == 1
    assert s.save_batch([Delivery(topic_for("lighting"), b"x" * 16385)])[2] == 1


def test_transaction_failure_preserves_valid_rows(db):
    s = store(db, enforce=False)
    good = native()
    bad = native(2)
    # With registry enforcement disabled, the DB foreign key still protects the
    # approved schema. Test row isolation rather than duplicating schema checks.
    bad["asset_id"] = str(uuid4())
    result = s.save_with_isolation([Delivery(topic_for("lighting"), encode(good)),
                                   Delivery("telemetry/v1/unknown/light/unknown", encode(bad))])
    assert result == (1, 0, 1)


def test_legacy_normalization_and_route_identity(db):
    s = store(db)
    # Reuse registered binding, explicitly trust an external NTP assertion.
    raw = {"asset_id": "W5_LIGHT_001", "message_id": "MSG_boot1_1", "sequence": 1,
           "source_time": time.time(), "firmware": "v1.0.0", "quality": "GOOD",
           "brightness_pct": 45, "metrics": {"power_w": 20, "energy_wh": 100, "temperature_c": 30}}
    topic = "pccom/lighting/W5_DEMO/W5_LIGHT_001/telemetry"
    assert s.save_batch([Delivery(topic, encode(raw))]) == (1, 0, 0)
    row = db.execute("SELECT clock_quality,energy_register_wh,energy_interval_wh,details FROM lighting.telemetry_lighting").fetchone()
    assert row[0] == "uncertain" and row[1] == 100 and row[2] is None
    assert row[3]["metrics"]["dimming_pct"]["value"] == 45
    assert s.save_batch([Delivery(topic, encode(raw))]) == (0, 1, 0)


def test_counter_late_arrival_reset_and_epoch_change(db):
    s = store(db)
    epoch = str(uuid4())
    base = datetime.now(timezone.utc) - timedelta(minutes=5)
    messages = []
    for seq, seconds, counter in [(1, 0, 100), (3, 20, 106), (2, 10, 102), (4, 30, 1), (5, 40, 4)]:
        p = native(seq)
        p["source_time"] = (base + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")
        p.pop("energy_interval_start")
        p["metrics"].pop("energy_interval_wh")
        p["metrics"]["energy_register_wh"] = {"value": counter, "unit": "Wh", "quality": "measured"}
        p["counter_epoch"] = epoch
        messages.append(Delivery(topic_for("lighting"), encode(p)))
    for d in messages:
        assert s.save_batch([d])[0] == 1
    rows = db.execute("SELECT energy_interval_wh FROM lighting.telemetry_lighting ORDER BY source_time").fetchall()
    assert [None if x[0] is None else float(x[0]) for x in rows] == [None, 2, 4, None, 3]
    assert db.execute("SELECT sum(energy_interval_wh) FROM lighting.telemetry_lighting").fetchone()[0] == 9


def test_registry_rejects_duplicate_and_demo_requires_opt_in(db):
    from ingestion.registry import register_assets, validate_registry
    doc = demo_registry()
    with pytest.raises(ValueError, match="allow-demo"):
        register_assets(db, doc)
    doc["assets"].append(copy.deepcopy(doc["assets"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_registry(doc)


def test_northbound_identity_mismatch_is_dead_lettered(db):
    s = store(db)
    p = {"source_site_id": "W5_DEMO", "device_type": "light", "device_id": "W5_LIGHT_001",
         "data": {"message_id": "a", "sequence": 1, "source_time": time.time(), "metrics": {"power_w": 12}}}
    assert s.save_batch([Delivery("pccom/v1/wrong/s01/gw-001/telemetry", json.dumps(p).encode())])[2] == 1


def test_batch_insert_throughput_postgres_only(db, capsys):
    s = store(db)
    records = [Delivery(topic_for("lighting"), encode(native(seq))) for seq in range(10000)]
    start = time.monotonic()
    for offset in range(0, len(records), 500):
        assert s.save_batch(records[offset:offset + 500])[0] == 500
    elapsed = time.monotonic() - start
    count = db.execute("SELECT count(*) FROM lighting.telemetry_lighting").fetchone()[0]
    result = {"environment": "native PostgreSQL16, direct BatchStore (not MQTT/Timescale)",
              "count": count, "seconds": round(elapsed, 3), "records_per_second": round(count / elapsed, 2)}
    print(json.dumps(result))
    assert count == 10000
