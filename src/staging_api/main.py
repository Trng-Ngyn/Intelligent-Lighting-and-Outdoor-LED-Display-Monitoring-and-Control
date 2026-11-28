"""Staging composition of SCRUM-30 authentication and registry-scoped operations.

The DE worker is the sole telemetry writer. HTTP 202 is acceptance, never proof
that a physical luminaire has changed.
"""

import hashlib
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from .db import connection, scope_clause, secret


def configure_auth():
    for name in ("JWT_SECRET", "DEV_PASSWORD"):
        value = secret(name)
        if len(value) < 24:
            raise RuntimeError(name + " must contain at least 24 generated characters")
        os.environ[name] = value
    os.environ["DATABASE_URL"] = URL.create(
        "postgresql+psycopg", username=os.getenv("PGUSER", "pccom_api"),
        password=secret("PGPASSWORD"), host=os.getenv("PGHOST", "timescaledb"),
        port=int(os.getenv("PGPORT", "5432")),
        database=os.getenv("PGDATABASE", "pccom_staging"),
    ).render_as_string(hide_password=False)


configure_auth()
from app.core.security import current_user, require_roles  # noqa: E402
from app.routers import auth  # noqa: E402
from .dispatcher import Dispatcher  # noqa: E402

dispatcher = Dispatcher()


@asynccontextmanager
async def lifespan(app):
    dispatcher.start()
    yield
    dispatcher.stop()


app = FastAPI(title="PCCOM Staging Console", version="1.0.0", lifespan=lifespan)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["SCRUM-30 authentication"])


@app.get("/health")
def health():
    with connection() as conn:
        conn.execute("SELECT 1")
    return {"database": "ok", "mqtt": dispatcher.connected.is_set()}


@app.get("/metrics", include_in_schema=False)
def metrics():
    with connection() as conn:
        total, pending = conn.execute("""
            SELECT count(*), count(*) FILTER (WHERE state IN ('queued','sent','executed'))
            FROM lighting.staging_commands
        """).fetchone()
        receipts = conn.execute("SELECT count(*) FROM lighting.ingestion_receipts").fetchone()[0]
        dlq = conn.execute("SELECT count(*) FROM lighting.ingestion_dlq").fetchone()[0]
    body = (
        "# TYPE pccom_mqtt_connected gauge\npccom_mqtt_connected "
        + str(int(dispatcher.connected.is_set())) + "\n"
        + "# TYPE pccom_commands_total gauge\npccom_commands_total " + str(total) + "\n"
        + "# TYPE pccom_commands_pending gauge\npccom_commands_pending " + str(pending) + "\n"
        + "# TYPE pccom_receipts_total gauge\npccom_receipts_total " + str(receipts) + "\n"
        + "# TYPE pccom_dlq_total gauge\npccom_dlq_total " + str(dlq) + "\n"
    )
    return Response(body, media_type="text/plain; version=0.0.4")


def metric(details, name):
    entry = (details or {}).get("metrics", {}).get(name, {})
    return entry.get("value") if entry.get("quality") in ("measured", "estimated") else None


def asset_status(row, now):
    received = row.get("received_time")
    source = row.get("source_time")
    stale = max(30, row["heartbeat_s"] * 3)
    if received is None or source is None or (now - received).total_seconds() > stale:
        return "offline"
    if (now - source).total_seconds() > stale or (source - now).total_seconds() > 60:
        return "offline"
    details = row.get("details", {})
    faults = ("driver_fault_code", "cabinet_fault_code", "module_fault_code", "power_fault_code")
    if any(metric(details, name) not in (None, 0, "", "OK", "NONE") for name in faults):
        return "error"
    return "online"


def assets_for(user_id):
    with connection(dicts=True) as conn:
        rows = conn.execute("""
            SELECT a.tenant_id,a.site_id,a.asset_id,a.asset_code,a.kind,a.heartbeat_s,
                   a.location_id,coalesce(a.circuit_id,a.site_id) AS group_id,
                   coalesce(c.code,b.field_site) AS group_name,l.latitude,l.longitude,
                   b.is_demo,b.command_mode,t.source_time,t.received_time,t.power_w,
                   t.clock_quality,t.metric_quality,t.details
            FROM lighting.assets a
            JOIN lighting.ingestion_bindings b USING (tenant_id,site_id,asset_id)
            LEFT JOIN lighting.locations l USING (tenant_id,site_id,location_id)
            LEFT JOIN lighting.circuits c ON c.tenant_id=a.tenant_id AND c.site_id=a.site_id AND c.circuit_id=a.circuit_id
            LEFT JOIN LATERAL (
                SELECT source_time,received_time,power_w,clock_quality,metric_quality,details
                FROM (
                  (SELECT source_time,received_time,power_w,clock_quality,metric_quality,details
                   FROM lighting.telemetry_lighting x
                   WHERE x.tenant_id=a.tenant_id AND x.site_id=a.site_id AND x.asset_id=a.asset_id
                   ORDER BY source_time DESC LIMIT 1)
                  UNION ALL
                  (SELECT source_time,received_time,power_w,clock_quality,metric_quality,details
                   FROM lighting.telemetry_led x
                   WHERE x.tenant_id=a.tenant_id AND x.site_id=a.site_id AND x.asset_id=a.asset_id
                   ORDER BY source_time DESC LIMIT 1)
                ) latest ORDER BY source_time DESC LIMIT 1
            ) t ON true
            WHERE a.retired_at IS NULL AND """ + scope_clause() + """
            ORDER BY l.name,a.asset_code
        """, (user_id,)).fetchall()
    now = datetime.now(timezone.utc)
    result = []
    for row in rows:
        row["status"] = asset_status(row, now)
        row["reported_brightness"] = metric(row["details"], "dimming_pct" if row["kind"] == "lighting" else "brightness_pct")
        row["power_w"] = row["power_w"] if (row["metric_quality"] or {}).get("power_w") in ("measured", "estimated") else None
        row.pop("details")
        row.pop("metric_quality")
        result.append(row)
    return result


