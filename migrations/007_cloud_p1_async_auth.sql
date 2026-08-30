PRAGMA foreign_keys = ON;

ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN bootstrap_policy_applied INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1;

CREATE TABLE async_ai_jobs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  requested_by TEXT NOT NULL REFERENCES users(id),
  operation TEXT NOT NULL CHECK(operation IN ('REQUIREMENTS','REQUIREMENTS_REGENERATE','SOLUTIONS','SOLUTIONS_REGENERATE','DELIVERY_PLAN','DELIVERY_PLAN_REGENERATE','MATERIALIZATION','QA_SCOPE','ACCEPTANCE_PACKAGE')),
  status TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','COMPLETED','FAILED')),
  request_json TEXT NOT NULL,
  result_json TEXT,
  failure_code TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  lease_owner TEXT,
  lease_expires_at TEXT,
  domain_run_id TEXT,
  created_at TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT
);

CREATE INDEX idx_async_ai_jobs_claim ON async_ai_jobs(status,lease_expires_at,created_at);
CREATE INDEX idx_async_ai_jobs_project ON async_ai_jobs(project_id,created_at);
