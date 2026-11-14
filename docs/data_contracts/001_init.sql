BEGIN;

CREATE EXTENSION IF NOT EXISTS timescaledb WITH SCHEMA public;
CREATE SCHEMA IF NOT EXISTS lighting;
SET LOCAL search_path = lighting, public;

CREATE TABLE IF NOT EXISTS locations (
    tenant_id uuid,
    site_id uuid,
    location_id uuid,
    name text NOT NULL,
    latitude double precision CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision CHECK (longitude BETWEEN -180 AND 180),
    PRIMARY KEY (tenant_id, site_id, location_id),
    CHECK ((latitude IS NULL) = (longitude IS NULL))
);

CREATE TABLE IF NOT EXISTS circuits (
    tenant_id uuid,
    site_id uuid,
    circuit_id uuid,
    location_id uuid NOT NULL,
    code text NOT NULL,
    PRIMARY KEY (tenant_id, site_id, circuit_id),
    UNIQUE (tenant_id, site_id, code),
    FOREIGN KEY (tenant_id, site_id, location_id) REFERENCES locations
);

CREATE TABLE IF NOT EXISTS firmware_versions (
    tenant_id uuid,
    model text,
    version text,
    released_at timestamptz,
    PRIMARY KEY (tenant_id, model, version)
);

CREATE TABLE IF NOT EXISTS assets (
    tenant_id uuid,
    site_id uuid,
    asset_id uuid,
    asset_code text NOT NULL,
    device_id uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('lighting', 'led', 'gateway')),
    parent_id uuid,
    location_id uuid NOT NULL,
    circuit_id uuid,
    model text NOT NULL,
    firmware text NOT NULL,
    owner_ref text NOT NULL,
    energy_mode text NOT NULL CHECK (energy_mode IN ('none', 'interval', 'counter')),
    heartbeat_s integer NOT NULL DEFAULT 60 CHECK (heartbeat_s > 0),
    commissioned_at timestamptz,
    retired_at timestamptz,
    PRIMARY KEY (tenant_id, site_id, asset_id),
    UNIQUE (tenant_id, asset_id),
    UNIQUE (tenant_id, site_id, asset_code),
    UNIQUE (tenant_id, site_id, asset_id, device_id, kind),
    FOREIGN KEY (tenant_id, site_id, parent_id) REFERENCES assets,
    FOREIGN KEY (tenant_id, site_id, location_id) REFERENCES locations,
    FOREIGN KEY (tenant_id, site_id, circuit_id) REFERENCES circuits,
    FOREIGN KEY (tenant_id, model, firmware) REFERENCES firmware_versions,
    CHECK (parent_id IS DISTINCT FROM asset_id),
    CHECK (retired_at IS NULL OR (commissioned_at IS NOT NULL AND retired_at > commissioned_at)),
    CHECK (kind <> 'gateway' OR energy_mode = 'none')
);

CREATE TABLE IF NOT EXISTS users_roles (
    tenant_id uuid,
    site_id uuid,
    user_id uuid,
    role_code text CHECK (btrim(role_code) <> ''),
    PRIMARY KEY (tenant_id, site_id, user_id, role_code)
);

COMMIT;

BEGIN;

SET LOCAL search_path = lighting, public;

CREATE TABLE IF NOT EXISTS telemetry_lighting (
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    device_id uuid NOT NULL,
    kind text NOT NULL DEFAULT 'lighting' CHECK (kind = 'lighting'),
    message_id uuid NOT NULL,
    schema_version smallint NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    source_time timestamptz NOT NULL,
    received_time timestamptz NOT NULL,
    sequence bigint NOT NULL CHECK (sequence BETWEEN 0 AND 9007199254740991),
    firmware text NOT NULL,
    clock_quality text NOT NULL CHECK (clock_quality IN ('synced', 'uncertain')),
    power_w double precision CHECK (power_w >= 0),
    energy_interval_wh numeric(20,6) CHECK (energy_interval_wh >= 0),
    energy_interval_start timestamptz,
    energy_register_wh numeric(20,6) CHECK (energy_register_wh >= 0),
    counter_epoch uuid,
    voltage_v double precision CHECK (voltage_v >= 0),
    current_a double precision CHECK (current_a >= 0),
    power_factor double precision CHECK (power_factor BETWEEN -1 AND 1),
    illuminance_lx double precision CHECK (illuminance_lx >= 0),
    temperature_c double precision,
    metric_quality jsonb NOT NULL CHECK (jsonb_typeof(metric_quality) = 'object'),
    details jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(details) = 'object'),
    PRIMARY KEY (tenant_id, site_id, asset_id, source_time, message_id),
    FOREIGN KEY (tenant_id, site_id, asset_id, device_id, kind)
        REFERENCES assets (tenant_id, site_id, asset_id, device_id, kind),
    CHECK ((energy_interval_wh IS NULL) = (energy_interval_start IS NULL)),
    CHECK (energy_interval_start < source_time),
    CHECK ((energy_register_wh IS NULL) = (counter_epoch IS NULL))
);

