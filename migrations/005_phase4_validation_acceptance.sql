PRAGMA foreign_keys = ON;

ALTER TABLE projects ADD COLUMN next_qa_number INTEGER NOT NULL DEFAULT 1;
ALTER TABLE projects ADD COLUMN next_validation_number INTEGER NOT NULL DEFAULT 1;
ALTER TABLE projects ADD COLUMN next_evidence_number INTEGER NOT NULL DEFAULT 1;
ALTER TABLE projects ADD COLUMN next_acceptance_number INTEGER NOT NULL DEFAULT 1;

CREATE TABLE qa_bindings (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  target_type TEXT NOT NULL CHECK(target_type='QA_AGAIN'), external_project_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('UNBOUND','INVALID','READY','STALE','ERROR')),
  capabilities_json TEXT NOT NULL, last_verified_at TEXT,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(project_id,target_type)
);

CREATE TABLE qa_ai_runs (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  run_type TEXT NOT NULL CHECK(run_type IN ('QA_SCOPE','ACCEPTANCE_PACKAGE')),
  requested_by TEXT NOT NULL REFERENCES users(id), provider TEXT NOT NULL, model TEXT NOT NULL,
  reasoning_effort TEXT, prompt_version TEXT NOT NULL, instruction TEXT NOT NULL DEFAULT '',
  requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id),
  delivery_baseline_id TEXT NOT NULL REFERENCES delivery_baselines(id),
  qa_scope_id TEXT, status TEXT NOT NULL CHECK(status IN ('RUNNING','SUCCEEDED','FAILED')),
  failure_code TEXT, findings_json TEXT NOT NULL DEFAULT '[]',
  input_tokens INTEGER, cache_hit_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER,
  latency_ms REAL, provider_request_id TEXT, started_at TEXT NOT NULL, completed_at TEXT
);

CREATE TABLE qa_scopes (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), qa_code TEXT NOT NULL,
  requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id),
  delivery_baseline_id TEXT NOT NULL REFERENCES delivery_baselines(id),
  delivery_plan_revision_id TEXT NOT NULL REFERENCES delivery_plan_revisions(id),
  execution_snapshot_hash TEXT NOT NULL, execution_reconciliation_run_id TEXT REFERENCES execution_reconciliation_runs(id),
  ai_run_id TEXT REFERENCES qa_ai_runs(id),
  status TEXT NOT NULL CHECK(status IN ('AI_CANDIDATE','HUMAN_REVIEWED','COMMITTED','REJECTED','STALE')),
  current_revision INTEGER NOT NULL DEFAULT 1, summary TEXT NOT NULL,
  risks_json TEXT NOT NULL DEFAULT '[]', gaps_json TEXT NOT NULL DEFAULT '[]',
  committed_by TEXT REFERENCES users(id), committed_at TEXT,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(project_id,qa_code), UNIQUE(ai_run_id)
);

CREATE TABLE qa_scope_revisions (
  id TEXT PRIMARY KEY, qa_scope_id TEXT NOT NULL REFERENCES qa_scopes(id),
  project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL,
  content_json TEXT NOT NULL, edited_by TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK(actor_type IN ('AI','HUMAN','SYSTEM')), created_at TEXT NOT NULL,
  UNIQUE(qa_scope_id,revision)
);

