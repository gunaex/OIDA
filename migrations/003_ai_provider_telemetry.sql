PRAGMA foreign_keys = ON;

CREATE TABLE ai_run_telemetry (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  run_kind TEXT NOT NULL CHECK(run_kind IN ('REQUIREMENT','SOLUTION','DELIVERY_PLAN')),
  run_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  reasoning_effort TEXT,
  input_tokens INTEGER,
  cache_hit_tokens INTEGER,
  output_tokens INTEGER,
  total_tokens INTEGER,
  latency_ms REAL,
  provider_request_id TEXT,
  error_class TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(run_kind,run_id)
);

CREATE INDEX idx_ai_telemetry_project ON ai_run_telemetry(project_id,created_at);
