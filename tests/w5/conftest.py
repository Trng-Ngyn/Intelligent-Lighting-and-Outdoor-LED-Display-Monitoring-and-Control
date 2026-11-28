"""Disposable PostgreSQL tests; native/Compose acceptance tests actual Timescale policies."""

import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import pytest
import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "src/backend"), str(ROOT)]
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-never-use-on-a-real-server")
os.environ.setdefault("DEV_PASSWORD", "test-only-operator-password-for-test-session")
os.environ.setdefault("SIGNING_SECRET", "test-only-signing-secret-for-offline-tests")


@pytest.fixture(scope="session")
def postgres(tmp_path_factory):
    import pgserver
    directory = tmp_path_factory.mktemp("postgres") / "data"
    binary = Path(pgserver.__file__).parent / "pginstall/bin"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    subprocess.run([str(binary / "initdb"), "-D", str(directory), "-U", "postgres", "--auth=trust"],
                   check=True, capture_output=True)
    subprocess.run([str(binary / "pg_ctl"), "-D", str(directory), "-l", str(directory / "server.log"),
                    "-o", "-h 127.0.0.1 -p " + str(port) + " -c unix_socket_directories=''", "-w", "start"],
                   check=True, capture_output=True)
    os.environ.update(PGHOST="127.0.0.1", PGPORT=str(port), PGDATABASE="postgres", PGUSER="postgres", PGSSLMODE="disable")
    uri = "postgresql://postgres@127.0.0.1:" + str(port) + "/postgres"
    try:
        yield uri
    finally:
        subprocess.run([str(binary / "pg_ctl"), "-D", str(directory), "-m", "fast", "stop"], capture_output=True)


@pytest.fixture()
def db(postgres):
    from ingestion.registry import register_assets
    from ingestion.fixtures import demo_registry
    with psycopg.connect(postgres, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS lighting CASCADE")
        # Preserve all approved table definitions and constraints; remove only
        # the extension-dependent hypertable/index/view section in this test.
        source = (ROOT / "docs/data_contracts/001_init.sql").read_text(encoding="utf-8-sig")
        source = re.sub(r"CREATE EXTENSION IF NOT EXISTS timescaledb[^;]*;", "", source)
        source = source[:source.index("SELECT create_hypertable")]
        conn.execute(source + "\nCOMMIT;")
        conn.execute((ROOT / "sql/w5_ingestion.sql").read_text())
        for path in sorted((ROOT / "database/staging").glob("*.sql")):
            conn.execute(path.read_text())
        register_assets(conn, demo_registry(), allow_demo=True)
        conn.execute("""
          INSERT INTO lighting.users_roles
          SELECT DISTINCT tenant_id,site_id,'00000000-0000-4000-8000-000000000001'::uuid,'ADMIN'
          FROM lighting.assets ON CONFLICT DO NOTHING
        """)
        # SQL projection for HTTP serialization tests only, not a Timescale CAGG.
        for kind in ("lighting", "led"):
            conn.execute("CREATE VIEW lighting.energy_" + kind + """_hourly AS
              SELECT tenant_id,site_id,asset_id,date_trunc('hour',source_time-interval '1 microsecond') bucket,
                     sum(energy_interval_wh) energy_wh
              FROM lighting.telemetry_""" + kind + """
              WHERE clock_quality='synced' AND metric_quality->>'energy_interval_wh' IN ('measured','estimated')
              GROUP BY 1,2,3,4
            """)
        conn.execute("""
          CREATE OR REPLACE FUNCTION public.time_bucket(interval,timestamptz)
          RETURNS timestamptz LANGUAGE SQL IMMUTABLE AS
          'SELECT date_bin($1,$2,''2000-01-01 00:00:00+00''::timestamptz)'
        """)
        yield conn
