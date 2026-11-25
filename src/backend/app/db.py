import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from app.core.config import settings

_engine: Engine | None = None

def get_engine() -> Engine:
    global _engine
    if not settings.database_url:
        raise RuntimeError("Chưa cấu hình DATABASE_URL trong file .env")
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def fetch_all_assets(tenant_id: str | None = None, site_id: str | None = None):
    query = """
        SELECT tenant_id, site_id, asset_id, asset_code, device_id, kind, parent_id,
               location_id, circuit_id, model, firmware, owner_ref,
               energy_mode, heartbeat_s, commissioned_at, retired_at
        FROM lighting.assets
        WHERE retired_at IS NULL
          AND (CAST(:tenant_id AS uuid) IS NULL OR tenant_id = CAST(:tenant_id AS uuid))
          AND (CAST(:site_id AS uuid) IS NULL OR site_id = CAST(:site_id AS uuid))
        ORDER BY commissioned_at DESC NULLS LAST
    """
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(query),
            {"tenant_id": tenant_id, "site_id": site_id}
        )
        return [dict(row._mapping) for row in rows]


def fetch_telemetry_history(asset_id: str, start_time, end_time, limit: int = 500):
    query = """
        SELECT asset_id, source_time, received_time, power_w,
               energy_interval_wh, energy_register_wh, voltage_v,
               current_a, power_factor, illuminance_lx, temperature_c,
               metric_quality, details
        FROM lighting.telemetry_lighting
        WHERE asset_id = CAST(:asset_id AS uuid)
          AND source_time >= :start_time
          AND source_time <= :end_time
        ORDER BY source_time DESC
        LIMIT :limit
    """
    with get_engine().connect() as conn:
        rows = conn.execute(text(query), {
            "asset_id": asset_id, "start_time": start_time,
            "end_time": end_time, "limit": limit
        })
        return [dict(row._mapping) for row in rows]


def insert_telemetry_lighting(
    asset_code: str,
    data: dict,
    correlation_id: str,
    topic: str,
    ts_ms: int,
):
    """L?u m?t b?n tin telemetry lighting ?? ???c Cloud x?c th?c."""
    metrics = data.get("metrics") or {}

    source_epoch = data.get("source_time")
    if source_epoch is None:
        source_epoch = ts_ms / 1000

    source_time = datetime.fromtimestamp(float(source_epoch), tz=timezone.utc)
    received_time = datetime.now(timezone.utc)

    with get_engine().begin() as conn:
        asset = conn.execute(
            text("""
                SELECT tenant_id, site_id, asset_id, device_id, kind, firmware
                FROM lighting.assets
                WHERE asset_code = :asset_code
                  AND retired_at IS NULL
                ORDER BY commissioned_at DESC NULLS LAST
                LIMIT 1
            """),
            {"asset_code": asset_code},
        ).mappings().first()

        if asset is None:
            raise ValueError(f"Kh?ng t?m th?y asset_code={asset_code} trong Database")

        quality = str(data.get("quality") or "UNKNOWN")
        metric_quality = {
            key: quality for key in (
                "power_w", "voltage_v", "current_a",
                "power_factor", "temperature_c", "ambient_lux"
            )
            if metrics.get(key) is not None
        }

        details = {
            "energy_wh": metrics.get("energy_wh"),
            "brightness_pct": data.get("brightness_pct"),
            "relay_state": data.get("relay_state"),
            "quality": quality,
            "original_message_id": data.get("message_id"),
            "correlation_id": correlation_id,
            "topic": topic,
            "ts_ms": ts_ms,
        }

        result = conn.execute(
            text("""
                INSERT INTO lighting.telemetry_lighting (
                    tenant_id, site_id, asset_id, device_id, kind,
                    message_id, schema_version, source_time, received_time,
                    sequence, firmware, clock_quality,
                    power_w, voltage_v, current_a, power_factor,
                    illuminance_lx, temperature_c,
                    metric_quality, details
                )
                VALUES (
                    :tenant_id, :site_id, :asset_id, :device_id, :kind,
                    CAST(:message_id AS uuid), 1, :source_time, :received_time,
                    :sequence, :firmware, 'uncertain',
                    :power_w, :voltage_v, :current_a, :power_factor,
                    :illuminance_lx, :temperature_c,
                    CAST(:metric_quality AS jsonb), CAST(:details AS jsonb)
                )
                ON CONFLICT DO NOTHING
            """),
            {
                "tenant_id": asset["tenant_id"],
                "site_id": asset["site_id"],
                "asset_id": asset["asset_id"],
                "device_id": asset["device_id"],
                "kind": asset["kind"],
                "message_id": correlation_id,
                "source_time": source_time,
                "received_time": received_time,
                "sequence": int(data.get("sequence", 0)),
                "firmware": asset["firmware"],
                "power_w": metrics.get("power_w"),
                "voltage_v": metrics.get("voltage_v"),
                "current_a": metrics.get("current_a"),
                "power_factor": metrics.get("power_factor"),
                "illuminance_lx": metrics.get("ambient_lux"),
                "temperature_c": metrics.get("temperature_c"),
                "metric_quality": json.dumps(metric_quality),
                "details": json.dumps(details),
            },
        )

        return result.rowcount > 0


