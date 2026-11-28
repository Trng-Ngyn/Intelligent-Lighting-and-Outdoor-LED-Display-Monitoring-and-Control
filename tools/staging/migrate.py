"""Run G1 once, then additive migrations and explicit device registration."""

import json
import os
from pathlib import Path
from uuid import UUID

from psycopg import sql
from ingestion.registry import register_assets
from staging_api.db import connection

ROOT = Path(__file__).resolve().parents[2]


def migrate():
    registry = json.loads(Path(os.getenv("STAGING_REGISTRY_FILE", "/run/config/registry.json")).read_text())
    secret_directory = Path(os.getenv("STAGING_SECRET_DIR", "/run/secrets"))
    with connection() as conn:
        conn.execute("SELECT pg_advisory_lock(260029)")
        try:
            if conn.execute("SELECT to_regclass('lighting.assets')").fetchone()[0] is None:
                conn.execute((ROOT / "docs/data_contracts/001_init.sql").read_text(encoding="utf-8-sig"))
            tables = conn.execute("""
                SELECT hypertable_name FROM timescaledb_information.hypertables
                WHERE hypertable_schema='lighting'
            """).fetchall()
            if {r[0] for r in tables} != {"telemetry_lighting", "telemetry_led"}:
                raise RuntimeError("Existing database is not the approved G1 schema; migrate it explicitly")
            conn.execute((ROOT / "sql/w5_ingestion.sql").read_text())
            for path in sorted((ROOT / "database/staging").glob("*.sql")):
                conn.execute(path.read_text())
            register_assets(conn, registry, allow_demo=os.getenv("STAGING_DEMO") == "1")
            user_id = UUID(os.environ["DEV_USER_ID"])
            with conn.transaction():
                for a in registry["assets"]:
                    conn.execute("""
                        INSERT INTO lighting.users_roles VALUES (%s,%s,%s,'ADMIN') ON CONFLICT DO NOTHING
                    """, (a["tenant_id"], a["site_id"], user_id))
                for role, filename in (("pccom_api", "db_api"), ("pccom_ingestion", "db_ingestion")):
                    password = (secret_directory / filename).read_text().strip()
                    if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                        conn.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role)))
                    conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
                    conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(os.environ["PGDATABASE"]), sql.Identifier(role)))
                    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA lighting TO {}").format(sql.Identifier(role)))
                conn.execute("GRANT SELECT ON ALL TABLES IN SCHEMA lighting TO pccom_api")
                conn.execute("""
                    GRANT INSERT,UPDATE,DELETE ON lighting.auth_sessions TO pccom_api;
                    GRANT INSERT,UPDATE ON lighting.staging_commands,lighting.staging_requests,lighting.staging_audit TO pccom_api;
                    GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA lighting TO pccom_api;
                    GRANT SELECT ON lighting.assets,lighting.ingestion_bindings TO pccom_ingestion;
                    GRANT SELECT,INSERT,UPDATE ON lighting.telemetry_lighting,lighting.telemetry_led,
                        lighting.ingestion_receipts,lighting.ingestion_dlq TO pccom_ingestion;
                    GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA lighting TO pccom_ingestion;
                """)
            print(json.dumps({"migrated": True, "registered_assets": len(registry["assets"])}))
        finally:
            conn.execute("SELECT pg_advisory_unlock(260029)")


if __name__ == "__main__":
    migrate()
