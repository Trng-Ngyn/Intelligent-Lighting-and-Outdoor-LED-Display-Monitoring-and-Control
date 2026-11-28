"""Explicitly synthetic commissioning fixtures, never production asset identities."""

from uuid import UUID, uuid5


def demo_registry():
    tenant = "11111111-1111-4111-8111-111111111111"
    site = "22222222-2222-4222-8222-222222222222"
    result = []
    for code, kind, aid, did, lat, lon in [
        ("W5_LIGHT_001", "lighting", "44444444-4444-4444-8444-444444444444", "66666666-6666-4666-8666-666666666666", 16.0678, 108.2240),
        ("W5_LIGHT_002", "lighting", str(uuid5(UUID(tenant), "light2")), str(uuid5(UUID(tenant), "device2")), 16.0684, 108.2251),
        ("W5_LED_001", "led", "55555555-5555-4555-8555-555555555555", "77777777-7777-4777-8777-777777777777", 16.0669, 108.2254),
    ]:
        result.append({
            "tenant_id": tenant, "site_id": site, "asset_id": aid, "device_id": did,
            "location_id": str(uuid5(UUID(tenant), code + "/location")),
            "tenant_code": "t1", "cloud_site": "s01", "gateway_code": "gw-001",
            "field_site": "W5_DEMO", "device_code": code, "kind": kind,
            "model": "W5-TEST", "firmware": "1.0.0", "energy_mode": "interval",
            "latitude": lat, "longitude": lon, "location_name": "DEMO · " + code,
            "heartbeat_s": 5, "command_mode": "southbound", "is_demo": True,
        })
    return {"version": 1, "assets": result}