CREATE TABLE IF NOT EXISTS telemetry_led (
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    device_id uuid NOT NULL,
    kind text NOT NULL DEFAULT 'led' CHECK (kind = 'led'),
    message_id uuid NOT NULL,
    schema_version smallint NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    source_time timestamptz NOT NULL,
    received_time timestamptz NOT NULL,
    sequence bigint NOT NULL CHECK (sequence BETWEEN 0 AND 9007199254740991),
    firmware text NOT NULL,
    clock_quality text NOT NULL CHECK (clock_quality IN ('synced', 'uncertain')),
    power_w double precision CHECK (power_w >= 0),
    energy_interval_wh numeric(20,6) CHECK (energy_interval_wh >= 0),
    energy_interval_start timestamptz,
    energy_register_wh numeric(20,6) CHECK (energy_register_wh >= 0),
    counter_epoch uuid,
    voltage_v double precision CHECK (voltage_v >= 0),
    current_a double precision CHECK (current_a >= 0),
    power_factor double precision CHECK (power_factor BETWEEN -1 AND 1),
    illuminance_lx double precision CHECK (illuminance_lx >= 0),
    temperature_c double precision,
    metric_quality jsonb NOT NULL CHECK (jsonb_typeof(metric_quality) = 'object'),
    details jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(details) = 'object'),
    PRIMARY KEY (tenant_id, site_id, asset_id, source_time, message_id),
    FOREIGN KEY (tenant_id, site_id, asset_id, device_id, kind)
        REFERENCES assets (tenant_id, site_id, asset_id, device_id, kind),
    CHECK ((energy_interval_wh IS NULL) = (energy_interval_start IS NULL)),
    CHECK (energy_interval_start < source_time),
    CHECK ((energy_register_wh IS NULL) = (counter_epoch IS NULL))
);

SELECT create_hypertable(
    'lighting.telemetry_lighting',
    by_range('source_time', INTERVAL '7 days'),
    if_not_exists => TRUE,
    create_default_indexes => FALSE
);

SELECT create_hypertable(
    'lighting.telemetry_led',
    by_range('source_time', INTERVAL '7 days'),
    if_not_exists => TRUE,
    create_default_indexes => FALSE
);

CREATE INDEX IF NOT EXISTS telemetry_lighting_site_time_idx
    ON telemetry_lighting (tenant_id, site_id, source_time DESC);

CREATE INDEX IF NOT EXISTS telemetry_led_site_time_idx
    ON telemetry_led (tenant_id, site_id, source_time DESC);

COMMIT;
BEGIN;
SET LOCAL search_path = lighting, public;
SET LOCAL TIME ZONE 'UTC';

CREATE MATERIALIZED VIEW IF NOT EXISTS energy_lighting_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket(INTERVAL '1 hour', source_time, INTERVAL '1 microsecond') AS bucket,
       tenant_id, site_id, asset_id,
       SUM(energy_interval_wh) AS energy_wh
FROM telemetry_lighting
WHERE clock_quality = 'synced'
  AND energy_interval_wh IS NOT NULL
  AND metric_quality->>'energy_interval_wh' IN ('measured', 'estimated')
GROUP BY 1, 2, 3, 4
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS energy_lighting_daily
WITH (timescaledb.continuous) AS
SELECT time_bucket(INTERVAL '1 day', bucket, INTERVAL '1 microsecond') AS bucket,
       tenant_id, site_id, asset_id,
       SUM(energy_wh) AS energy_wh
FROM energy_lighting_hourly
GROUP BY 1, 2, 3, 4
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS energy_lighting_monthly
WITH (timescaledb.continuous) AS
SELECT time_bucket(INTERVAL '1 month', bucket, INTERVAL '1 microsecond') AS bucket,
       tenant_id, site_id, asset_id,
       SUM(energy_wh) AS energy_wh
FROM energy_lighting_daily
GROUP BY 1, 2, 3, 4
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS energy_led_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket(INTERVAL '1 hour', source_time, INTERVAL '1 microsecond') AS bucket,
       tenant_id, site_id, asset_id,
       SUM(energy_interval_wh) AS energy_wh
FROM telemetry_led
WHERE clock_quality = 'synced'
  AND energy_interval_wh IS NOT NULL
  AND metric_quality->>'energy_interval_wh' IN ('measured', 'estimated')
GROUP BY 1, 2, 3, 4
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS energy_led_daily
WITH (timescaledb.continuous) AS
SELECT time_bucket(INTERVAL '1 day', bucket, INTERVAL '1 microsecond') AS bucket,
       tenant_id, site_id, asset_id,
       SUM(energy_wh) AS energy_wh
FROM energy_led_hourly
GROUP BY 1, 2, 3, 4
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS energy_led_monthly
WITH (timescaledb.continuous) AS
SELECT time_bucket(INTERVAL '1 month', bucket, INTERVAL '1 microsecond') AS bucket,
       tenant_id, site_id, asset_id,
       SUM(energy_wh) AS energy_wh
FROM energy_led_daily
GROUP BY 1, 2, 3, 4
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    view_name::regclass,
    start_offset => refresh_from,
    end_offset => refresh_until,
    schedule_interval => run_every,
    if_not_exists => TRUE
)
FROM (VALUES
    ('lighting.energy_lighting_hourly',  INTERVAL '14 days',  INTERVAL '0 seconds', INTERVAL '15 minutes'),
    ('lighting.energy_lighting_daily',   INTERVAL '21 days',  INTERVAL '1 hour',    INTERVAL '1 hour'),
    ('lighting.energy_lighting_monthly', INTERVAL '3 months', INTERVAL '2 hours',   INTERVAL '1 day'),
    ('lighting.energy_led_hourly',       INTERVAL '14 days',  INTERVAL '0 seconds', INTERVAL '15 minutes'),
    ('lighting.energy_led_daily',        INTERVAL '21 days',  INTERVAL '1 hour',    INTERVAL '1 hour'),
    ('lighting.energy_led_monthly',      INTERVAL '3 months', INTERVAL '2 hours',   INTERVAL '1 day')
) AS policies(view_name, refresh_from, refresh_until, run_every);

COMMIT;