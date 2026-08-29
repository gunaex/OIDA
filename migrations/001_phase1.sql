PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
  password_hash TEXT NOT NULL, actor_type TEXT NOT NULL CHECK(actor_type='HUMAN'), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, name TEXT NOT NULL, objective TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '', state TEXT NOT NULL CHECK(state='ACTIVE'),
  context_revision INTEGER NOT NULL DEFAULT 0, next_requirement_number INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_memberships (
  project_id TEXT NOT NULL REFERENCES projects(id), user_id TEXT NOT NULL REFERENCES users(id),
  role TEXT NOT NULL CHECK(role IN ('PROJECT_OWNER','PROJECT_MEMBER')),
  PRIMARY KEY(project_id,user_id)
);
CREATE TABLE IF NOT EXISTS project_context_items (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  source_type TEXT NOT NULL CHECK(source_type IN ('PROJECT_OBJECTIVE','PASTED_TEXT','USER_NOTE','DOCUMENT','SYSTEM')),
  title TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE', version INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_runs (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), requested_by TEXT NOT NULL REFERENCES users(id),
  actor_type TEXT NOT NULL CHECK(actor_type='AI'), provider TEXT NOT NULL, model TEXT NOT NULL,
  prompt_version TEXT NOT NULL, instruction TEXT NOT NULL DEFAULT '', context_revision INTEGER NOT NULL,
  status TEXT NOT NULL, failure_code TEXT, findings_json TEXT NOT NULL DEFAULT '[]',
  started_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS requirement_candidates (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), ai_run_id TEXT NOT NULL REFERENCES ai_runs(id),
  title TEXT NOT NULL, statement TEXT NOT NULL, rationale TEXT NOT NULL, priority TEXT NOT NULL,
  category TEXT NOT NULL, acceptance_criteria_json TEXT NOT NULL, source_ids_json TEXT NOT NULL,
  assumptions_json TEXT NOT NULL, gaps_json TEXT NOT NULL, confidence TEXT NOT NULL,
  grounding TEXT NOT NULL, status TEXT NOT NULL, human_modified INTEGER NOT NULL DEFAULT 0,
  current_revision INTEGER NOT NULL DEFAULT 1, original_ai_json TEXT NOT NULL,
  supersedes_candidate_id TEXT REFERENCES requirement_candidates(id), rejection_reason TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_revisions (
  id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES requirement_candidates(id), project_id TEXT NOT NULL REFERENCES projects(id),
  revision INTEGER NOT NULL, content_json TEXT NOT NULL, edited_by TEXT NOT NULL, actor_type TEXT NOT NULL,
  created_at TEXT NOT NULL, UNIQUE(candidate_id, revision)
);
CREATE TABLE IF NOT EXISTS requirements (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), requirement_code TEXT NOT NULL,
  origin TEXT NOT NULL CHECK(origin IN ('AI','HUMAN')), source_candidate_id TEXT REFERENCES requirement_candidates(id),
  status TEXT NOT NULL DEFAULT 'COMMITTED', current_revision INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL, accepted_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(project_id, requirement_code), UNIQUE(source_candidate_id)
);
CREATE TABLE IF NOT EXISTS requirement_revisions (
  id TEXT PRIMARY KEY, requirement_id TEXT NOT NULL REFERENCES requirements(id), project_id TEXT NOT NULL REFERENCES projects(id),
  revision INTEGER NOT NULL, title TEXT NOT NULL, statement TEXT NOT NULL, rationale TEXT NOT NULL,
  priority TEXT NOT NULL, acceptance_criteria_json TEXT NOT NULL, source_ids_json TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(requirement_id, revision)
);
CREATE TABLE IF NOT EXISTS requirement_baselines (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), version INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status='FROZEN'), frozen_by TEXT NOT NULL REFERENCES users(id), frozen_at TEXT NOT NULL,
  UNIQUE(project_id, version)
);
CREATE TABLE IF NOT EXISTS requirement_baseline_members (
  baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id), requirement_id TEXT NOT NULL REFERENCES requirements(id),
  requirement_revision_id TEXT NOT NULL REFERENCES requirement_revisions(id), requirement_code TEXT NOT NULL,
  PRIMARY KEY(baseline_id, requirement_id)
);
CREATE TABLE IF NOT EXISTS audit_events (
  id TEXT PRIMARY KEY, project_id TEXT, actor_id TEXT NOT NULL, actor_type TEXT NOT NULL,
  action TEXT NOT NULL, target_type TEXT NOT NULL, target_id TEXT, result TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency_records (
  project_scope TEXT NOT NULL, actor_id TEXT NOT NULL, action TEXT NOT NULL, idempotency_key TEXT NOT NULL,
  response_json TEXT NOT NULL, created_at TEXT NOT NULL,
  PRIMARY KEY(project_scope, actor_id, action, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_context_project ON project_context_items(project_id);
CREATE INDEX IF NOT EXISTS idx_runs_project ON ai_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_candidates_project ON requirement_candidates(project_id);
CREATE INDEX IF NOT EXISTS idx_requirements_project ON requirements(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_project ON audit_events(project_id);

