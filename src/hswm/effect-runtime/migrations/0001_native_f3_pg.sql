CREATE SCHEMA IF NOT EXISTS hswm_f3;

CREATE TABLE IF NOT EXISTS hswm_f3.runs (
  run_id text PRIMARY KEY CHECK (length(run_id) BETWEEN 1 AND 256),
  config_digest char(64) NOT NULL CHECK (config_digest ~ '^[0-9a-f]{64}$'),
  max_calls bigint NOT NULL CHECK (max_calls >= 0 AND max_calls <= 9007199254740991),
  used bigint NOT NULL DEFAULT 0 CHECK (used >= 0 AND used <= max_calls),
  hits bigint NOT NULL DEFAULT 0 CHECK (hits >= 0),
  misses bigint NOT NULL DEFAULT 0 CHECK (misses >= 0),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS hswm_f3.cache_entries (
  run_id text NOT NULL REFERENCES hswm_f3.runs(run_id) ON DELETE RESTRICT,
  request_sha256 char(64) NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  status text NOT NULL CHECK (status IN ('RESERVED','COMPLETED','FAILED_KNOWN')),
  reservation_id uuid NOT NULL UNIQUE,
  document jsonb,
  known_terminal text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  completed_at timestamptz,
  PRIMARY KEY (run_id, request_sha256),
  CHECK ((status = 'COMPLETED') = (document IS NOT NULL)),
  CHECK (document IS NULL OR octet_length(document::text) <= 1048576),
  CHECK ((status = 'FAILED_KNOWN') = (known_terminal IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS hswm_f3.client_counters (
  run_id text NOT NULL REFERENCES hswm_f3.runs(run_id) ON DELETE RESTRICT,
  client_id text NOT NULL CHECK (length(client_id) BETWEEN 1 AND 256),
  hits bigint NOT NULL DEFAULT 0 CHECK (hits >= 0),
  misses bigint NOT NULL DEFAULT 0 CHECK (misses >= 0),
  PRIMARY KEY (run_id, client_id)
);

CREATE TABLE IF NOT EXISTS hswm_f3.attempt_history (
  reservation_id uuid PRIMARY KEY,
  run_id text NOT NULL REFERENCES hswm_f3.runs(run_id) ON DELETE RESTRICT,
  request_sha256 char(64) NOT NULL CHECK (request_sha256 ~ '^[0-9a-f]{64}$'),
  terminal text NOT NULL CHECK (terminal = 'FAILED_KNOWN'),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
