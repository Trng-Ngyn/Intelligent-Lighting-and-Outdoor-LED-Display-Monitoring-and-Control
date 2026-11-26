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