CREATE TABLE validation_items (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  qa_scope_id TEXT NOT NULL REFERENCES qa_scopes(id), validation_code TEXT NOT NULL,
  area TEXT NOT NULL, title TEXT NOT NULL, objective TEXT NOT NULL,
  preconditions_json TEXT NOT NULL DEFAULT '[]', validation_method TEXT NOT NULL, expected_result TEXT NOT NULL,
  validation_type TEXT NOT NULL CHECK(validation_type IN ('FUNCTIONAL','INTEGRATION','SECURITY','DATA','PERFORMANCE','OPERATIONAL','ACCEPTANCE','OTHER')),
  execution_mode TEXT NOT NULL CHECK(execution_mode IN ('MANUAL','AUTOMATED','HYBRID','EXTERNAL')),
  target_type TEXT NOT NULL CHECK(target_type IN ('INTERNAL','QA_AGAIN','MANUAL_EXTERNAL')),
  binding_id TEXT REFERENCES qa_bindings(id), external_id TEXT, external_url TEXT,
  required_evidence_types_json TEXT NOT NULL DEFAULT '[]', priority TEXT NOT NULL CHECK(priority IN ('HIGH','MEDIUM','LOW')),
  severity_if_failed TEXT NOT NULL CHECK(severity_if_failed IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  owner_role TEXT NOT NULL, owner_id TEXT REFERENCES users(id), required_for_acceptance INTEGER NOT NULL DEFAULT 1,
  candidate_status TEXT NOT NULL CHECK(candidate_status IN ('ACTIVE','REJECTED')),
  materialization_status TEXT NOT NULL CHECK(materialization_status IN ('DRAFT','READY','CONFIRMED','BLOCKED','FAILED','UNCONFIRMED')),
  execution_status TEXT NOT NULL CHECK(execution_status IN ('NOT_STARTED','IN_PROGRESS','PASS','FAIL','BLOCKED','SKIPPED')),
  origin TEXT NOT NULL CHECK(origin IN ('AI','HUMAN')), current_revision INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(project_id,validation_code), UNIQUE(target_type,binding_id,external_id)
);

CREATE TABLE validation_item_revisions (
  id TEXT PRIMARY KEY, validation_item_id TEXT NOT NULL REFERENCES validation_items(id),
  project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL,
  content_json TEXT NOT NULL, edited_by TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK(actor_type IN ('AI','HUMAN','SYSTEM')), created_at TEXT NOT NULL,
  UNIQUE(validation_item_id,revision)
);

CREATE TABLE validation_item_requirements (
  validation_item_id TEXT NOT NULL REFERENCES validation_items(id),
  requirement_revision_id TEXT NOT NULL REFERENCES requirement_revisions(id),
  criterion_index INTEGER NOT NULL DEFAULT -1,
  PRIMARY KEY(validation_item_id,requirement_revision_id,criterion_index)
);
CREATE TABLE validation_item_delivery_links (
  validation_item_id TEXT NOT NULL REFERENCES validation_items(id),
  delivery_item_id TEXT NOT NULL REFERENCES delivery_plan_revision_items(id),
  PRIMARY KEY(validation_item_id,delivery_item_id)
);
CREATE TABLE validation_item_execution_links (
  validation_item_id TEXT NOT NULL REFERENCES validation_items(id),
  execution_item_id TEXT NOT NULL REFERENCES execution_items(id),
  PRIMARY KEY(validation_item_id,execution_item_id)
);

CREATE TABLE validation_results (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  validation_item_id TEXT NOT NULL REFERENCES validation_items(id), result_no INTEGER NOT NULL,
  result TEXT NOT NULL CHECK(result IN ('PASS','FAIL','BLOCKED','SKIPPED')),
  observed_result TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
  source_type TEXT NOT NULL CHECK(source_type IN ('MANUAL','AUTOMATED_INTERNAL','QA_AGAIN','EXTERNAL')),
  source_reference TEXT, executed_by TEXT NOT NULL, actor_type TEXT NOT NULL CHECK(actor_type IN ('HUMAN','SYSTEM','SERVICE')),
  executed_at TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('CURRENT','SUPERSEDED','INVALIDATED')),
  created_at TEXT NOT NULL, UNIQUE(validation_item_id,result_no)
);

CREATE TABLE evidence_records (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), evidence_code TEXT NOT NULL,
  classification TEXT NOT NULL CHECK(classification IN ('TEST','INTERNAL','CUSTOMER')),
  evidence_type TEXT NOT NULL CHECK(evidence_type IN ('SCREENSHOT','LOG','REPORT','DOCUMENT','API_RESPONSE','RECORD','APPROVAL','LINK','OTHER')),
  validation_item_id TEXT REFERENCES validation_items(id), validation_result_id TEXT REFERENCES validation_results(id),
  execution_item_id TEXT REFERENCES execution_items(id), title TEXT NOT NULL, description TEXT NOT NULL,
  storage_reference TEXT NOT NULL, external_reference TEXT, content_text TEXT,
  content_sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('VALID','INVALID','STALE','MISSING','SUPERSEDED')),
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(project_id,evidence_code)
);
CREATE TABLE evidence_requirement_links (
  evidence_id TEXT NOT NULL REFERENCES evidence_records(id),
  requirement_revision_id TEXT NOT NULL REFERENCES requirement_revisions(id),
  PRIMARY KEY(evidence_id,requirement_revision_id)
);
CREATE TABLE evidence_status_history (
  id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL REFERENCES evidence_records(id),
  project_id TEXT NOT NULL REFERENCES projects(id), status TEXT NOT NULL,
  reason TEXT NOT NULL, changed_by TEXT NOT NULL, changed_at TEXT NOT NULL
);

