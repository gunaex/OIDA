PRAGMA foreign_keys = ON;

ALTER TABLE projects ADD COLUMN next_execution_number INTEGER NOT NULL DEFAULT 1;

CREATE TABLE execution_bindings (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  target_type TEXT NOT NULL CHECK(target_type IN ('PM_AGAIN')),
  external_project_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('UNBOUND','INVALID','READY','STALE','ERROR')),
  capabilities_json TEXT NOT NULL,
  last_verified_at TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id,target_type)
);

CREATE TABLE materialization_ai_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  requested_by TEXT NOT NULL REFERENCES users(id),
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  reasoning_effort TEXT,
  prompt_version TEXT NOT NULL,
  instruction TEXT NOT NULL DEFAULT '',
  delivery_baseline_id TEXT NOT NULL REFERENCES delivery_baselines(id),
  status TEXT NOT NULL CHECK(status IN ('RUNNING','SUCCEEDED','FAILED')),
  failure_code TEXT,
  findings_json TEXT NOT NULL DEFAULT '[]',
  input_tokens INTEGER,
  cache_hit_tokens INTEGER,
  output_tokens INTEGER,
  total_tokens INTEGER,
  latency_ms REAL,
  provider_request_id TEXT,
  started_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE materialization_plans (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  delivery_baseline_id TEXT NOT NULL REFERENCES delivery_baselines(id),
  ai_run_id TEXT REFERENCES materialization_ai_runs(id),
  status TEXT NOT NULL CHECK(status IN ('NEEDS_REVIEW','AUTHORIZED','MATERIALIZED','PARTIAL','REJECTED')),
  current_revision INTEGER NOT NULL DEFAULT 1,
  routing_warnings_json TEXT NOT NULL DEFAULT '[]',
  unresolved_items_json TEXT NOT NULL DEFAULT '[]',
  authorized_by TEXT REFERENCES users(id),
  authorized_at TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(ai_run_id)
);

CREATE TABLE materialization_plan_revisions (
  id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL REFERENCES materialization_plans(id),
  project_id TEXT NOT NULL REFERENCES projects(id),
  revision INTEGER NOT NULL,
  content_json TEXT NOT NULL,
  edited_by TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK(actor_type IN ('AI','HUMAN','SYSTEM')),
  created_at TEXT NOT NULL,
  UNIQUE(plan_id,revision)
);

CREATE TABLE materialization_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  plan_id TEXT NOT NULL REFERENCES materialization_plans(id),
  source_delivery_item_id TEXT REFERENCES delivery_plan_revision_items(id),
  source_delivery_item_ref TEXT,
  source_plan_revision_id TEXT NOT NULL REFERENCES delivery_plan_revisions(id),
  target_type TEXT NOT NULL CHECK(target_type IN ('INTERNAL','PM_AGAIN','MANUAL_EXTERNAL')),
  binding_id TEXT REFERENCES execution_bindings(id),
  execution_title TEXT NOT NULL,
  execution_description TEXT NOT NULL,
  owner_id TEXT REFERENCES users(id),
  owner_role TEXT,
  priority TEXT NOT NULL CHECK(priority IN ('HIGH','MEDIUM','LOW')),
  milestone_ref TEXT,
  execution_type TEXT NOT NULL CHECK(execution_type IN ('BUILD','CONFIGURE','INTEGRATE','VALIDATE','DOCUMENT','MIGRATE','OPERATE','DECIDE')),
  acceptance_hint TEXT NOT NULL,
  dependencies_json TEXT NOT NULL DEFAULT '[]',
  warnings_json TEXT NOT NULL DEFAULT '[]',
  external_reference TEXT,
  origin TEXT NOT NULL CHECK(origin IN ('AI','HUMAN')),
  enabled INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL CHECK(status IN ('PLANNED','MATERIALIZING','MATERIALIZED','BLOCKED','FAILED','UNCONFIRMED','DISABLED')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE execution_items (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  execution_code TEXT NOT NULL,
  materialization_plan_id TEXT REFERENCES materialization_plans(id),
  materialization_item_id TEXT UNIQUE REFERENCES materialization_items(id),
  source_delivery_item_id TEXT REFERENCES delivery_plan_revision_items(id),
  source_plan_revision_id TEXT REFERENCES delivery_plan_revisions(id),
  target_type TEXT NOT NULL CHECK(target_type IN ('INTERNAL','PM_AGAIN','MANUAL_EXTERNAL')),
  binding_id TEXT REFERENCES execution_bindings(id),
  external_id TEXT,
  external_url TEXT,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  owner_id TEXT REFERENCES users(id),
  owner_role TEXT,
  priority TEXT NOT NULL CHECK(priority IN ('HIGH','MEDIUM','LOW')),
  status TEXT NOT NULL CHECK(status IN ('NOT_STARTED','IN_PROGRESS','BLOCKED','COMPLETED','CANCELLED')),
  milestone_ref TEXT,
  dependencies_json TEXT NOT NULL DEFAULT '[]',
  expected_json TEXT NOT NULL,
  link_state TEXT NOT NULL CHECK(link_state IN ('LINKED','UNLINKED')),
  reconciliation_status TEXT NOT NULL CHECK(reconciliation_status IN ('NOT_CHECKED','CONFIRMED','MISMATCH','STALE','UNCONFIRMED','ERROR')),
  last_verified_at TEXT,
  current_revision INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id,execution_code),
  UNIQUE(target_type,binding_id,external_id)
);