def fetch_latest_telemetry(asset_id: str):
    """L?y b?n ghi telemetry m?i nh?t c?a m?t thi?t b? chi?u s?ng."""
    engine = get_engine()

    query = text("""
        SELECT
            asset_id,
            source_time,
            received_time,
            sequence,
            power_w,
            voltage_v,
            current_a,
            power_factor,
            illuminance_lx,
            temperature_c,
            details
        FROM lighting.telemetry_lighting
        WHERE asset_id = CAST(:asset_id AS uuid)
        ORDER BY source_time DESC
        LIMIT 1
    """)

    with engine.connect() as conn:
        row = conn.execute(query, {"asset_id": asset_id}).mappings().first()

    return dict(row) if row else None


def fetch_telemetry_summary(asset_id: str, start_time, end_time):
    """T?ng h?p c?c ch? s? telemetry trong kho?ng th?i gian."""
    engine = get_engine()

    query = text("""
        SELECT
            COUNT(*) AS total_records,
            AVG(power_w) AS average_power_w,
            MAX(power_w) AS maximum_power_w,
            AVG(temperature_c) AS average_temperature_c,
            AVG(voltage_v) AS average_voltage_v
        FROM lighting.telemetry_lighting
        WHERE asset_id = CAST(:asset_id AS uuid)
          AND source_time >= :start_time
          AND source_time <= :end_time
    """)

    with engine.connect() as conn:
        row = conn.execute(
            query,
            {
                "asset_id": asset_id,
                "start_time": start_time,
                "end_time": end_time,
            },
        ).mappings().first()

    return dict(row) if row else None