CREATE TABLE acceptance_packages (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), version INTEGER NOT NULL,
  requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id),
  delivery_baseline_id TEXT NOT NULL REFERENCES delivery_baselines(id),
  qa_scope_id TEXT NOT NULL REFERENCES qa_scopes(id), qa_scope_revision INTEGER NOT NULL,
  execution_snapshot_hash TEXT NOT NULL, validation_snapshot_hash TEXT NOT NULL,
  ai_run_id TEXT REFERENCES qa_ai_runs(id),
  status TEXT NOT NULL CHECK(status IN ('CURRENT','STALE','REJECTED')),
  executive_summary TEXT NOT NULL, requirement_summary_json TEXT NOT NULL,
  validation_summary_json TEXT NOT NULL, evidence_summary_json TEXT NOT NULL, execution_summary_json TEXT NOT NULL,
  critical_failures_json TEXT NOT NULL, critical_blockers_json TEXT NOT NULL,
  missing_evidence_json TEXT NOT NULL, residual_risks_json TEXT NOT NULL,
  recommendation TEXT NOT NULL CHECK(recommendation IN ('RECOMMEND_ACCEPT','RECOMMEND_ACCEPT_WITH_CONDITIONS','RECOMMEND_NOT_ACCEPT','NO_AI_RECOMMENDATION')),
  recommendation_basis TEXT NOT NULL, generated_by TEXT NOT NULL, generated_at TEXT NOT NULL,
  UNIQUE(project_id,version), UNIQUE(ai_run_id)
);

CREATE TABLE acceptance_exceptions (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  validation_item_id TEXT NOT NULL REFERENCES validation_items(id),
  validation_result_id TEXT NOT NULL REFERENCES validation_results(id),
  reason TEXT NOT NULL, risk TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED','SUPERSEDED')),
  requested_by TEXT NOT NULL, approved_by TEXT REFERENCES users(id), requested_at TEXT NOT NULL, decided_at TEXT
);

CREATE TABLE final_acceptances (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), version INTEGER NOT NULL,
  acceptance_code TEXT NOT NULL, status TEXT NOT NULL CHECK(status='ACCEPTED'),
  requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id), requirement_baseline_version INTEGER NOT NULL,
  delivery_baseline_id TEXT NOT NULL REFERENCES delivery_baselines(id), delivery_baseline_version INTEGER NOT NULL,
  execution_snapshot_hash TEXT NOT NULL, qa_scope_id TEXT NOT NULL REFERENCES qa_scopes(id), qa_scope_revision INTEGER NOT NULL,
  acceptance_package_id TEXT NOT NULL REFERENCES acceptance_packages(id), acceptance_package_version INTEGER NOT NULL,
  membership_hash TEXT NOT NULL, acceptance_comment TEXT NOT NULL,
  accepted_by TEXT NOT NULL REFERENCES users(id), accepted_at TEXT NOT NULL,
  UNIQUE(project_id,version), UNIQUE(project_id,membership_hash)
);
CREATE TABLE final_acceptance_validation_results (
  final_acceptance_id TEXT NOT NULL REFERENCES final_acceptances(id),
  validation_result_id TEXT NOT NULL REFERENCES validation_results(id),
  PRIMARY KEY(final_acceptance_id,validation_result_id)
);
CREATE TABLE final_acceptance_evidence (
  final_acceptance_id TEXT NOT NULL REFERENCES final_acceptances(id),
  evidence_id TEXT NOT NULL REFERENCES evidence_records(id),
  PRIMARY KEY(final_acceptance_id,evidence_id)
);
CREATE TABLE final_acceptance_exceptions (
  final_acceptance_id TEXT NOT NULL REFERENCES final_acceptances(id),
  acceptance_exception_id TEXT NOT NULL REFERENCES acceptance_exceptions(id),
  PRIMARY KEY(final_acceptance_id,acceptance_exception_id)
);

CREATE INDEX idx_qa_scopes_project ON qa_scopes(project_id,status);
CREATE INDEX idx_validation_items_scope ON validation_items(qa_scope_id,candidate_status);
CREATE INDEX idx_validation_results_item ON validation_results(validation_item_id,result_no);
CREATE INDEX idx_evidence_project ON evidence_records(project_id,status);
CREATE INDEX idx_acceptance_packages_project ON acceptance_packages(project_id,version);
CREATE INDEX idx_final_acceptances_project ON final_acceptances(project_id,version);
