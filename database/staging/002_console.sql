CREATE TABLE IF NOT EXISTS lighting.staging_commands (
    command_id uuid PRIMARY KEY,
    batch_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    user_id uuid NOT NULL,
    brightness integer NOT NULL CHECK (brightness BETWEEN 0 AND 100),
    state text NOT NULL DEFAULT 'queued'
      CHECK (state IN ('queued','sent','acknowledged','executed','verified','rejected','expired','failed')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    sent_at timestamptz,
    ack_at timestamptz,
    verified_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    attempts integer NOT NULL DEFAULT 0,
    reason text,
    result jsonb,
    FOREIGN KEY (tenant_id,site_id,asset_id) REFERENCES lighting.assets(tenant_id,site_id,asset_id)
);
CREATE INDEX IF NOT EXISTS staging_commands_pending
    ON lighting.staging_commands(state,expires_at)
    WHERE state IN ('queued','sent','acknowledged','executed');
CREATE TABLE IF NOT EXISTS lighting.staging_requests (
    user_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (user_id,idempotency_key)
);
CREATE TABLE IF NOT EXISTS lighting.staging_audit (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL,
    action text NOT NULL,
    batch_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    details jsonb NOT NULL
);
