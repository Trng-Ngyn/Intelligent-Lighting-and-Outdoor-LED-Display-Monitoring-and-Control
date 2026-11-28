"""Compare source-device publication manifest against committed receipt IDs.

Input is JSONL, one source record containing tenant_id,site_id,asset_id,message_id.
Never treat a synthetic publisher as evidence from a physical ESP32.
"""

import argparse
import json
from pathlib import Path
import sys
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from ingestion.worker import database_connection  # noqa: E402


def reconcile(conn, records):
    expected = set()
    for row in records:
        tenant, site, asset = (UUID(row[k]) for k in ("tenant_id", "site_id", "asset_id"))
        try:
            mid = UUID(str(row["message_id"]))
        except ValueError:
            mid = uuid5(asset, str(row["message_id"]))
        expected.add((tenant, site, asset, mid))
    found = set()
    for key in expected:
        row = conn.execute("""
            SELECT 1 FROM lighting.ingestion_receipts
            WHERE tenant_id=%s AND site_id=%s AND asset_id=%s AND message_id=%s
        """, key).fetchone()
        if row:
            found.add(key)
    missing = expected - found
    return {"source_unique": len(expected), "stored_unique": len(found),
            "coverage_pct": 100 * len(found) / len(expected) if expected else None,
            "missing": [[str(x) for x in key] for key in sorted(missing)],
            "passed": bool(expected) and not missing}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.manifest.read_text().splitlines() if line.strip()]
    with database_connection() as conn:
        report = reconcile(conn, records)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)
