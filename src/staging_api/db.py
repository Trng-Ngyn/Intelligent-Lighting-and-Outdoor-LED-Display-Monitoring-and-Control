import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def secret(name, default=""):
    path = os.getenv(name + "_FILE")
    return Path(path).read_text().strip() if path else os.getenv(name, default)


@contextmanager
def connection(dicts=False):
    with psycopg.connect(
        host=os.getenv("PGHOST", "timescaledb"), port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "pccom_staging"), user=os.getenv("PGUSER", "postgres"),
        password=secret("PGPASSWORD"), connect_timeout=5,
        sslmode=os.getenv("PGSSLMODE", "prefer"), autocommit=True,
        row_factory=dict_row if dicts else None,
    ) as conn:
        yield conn


def scope_clause(alias="a"):
    return (
        "EXISTS (SELECT 1 FROM lighting.users_roles ur WHERE ur.user_id=%s "
        "AND ur.tenant_id=" + alias + ".tenant_id AND ur.site_id=" + alias + ".site_id)"
    )
