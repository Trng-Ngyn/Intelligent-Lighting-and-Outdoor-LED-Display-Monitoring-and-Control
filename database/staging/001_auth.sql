-- SCRUM-30 auth functions expect text user_id and JSON roles.
CREATE TABLE IF NOT EXISTS lighting.auth_sessions (
    session_id uuid PRIMARY KEY,
    user_id text NOT NULL,
    roles jsonb NOT NULL,
    refresh_token_hash text NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS auth_sessions_expiry ON lighting.auth_sessions(expires_at);