def get_idempotency_record(idempotency_key: str, user_id: str):
    """Retrieve an idempotency record for a user."""
    from sqlalchemy import text

    engine = get_engine()
    query = text("""
        SELECT idempotency_key, user_id, request_hash, response_json
        FROM lighting.idempotency_keys
        WHERE idempotency_key = :key AND user_id = :user_id
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(
            query,
            {"key": idempotency_key, "user_id": user_id},
        ).mappings().first()
    return dict(row) if row else None


def save_idempotency_record(
    idempotency_key: str,
    user_id: str,
    request_hash: str,
    response_json: dict,
):
    """Save an idempotency result without overwriting an existing record."""
    import json
    from sqlalchemy import text

    engine = get_engine()
    query = text("""
        INSERT INTO lighting.idempotency_keys
            (idempotency_key, user_id, request_hash, response_json)
        VALUES
            (:key, :user_id, :request_hash, CAST(:response_json AS jsonb))
        ON CONFLICT (idempotency_key) DO NOTHING
    """)
    with engine.begin() as conn:
        result = conn.execute(
            query,
            {
                "key": idempotency_key,
                "user_id": user_id,
                "request_hash": request_hash,
                "response_json": json.dumps(response_json),
            },
        )
    return result.rowcount == 1
def claim_idempotency_key(
    idempotency_key: str,
    user_id: str,
    request_hash: str,
):
    """Atomically reserve an idempotency key before processing."""
    from sqlalchemy import text

    engine = get_engine()
    query = text("""
        INSERT INTO lighting.idempotency_keys
            (idempotency_key, user_id, request_hash)
        VALUES
            (:key, :user_id, :request_hash)
        ON CONFLICT (idempotency_key) DO NOTHING
        RETURNING idempotency_key
    """)

    with engine.begin() as conn:
        row = conn.execute(
            query,
            {
                "key": idempotency_key,
                "user_id": user_id,
                "request_hash": request_hash,
            },
        ).first()

    return row is not None
def update_idempotency_response(
    idempotency_key: str,
    user_id: str,
    request_hash: str,
    response_json: dict,
):
    """Store the completed response for a reserved key."""
    import json
    from sqlalchemy import text

    query = text("""
        UPDATE lighting.idempotency_keys
        SET response_json = CAST(:response_json AS jsonb)
        WHERE idempotency_key = :key
          AND user_id = :user_id
          AND request_hash = :request_hash
    """)

    with get_engine().begin() as conn:
        result = conn.execute(query, {
            "key": idempotency_key,
            "user_id": user_id,
            "request_hash": request_hash,
            "response_json": json.dumps(response_json),
        })

    return result.rowcount == 1


def release_idempotency_key(
    idempotency_key: str,
    user_id: str,
    request_hash: str,
):
    """Release a reservation when command publishing fails."""
    from sqlalchemy import text

    query = text("""
        DELETE FROM lighting.idempotency_keys
        WHERE idempotency_key = :key
          AND user_id = :user_id
          AND request_hash = :request_hash
          AND response_json IS NULL
    """)

    with get_engine().begin() as conn:
        result = conn.execute(query, {
            "key": idempotency_key,
            "user_id": user_id,
            "request_hash": request_hash,
        })

    return result.rowcount == 1

def create_auth_session(
    session_id: str,
    user_id: str,
    roles: list[str],
    refresh_token_hash: str,
    expires_at,
):
    import json

    query = text("""
        INSERT INTO lighting.auth_sessions
            (session_id, user_id, roles, refresh_token_hash, expires_at)
        VALUES
            (CAST(:session_id AS uuid), :user_id,
             CAST(:roles AS jsonb), :refresh_token_hash, :expires_at)
    """)

    with get_engine().begin() as conn:
        conn.execute(query, {
            "session_id": session_id,
            "user_id": user_id,
            "roles": json.dumps(roles),
            "refresh_token_hash": refresh_token_hash,
            "expires_at": expires_at,
        })


def get_auth_session(session_id: str):
    query = text("""
        SELECT session_id, user_id, roles, refresh_token_hash,
               expires_at, revoked_at
        FROM lighting.auth_sessions
        WHERE session_id = CAST(:session_id AS uuid)
    """)

    with get_engine().connect() as conn:
        row = conn.execute(
            query, {"session_id": session_id}
        ).mappings().first()

    return dict(row) if row else None


def rotate_auth_session(
    session_id: str,
    old_token_hash: str,
    new_token_hash: str,
    expires_at,
):
    query = text("""
        UPDATE lighting.auth_sessions
        SET refresh_token_hash = :new_hash,
            expires_at = :expires_at,
            updated_at = NOW()
        WHERE session_id = CAST(:session_id AS uuid)
          AND refresh_token_hash = :old_hash
          AND revoked_at IS NULL
          AND expires_at > NOW()
    """)

    with get_engine().begin() as conn:
        result = conn.execute(query, {
            "session_id": session_id,
            "old_hash": old_token_hash,
            "new_hash": new_token_hash,
            "expires_at": expires_at,
        })

    return result.rowcount == 1


def revoke_auth_session(session_id: str):
    query = text("""
        UPDATE lighting.auth_sessions
        SET revoked_at = NOW(),
            updated_at = NOW()
        WHERE session_id = CAST(:session_id AS uuid)
          AND revoked_at IS NULL
    """)

    with get_engine().begin() as conn:
        result = conn.execute(query, {
            "session_id": session_id,
        })

    return result.rowcount == 1
