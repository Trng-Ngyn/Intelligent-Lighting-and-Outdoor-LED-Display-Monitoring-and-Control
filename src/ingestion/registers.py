"""Derive interval energy from ordered registers, including late arrivals/reset gaps."""

from uuid import UUID, uuid5
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def reconcile_registers(connection, kind, affected):
    if not affected:
        return
    table = sql.Identifier("lighting", "telemetry_" + kind)
    # Only affected assets are read; native interval messages never enter this path.
    # Updating an old derived interval invalidates its Timescale continuous aggregate.
    query = sql.SQL("""
        WITH affected AS (
          SELECT * FROM unnest(%s::uuid[],%s::uuid[],%s::uuid[],%s::timestamptz[])
            AS a(tenant_id,site_id,asset_id,since)
        )
        SELECT t.tenant_id,t.site_id,t.asset_id,source_time,message_id,sequence,
               clock_quality, energy_register_wh, counter_epoch,
               energy_interval_wh, energy_interval_start, metric_quality, details,
               source_time < a.since AS seed
        FROM {} t JOIN affected a USING (tenant_id,site_id,asset_id)
        WHERE energy_register_wh IS NOT NULL AND (
          source_time >= a.since OR source_time = (
            SELECT max(p.source_time) FROM {} p
            WHERE p.tenant_id=t.tenant_id AND p.site_id=t.site_id AND p.asset_id=t.asset_id
              AND p.energy_register_wh IS NOT NULL AND p.source_time<a.since
          ))
        ORDER BY t.tenant_id,t.site_id,t.asset_id,source_time,message_id
        FOR UPDATE OF t
    """).format(table, table)
    keys = list(affected)
    params = ([k[0] for k in keys], [k[1] for k in keys], [k[2] for k in keys],
              [affected[k] for k in keys])
    with connection.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(query, params).fetchall()
    previous = {}
    changes = []
    epochs = {}
    for row in rows:
        key = (row["tenant_id"], row["site_id"], row["asset_id"])
        details = dict(row["details"])
        qualities = dict(row["metric_quality"])
        derive = details.get("derive_register", False)
        source_epoch = details.get("source_counter_epoch", str(row["counter_epoch"]))
        inferred = details.get("inferred_counter_epoch", False)
        effective = epochs.get((key, source_epoch), UUID(source_epoch))
        prior = previous.get(key)
        valid = row["clock_quality"] == "synced" and qualities.get("energy_register_wh") in ("measured", "estimated")
        if row["seed"]:
            if valid:
                effective = row["counter_epoch"]
                epochs[(key, source_epoch)] = effective
                previous[key] = {"register": row["energy_register_wh"], "time": row["source_time"], "epoch": effective}
            continue
        delta, start = None, None
        if valid and prior is not None:
            reset = row["energy_register_wh"] < prior["register"]
            if inferred and reset:
                effective = uuid5(row["asset_id"], "reset/" + row["source_time"].isoformat()
                                  + "/" + str(row["message_id"]))
                epochs[(key, source_epoch)] = effective
            if not reset and effective == prior["epoch"] and row["source_time"] > prior["time"]:
                delta = row["energy_register_wh"] - prior["register"]
                start = prior["time"]
        if valid:
            previous[key] = {"register": row["energy_register_wh"], "time": row["source_time"], "epoch": effective}
        else:
            previous.pop(key, None)
        if not derive:
            continue
        quality = "estimated" if delta is not None else "unavailable"
        qualities["energy_interval_wh"] = quality
        details["energy_derivation"] = "register_difference" if delta is not None else "baseline_or_reset_gap"
        new = (delta, start, effective, qualities, details)
        old = (row["energy_interval_wh"], row["energy_interval_start"], row["counter_epoch"],
               row["metric_quality"], row["details"])
        if new != old:
            changes.append((delta, start, effective, Jsonb(qualities), Jsonb(details),
                            row["tenant_id"], row["site_id"], row["asset_id"],
                            row["source_time"], row["message_id"]))
    if changes:
        query = sql.SQL("""
            UPDATE {} SET energy_interval_wh=%s, energy_interval_start=%s,
                counter_epoch=%s, metric_quality=%s, details=%s
            WHERE tenant_id=%s AND site_id=%s AND asset_id=%s
              AND source_time=%s AND message_id=%s
        """).format(table)
        with connection.cursor() as cursor:
            cursor.executemany(query, changes)
