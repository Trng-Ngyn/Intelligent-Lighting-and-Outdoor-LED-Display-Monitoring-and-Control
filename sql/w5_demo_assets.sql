BEGIN;

INSERT INTO lighting.locations (tenant_id, site_id, location_id, name)
VALUES (
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '33333333-3333-4333-8333-333333333333',
    'W5-DE local demonstration'
) ON CONFLICT DO NOTHING;

INSERT INTO lighting.firmware_versions (tenant_id, model, version)
VALUES ('11111111-1111-4111-8111-111111111111', 'W5-DEMO', '1.0.0')
ON CONFLICT DO NOTHING;

INSERT INTO lighting.assets (
    tenant_id, site_id, asset_id, asset_code, device_id, kind,
    location_id, model, firmware, owner_ref, energy_mode, commissioned_at
)
VALUES
(
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '44444444-4444-4444-8444-444444444444', 'W5_LIGHT_001',
    '66666666-6666-4666-8666-666666666666', 'lighting',
    '33333333-3333-4333-8333-333333333333',
    'W5-DEMO', '1.0.0', 'W5-DE local test', 'interval', now()
),
(
    '11111111-1111-4111-8111-111111111111',
    '22222222-2222-4222-8222-222222222222',
    '55555555-5555-4555-8555-555555555555', 'W5_LED_001',
    '77777777-7777-4777-8777-777777777777', 'led',
    '33333333-3333-4333-8333-333333333333',
    'W5-DEMO', '1.0.0', 'W5-DE local test', 'interval', now()
) ON CONFLICT DO NOTHING;

COMMIT;