CREATE TABLE execution_item_revisions (
  id TEXT PRIMARY KEY,
  execution_item_id TEXT NOT NULL REFERENCES execution_items(id),
  project_id TEXT NOT NULL REFERENCES projects(id),
  revision INTEGER NOT NULL,
  content_json TEXT NOT NULL,
  edited_by TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK(actor_type IN ('HUMAN','SYSTEM')),
  created_at TEXT NOT NULL,
  UNIQUE(execution_item_id,revision)
);

CREATE TABLE execution_reconciliation_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  delivery_baseline_id TEXT NOT NULL REFERENCES delivery_baselines(id),
  requested_by TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('RUNNING','SUCCEEDED','PARTIAL','FAILED')),
  confirmed_count INTEGER NOT NULL DEFAULT 0,
  missing_count INTEGER NOT NULL DEFAULT 0,
  mismatch_count INTEGER NOT NULL DEFAULT 0,
  stale_count INTEGER NOT NULL DEFAULT 0,
  unconfirmed_count INTEGER NOT NULL DEFAULT 0,
  started_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE execution_drift_records (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  detected_key TEXT NOT NULL,
  delivery_baseline_id TEXT NOT NULL REFERENCES delivery_baselines(id),
  source_delivery_item_id TEXT REFERENCES delivery_plan_revision_items(id),
  execution_item_id TEXT REFERENCES execution_items(id),
  drift_type TEXT NOT NULL CHECK(drift_type IN ('MISSING_EXECUTION','EXTERNAL_ITEM_MISSING','SCOPE_DRIFT','OWNER_DRIFT','DEPENDENCY_DRIFT','MILESTONE_DRIFT','UNLINKED_EXECUTION','STATUS_STALE')),
  severity TEXT NOT NULL CHECK(severity IN ('INFO','WARNING','CRITICAL')),
  status TEXT NOT NULL CHECK(status IN ('OPEN','ACKNOWLEDGED','RESOLVED','NO_LONGER_APPLICABLE')),
  detail_json TEXT NOT NULL,
  detected_at TEXT NOT NULL,
  acknowledged_by TEXT REFERENCES users(id),
  acknowledged_at TEXT,
  resolved_at TEXT,
  UNIQUE(project_id,detected_key)
);

CREATE INDEX idx_execution_bindings_project ON execution_bindings(project_id);
CREATE INDEX idx_materialization_runs_project ON materialization_ai_runs(project_id);
CREATE INDEX idx_materialization_plans_project ON materialization_plans(project_id);
CREATE INDEX idx_materialization_items_plan ON materialization_items(plan_id);
CREATE INDEX idx_execution_items_project ON execution_items(project_id);
CREATE INDEX idx_reconciliation_project ON execution_reconciliation_runs(project_id);
CREATE INDEX idx_execution_drift_project ON execution_drift_records(project_id,status);
