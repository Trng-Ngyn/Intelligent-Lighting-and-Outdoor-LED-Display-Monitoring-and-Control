CREATE TABLE IF NOT EXISTS lighting.ingestion_receipts (
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    message_id uuid NOT NULL,
    source_time timestamptz NOT NULL,
    payload_hash text NOT NULL,
    stored_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, site_id, asset_id, message_id)
);

CREATE TABLE IF NOT EXISTS lighting.ingestion_dlq (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payload_hash text NOT NULL UNIQUE,
    topic text NOT NULL,
    payload bytea NOT NULL,
    reason text NOT NULL,
    received_time timestamptz NOT NULL,
    published_at timestamptz
);

CREATE INDEX IF NOT EXISTS ingestion_dlq_pending_idx
    ON lighting.ingestion_dlq (id) WHERE published_at IS NULL;

CREATE TABLE IF NOT EXISTS lighting.ingestion_bindings (
    field_site text NOT NULL,
    device_type text NOT NULL CHECK (device_type IN ('light', 'led_display')),
    kind text GENERATED ALWAYS AS
        (CASE WHEN device_type = 'light' THEN 'lighting' ELSE 'led' END) STORED,
    device_code text NOT NULL,
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    device_id uuid NOT NULL,
    tenant_code text NOT NULL DEFAULT 't1',
    cloud_site text NOT NULL DEFAULT 's01',
    gateway_code text NOT NULL DEFAULT 'gw-001',
    command_mode text NOT NULL DEFAULT 'southbound'
        CHECK (command_mode IN ('southbound', 'northbound', 'legacy')),
    trust_legacy_clock boolean NOT NULL DEFAULT false,
    is_demo boolean NOT NULL DEFAULT false,
    PRIMARY KEY (field_site, device_type, device_code),
    UNIQUE (tenant_id, site_id, asset_id),
    FOREIGN KEY (tenant_id, site_id, asset_id, device_id, kind)
        REFERENCES lighting.assets (tenant_id, site_id, asset_id, device_id, kind)
);
