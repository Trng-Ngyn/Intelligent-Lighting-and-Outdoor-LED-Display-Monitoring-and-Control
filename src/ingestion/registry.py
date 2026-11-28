"""Transactional device registration; IDs are explicit, never guessed from a payload."""

import json
from pathlib import Path
from uuid import UUID

from jsonschema import Draft7Validator, FormatChecker


ASSET_REQUIRED = [
    "tenant_id", "site_id", "asset_id", "device_id", "location_id",
    "tenant_code", "field_site", "cloud_site", "gateway_code", "device_code",
    "kind", "model", "firmware", "energy_mode",
]
UUID_FIELDS = ("tenant_id", "site_id", "asset_id", "device_id", "location_id")
SEGMENT = {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,80}$"}
REGISTRY_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object", "required": ["version", "assets"], "additionalProperties": False,
    "properties": {
        "version": {"const": 1},
        "assets": {"type": "array", "minItems": 1, "maxItems": 20000, "items": {
            "type": "object", "required": ASSET_REQUIRED, "additionalProperties": False,
            "properties": {
                **{k: {"type": "string", "format": "uuid"} for k in UUID_FIELDS},
                **{k: SEGMENT for k in ("tenant_code", "field_site", "cloud_site", "gateway_code", "device_code")},
                "kind": {"enum": ["lighting", "led"]},
                "model": {"type": "string", "minLength": 1, "maxLength": 120},
                "firmware": {"type": "string", "minLength": 1, "maxLength": 80},
                "energy_mode": {"enum": ["none", "interval", "counter"]},
                "location_name": {"type": "string", "maxLength": 200},
                "latitude": {"type": ["number", "null"], "minimum": -90, "maximum": 90},
                "longitude": {"type": ["number", "null"], "minimum": -180, "maximum": 180},
                "heartbeat_s": {"type": "integer", "minimum": 1, "maximum": 86400},
                "command_mode": {"enum": ["southbound", "northbound", "legacy"]},
                "trust_legacy_clock": {"type": "boolean"},
                "is_demo": {"type": "boolean"},
            },
        }},
    },
}


def validate_registry(document):
    Draft7Validator(REGISTRY_SCHEMA, format_checker=FormatChecker()).validate(document)
    keys, codes, devices = set(), set(), set()
    for asset in document["assets"]:
        key = (asset["tenant_id"], asset["site_id"], asset["asset_id"])
        code = (asset["field_site"], asset["kind"], asset["device_code"])
        if key in keys or code in codes or asset["device_id"] in devices:
            raise ValueError("Duplicate registry identity or MQTT device code")
        if (asset.get("latitude") is None) != (asset.get("longitude") is None):
            raise ValueError("latitude and longitude must both be set or both be null")
        keys.add(key)
        codes.add(code)
        devices.add(asset["device_id"])


def register_assets(connection, document, allow_demo=False):
    validate_registry(document)
    if any(a.get("is_demo", False) for a in document["assets"]) and not allow_demo:
        raise ValueError("Demo registration needs an explicit --allow-demo")
    with connection.transaction():
        for a in document["assets"]:
            ids = {name: UUID(a[name]) for name in UUID_FIELDS}
            existing = connection.execute("""
                SELECT device_id, kind FROM lighting.assets
                WHERE tenant_id=%s AND site_id=%s AND asset_id=%s
            """, (ids["tenant_id"], ids["site_id"], ids["asset_id"])).fetchone()
            if existing and (existing[0] != ids["device_id"] or existing[1] != a["kind"]):
                raise ValueError("Changing a registered device identity requires an explicit migration")
            connection.execute("""
                INSERT INTO lighting.locations (tenant_id,site_id,location_id,name,latitude,longitude)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id,site_id,location_id) DO UPDATE SET
                  name=EXCLUDED.name, latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude
            """, (ids["tenant_id"], ids["site_id"], ids["location_id"],
                  a.get("location_name", a["field_site"]), a.get("latitude"), a.get("longitude")))
            connection.execute("""
                INSERT INTO lighting.firmware_versions (tenant_id,model,version)
                VALUES (%s,%s,%s) ON CONFLICT DO NOTHING
            """, (ids["tenant_id"], a["model"], a["firmware"]))
            connection.execute("""
                INSERT INTO lighting.assets
                (tenant_id,site_id,asset_id,asset_code,device_id,kind,location_id,
                 model,firmware,owner_ref,energy_mode,heartbeat_s,commissioned_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,clock_timestamp())
                ON CONFLICT (tenant_id,site_id,asset_id) DO UPDATE SET
                  asset_code=EXCLUDED.asset_code, location_id=EXCLUDED.location_id,
                  model=EXCLUDED.model, firmware=EXCLUDED.firmware,
                  energy_mode=EXCLUDED.energy_mode, heartbeat_s=EXCLUDED.heartbeat_s
            """, (ids["tenant_id"], ids["site_id"], ids["asset_id"], a["device_code"],
                  ids["device_id"], a["kind"], ids["location_id"], a["model"], a["firmware"],
                  "W5-DEMO" if a.get("is_demo") else "PCCOM", a["energy_mode"], a.get("heartbeat_s", 60)))
            dtype = "light" if a["kind"] == "lighting" else "led_display"
            connection.execute("""
                INSERT INTO lighting.ingestion_bindings
                (field_site,device_type,device_code,tenant_id,site_id,asset_id,device_id,
                 tenant_code,cloud_site,gateway_code,command_mode,trust_legacy_clock,is_demo)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (field_site,device_type,device_code) DO UPDATE SET
                  tenant_id=EXCLUDED.tenant_id,site_id=EXCLUDED.site_id,
                  asset_id=EXCLUDED.asset_id,device_id=EXCLUDED.device_id,
                  tenant_code=EXCLUDED.tenant_code,cloud_site=EXCLUDED.cloud_site,
                  gateway_code=EXCLUDED.gateway_code,command_mode=EXCLUDED.command_mode,
                  trust_legacy_clock=EXCLUDED.trust_legacy_clock,is_demo=EXCLUDED.is_demo
            """, (a["field_site"], dtype, a["device_code"], ids["tenant_id"], ids["site_id"],
                  ids["asset_id"], ids["device_id"], a["tenant_code"], a["cloud_site"],
                  a["gateway_code"], a.get("command_mode", "southbound"),
                  a.get("trust_legacy_clock", False), a.get("is_demo", False)))
    return len(document["assets"])


def main():
    import argparse
    if __package__:
        from .worker import database_connection
    else:
        from worker import database_connection
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("--allow-demo", action="store_true")
    args = parser.parse_args()
    with database_connection() as connection:
        count = register_assets(connection, json.loads(args.registry.read_text()), args.allow_demo)
    print(json.dumps({"registered": count}))


if __name__ == "__main__":
    main()