@app.get("/api/v1/console/assets")
def assets(user=Depends(current_user)):
    return {"assets": assets_for(user["user_id"]), "server_time": datetime.now(timezone.utc)}


def authorized_asset(conn, asset_id, user_id):
    row = conn.execute(
        "SELECT a.* FROM lighting.assets a WHERE a.asset_id=%s AND a.retired_at IS NULL AND "
        + scope_clause(), (asset_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Thiết bị không nằm trong phạm vi được cấp quyền")
    return row


@app.get("/api/v1/console/assets/{asset_id}/history")
def history(asset_id: UUID, hours: int = Query(24, ge=1, le=168), user=Depends(current_user)):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    with connection(dicts=True) as conn:
        a = authorized_asset(conn, asset_id, user["user_id"])
        # Identifier is selected from a fixed allowlist, never interpolated input.
        kind = "lighting" if a["kind"] == "lighting" else "led"
        params = (a["tenant_id"], a["site_id"], asset_id, start, end)
        power = conn.execute("""
            SELECT time_bucket('5 minutes',source_time) AS time,avg(power_w) AS value
            FROM lighting.telemetry_""" + kind + """
            WHERE tenant_id=%s AND site_id=%s AND asset_id=%s AND source_time BETWEEN %s AND %s
              AND clock_quality='synced' AND metric_quality->>'power_w' IN ('measured','estimated')
            GROUP BY 1 ORDER BY 1
        """, params).fetchall()
        energy = conn.execute("""
            SELECT bucket AS time,energy_wh/1000.0 AS value
            FROM lighting.energy_""" + kind + """_hourly
            WHERE tenant_id=%s AND site_id=%s AND asset_id=%s AND bucket BETWEEN %s AND %s
            ORDER BY 1
        """, params).fetchall()
    return {"power": power, "energy": energy, "power_unit": "W", "energy_unit": "kWh",
            "aggregation": "closed hourly buckets; scheduled refresh every 15 minutes",
            "start": start, "end": end}


class DimRequest(BaseModel):
    asset_ids: list[UUID] = Field(min_length=1, max_length=200)
    brightness: int = Field(ge=0, le=100, strict=True)


@app.post("/api/v1/console/dimming", status_code=202)
def dim(body: DimRequest, idempotency_key: str = Header(min_length=8, max_length=100),
        user=Depends(require_roles("OPERATOR"))):
    asset_ids = sorted(set(body.asset_ids), key=str)
    digest = hashlib.sha256(json.dumps([list(map(str, asset_ids)), body.brightness]).encode()).hexdigest()
    with connection(dicts=True) as conn, conn.transaction():
        # Serializes same user/key across API workers; transaction rollback releases it.
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (user["user_id"] + idempotency_key,))
        saved = conn.execute("""
            SELECT request_hash,response FROM lighting.staging_requests
            WHERE user_id=%s AND idempotency_key=%s
        """, (user["user_id"], idempotency_key)).fetchone()
        if saved:
            if saved["request_hash"] != digest:
                raise HTTPException(409, "Idempotency-Key đã dùng với nội dung khác")
            return saved["response"]
        for asset_id in asset_ids:
            target = authorized_asset(conn, asset_id, user["user_id"])
            if target["kind"] != "lighting":
                raise HTTPException(422, "Dimming chỉ áp dụng cho cột đèn")
        batch_id = uuid4()
        command_ids = []
        for asset_id in asset_ids:
            cid = uuid4()
            command_ids.append(str(cid))
            conn.execute("""
                INSERT INTO lighting.staging_commands
                  (command_id,batch_id,tenant_id,site_id,asset_id,user_id,brightness,expires_at)
                SELECT %s,%s,tenant_id,site_id,asset_id,%s,%s,clock_timestamp()+interval '60 seconds'
                FROM lighting.assets WHERE asset_id=%s AND """ + scope_clause("lighting.assets"),
                (cid, batch_id, user["user_id"], body.brightness, asset_id, user["user_id"]),
            )
        response = {"batch_id": str(batch_id), "command_ids": command_ids, "state": "queued"}
        conn.execute("INSERT INTO lighting.staging_requests VALUES (%s,%s,%s,%s,DEFAULT)",
                     (user["user_id"], idempotency_key, digest, Jsonb(response)))
        conn.execute("INSERT INTO lighting.staging_audit (user_id,action,batch_id,details) VALUES (%s,'DIM',%s,%s)",
                     (user["user_id"], batch_id, Jsonb({"assets": list(map(str, asset_ids)), "brightness": body.brightness})))
    return response


@app.get("/api/v1/console/commands/{batch_id}")
def commands(batch_id: UUID, user=Depends(current_user)):
    with connection(dicts=True) as conn:
        rows = conn.execute("""
            SELECT c.command_id,c.asset_id,c.brightness,c.state,c.created_at,c.sent_at,c.ack_at,
                   c.verified_at,c.reason,b.is_demo
            FROM lighting.staging_commands c
            JOIN lighting.assets a USING (tenant_id,site_id,asset_id)
            JOIN lighting.ingestion_bindings b USING (tenant_id,site_id,asset_id)
            WHERE batch_id=%s AND """ + scope_clause(), (batch_id, user["user_id"])).fetchall()
    if not rows:
        raise HTTPException(404, "Không tìm thấy nhóm lệnh")
    return {"commands": rows}
