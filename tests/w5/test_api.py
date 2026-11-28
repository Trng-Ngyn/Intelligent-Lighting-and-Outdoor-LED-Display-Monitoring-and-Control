from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from ingestion.publish_demo import encode, topic_for
from ingestion.worker import Delivery
from test_ingestion import store, native


@pytest.fixture()
def client(db, monkeypatch):
    from staging_api import main
    monkeypatch.setattr(main.dispatcher, "start", lambda: None)
    monkeypatch.setattr(main.dispatcher, "stop", lambda: None)
    with TestClient(main.app) as c:
        yield c


def login(client):
    result = client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "test-only-operator-password-for-test-session"})
    assert result.status_code == 200, result.text
    return result.json()


def test_auth_refresh_rotation_logout_and_scope(client, db):
    assert client.get("/api/v1/console/assets").status_code in (401, 403)
    tokens = login(client)
    client.headers["Authorization"] = "Bearer " + tokens["access_token"]
    assert len(client.get("/api/v1/console/assets").json()["assets"]) == 3
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != tokens["refresh_token"]
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/logout", json={"refresh_token": rotated.json()["refresh_token"]}).status_code == 204
    assert client.get("/api/v1/console/assets").status_code == 401


def test_commands_are_idempotent_and_no_fake_success(client, db):
    tokens = login(client)
    client.headers["Authorization"] = "Bearer " + tokens["access_token"]
    assets = client.get("/api/v1/console/assets").json()["assets"]
    ids = [a["asset_id"] for a in assets if a["kind"] == "lighting"]
    body = {"asset_ids": ids, "brightness": 35}
    headers = {"Idempotency-Key": str(uuid4())}
    result = client.post("/api/v1/console/dimming", json=body, headers=headers)
    assert result.status_code == 202, result.text
    assert result.json()["state"] == "queued"
    assert client.post("/api/v1/console/dimming", json=body, headers=headers).json() == result.json()
    assert client.post("/api/v1/console/dimming", json={**body, "brightness": 36}, headers=headers).status_code == 409
    state = client.get("/api/v1/console/commands/" + result.json()["batch_id"]).json()["commands"]
    assert len(state) == 2 and all(c["verified_at"] is None for c in state)
    assert client.post("/api/v1/console/dimming", json={**body, "brightness": 101}, headers={"Idempotency-Key": str(uuid4())}).status_code == 422
    assert client.post("/api/v1/console/dimming", json={"asset_ids": [str(uuid4())], "brightness": 50}, headers=headers).status_code in (404, 409)
    db.execute("DELETE FROM lighting.users_roles")
    assert client.get("/api/v1/console/assets").json()["assets"] == []


def test_real_database_history_and_status(client, db):
    s = store(db)
    p = native()
    p["metrics"]["dimming_pct"] = {"value": 42, "unit": "%", "quality": "measured"}
    assert s.save_batch([Delivery(topic_for("lighting"), encode(p))])[0] == 1
    client.headers["Authorization"] = "Bearer " + login(client)["access_token"]
    data = client.get("/api/v1/console/assets").json()["assets"]
    light = next(a for a in data if a["asset_code"] == "W5_LIGHT_001")
    assert light["status"] == "online" and light["reported_brightness"] == 42
    hist = client.get("/api/v1/console/assets/" + light["asset_id"] + "/history").json()
    assert hist["power"][0]["value"] > 0
    assert hist["energy"][0]["value"] == pytest.approx(.00001)
    assert hist["energy_unit"] == "kWh"


def test_readback_verification_and_expiry(client, db):
    from staging_api.main import dispatcher
    client.headers["Authorization"] = "Bearer " + login(client)["access_token"]
    asset = "44444444-4444-4444-8444-444444444444"
    r = client.post("/api/v1/console/dimming", json={"asset_ids": [asset], "brightness": 70},
                    headers={"Idempotency-Key": str(uuid4())})
    cid = r.json()["command_ids"][0]
    db.execute("UPDATE lighting.staging_commands SET state='sent',sent_at=clock_timestamp()-interval '1 second' WHERE command_id=%s", (cid,))
    s = store(db)
    p = native()
    p["metrics"]["dimming_pct"] = {"value": 70, "unit": "%", "quality": "estimated"}
    s.save_batch([Delivery(topic_for("lighting"), encode(p))])
    dispatcher.tick()
    assert db.execute("SELECT state FROM lighting.staging_commands").fetchone()[0] == "sent"
    p = native(2)
    p["metrics"]["dimming_pct"] = {"value": 70, "unit": "%", "quality": "measured"}
    s.save_batch([Delivery(topic_for("lighting"), encode(p))])
    dispatcher.tick()
    assert db.execute("SELECT state FROM lighting.staging_commands").fetchone()[0] == "verified"


def test_group_results_do_not_block_publish_transaction(client, db, monkeypatch):
    """An immediate device reply must not lock the network thread on the outbox."""
    import json
    from types import SimpleNamespace
    from iot_protocol.headers import build_headers
    from iot_protocol.signing import derive_device_key
    from staging_api.dispatcher import Dispatcher
    from staging_api.db import secret

    client.headers["Authorization"] = "Bearer " + login(client)["access_token"]
    ids = [a["asset_id"] for a in client.get("/api/v1/console/assets").json()["assets"]
           if a["kind"] == "lighting"]
    response = client.post("/api/v1/console/dimming", json={"asset_ids": ids, "brightness": 65},
                           headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 202
    # A regression that accesses the locked row from the callback fails quickly
    # instead of leaving the test waiting on a real database lock indefinitely.
    monkeypatch.setenv("PGOPTIONS", "-c lock_timeout=200ms")
    dispatcher = Dispatcher()

    def publish(topic, payload, **kwargs):
        result_topic = topic + "/result"
        body = json.dumps({"command_id": json.loads(payload)["command_id"], "status": "EXECUTED"})
        parts = topic.split("/")
        key = derive_device_key(secret("SIGNING_SECRET"), parts[2], parts[3], parts[4])
        headers, _, _ = build_headers(key, result_topic, body,
                                     correlation_id=json.loads(payload)["command_id"])
        dispatcher.on_message(None, None, SimpleNamespace(
            topic=result_topic, payload=body.encode(), retain=False,
            properties=SimpleNamespace(UserProperty=list(headers.items()))))
        return SimpleNamespace(wait_for_publish=lambda timeout: None, is_published=lambda: True)

    dispatcher.client = SimpleNamespace(publish=publish)
    dispatcher.connected.set()
    dispatcher.tick()
    dispatcher.connected.clear()
    dispatcher.tick()
    rows = db.execute("SELECT state,sent_at,ack_at FROM lighting.staging_commands").fetchall()
    assert len(rows) == 2
    assert all(state == "executed" and sent and ack for state, sent, ack in rows)
