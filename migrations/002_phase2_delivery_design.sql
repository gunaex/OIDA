PRAGMA foreign_keys = ON;

ALTER TABLE projects ADD COLUMN next_solution_number INTEGER NOT NULL DEFAULT 1;
ALTER TABLE projects ADD COLUMN next_plan_number INTEGER NOT NULL DEFAULT 1;

CREATE TABLE solution_ai_runs (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  requested_by TEXT NOT NULL REFERENCES users(id), provider TEXT NOT NULL, model TEXT NOT NULL,
  prompt_version TEXT NOT NULL, instruction TEXT NOT NULL DEFAULT '',
  requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id),
  context_revision INTEGER NOT NULL, status TEXT NOT NULL, failure_code TEXT,
  findings_json TEXT NOT NULL DEFAULT '[]', started_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE solution_candidates (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  ai_run_id TEXT REFERENCES solution_ai_runs(id), requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id),
  status TEXT NOT NULL CHECK(status IN ('NEEDS_REVIEW','SELECTED','REJECTED','SUPERSEDED','COMMITTED')),
  title TEXT NOT NULL, summary TEXT NOT NULL, content_json TEXT NOT NULL,
  original_ai_json TEXT NOT NULL, current_revision INTEGER NOT NULL DEFAULT 1,
  human_modified INTEGER NOT NULL DEFAULT 0, recommended INTEGER NOT NULL DEFAULT 0,
  origin TEXT NOT NULL CHECK(origin IN ('AI','HUMAN_MERGE')),
  supersedes_candidate_id TEXT REFERENCES solution_candidates(id), rejection_reason TEXT,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE solution_candidate_revisions (
  id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES solution_candidates(id),
  project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL,
  content_json TEXT NOT NULL, edited_by TEXT NOT NULL, actor_type TEXT NOT NULL,
  created_at TEXT NOT NULL, UNIQUE(candidate_id,revision)
);
CREATE TABLE solutions (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), solution_code TEXT NOT NULL,
  source_candidate_id TEXT NOT NULL REFERENCES solution_candidates(id), status TEXT NOT NULL CHECK(status='COMMITTED'),
  current_revision INTEGER NOT NULL DEFAULT 1, created_by TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(project_id,solution_code), UNIQUE(source_candidate_id)
);
CREATE TABLE solution_revisions (
  id TEXT PRIMARY KEY, solution_id TEXT NOT NULL REFERENCES solutions(id),
  project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL,
  requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id),
  title TEXT NOT NULL, summary TEXT NOT NULL, content_json TEXT NOT NULL,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(solution_id,revision)
);
CREATE TABLE solution_revision_coverage (
  solution_revision_id TEXT NOT NULL REFERENCES solution_revisions(id),
  requirement_revision_id TEXT NOT NULL REFERENCES requirement_revisions(id),
  status TEXT NOT NULL CHECK(status IN ('COVERED','PARTIAL','NOT_COVERED')),
  component_ref TEXT NOT NULL, explanation TEXT NOT NULL,
  PRIMARY KEY(solution_revision_id,requirement_revision_id)
);

CREATE TABLE delivery_plan_ai_runs (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), requested_by TEXT NOT NULL REFERENCES users(id),
  provider TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL, instruction TEXT NOT NULL DEFAULT '',
  requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id),
  solution_revision_id TEXT NOT NULL REFERENCES solution_revisions(id),
  status TEXT NOT NULL, failure_code TEXT, findings_json TEXT NOT NULL DEFAULT '[]',
  started_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE delivery_plan_candidates (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  ai_run_id TEXT REFERENCES delivery_plan_ai_runs(id),
  requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id),
  solution_revision_id TEXT NOT NULL REFERENCES solution_revisions(id),
  status TEXT NOT NULL CHECK(status IN ('NEEDS_REVIEW','REJECTED','SUPERSEDED','COMMITTED')),
  title TEXT NOT NULL, content_json TEXT NOT NULL, original_ai_json TEXT NOT NULL,
  current_revision INTEGER NOT NULL DEFAULT 1, human_modified INTEGER NOT NULL DEFAULT 0,
  origin TEXT NOT NULL CHECK(origin IN ('AI','HUMAN')), supersedes_candidate_id TEXT REFERENCES delivery_plan_candidates(id),
  rejection_reason TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE delivery_plan_candidate_revisions (
  id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES delivery_plan_candidates(id),
  project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL,
  content_json TEXT NOT NULL, edited_by TEXT NOT NULL, actor_type TEXT NOT NULL,
  created_at TEXT NOT NULL, UNIQUE(candidate_id,revision)
);
CREATE TABLE delivery_plans (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), plan_code TEXT NOT NULL,
  source_candidate_id TEXT NOT NULL REFERENCES delivery_plan_candidates(id),
  status TEXT NOT NULL CHECK(status='COMMITTED'), current_revision INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(project_id,plan_code), UNIQUE(source_candidate_id)
);
CREATE TABLE delivery_plan_revisions (
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES delivery_plans(id),
  project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL,
  requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id),
  solution_revision_id TEXT NOT NULL REFERENCES solution_revisions(id),
  title TEXT NOT NULL, content_json TEXT NOT NULL, created_by TEXT NOT NULL,
  created_at TEXT NOT NULL, UNIQUE(plan_id,revision)
);
CREATE TABLE delivery_plan_revision_items (
  id TEXT PRIMARY KEY, plan_revision_id TEXT NOT NULL REFERENCES delivery_plan_revisions(id),
  local_ref TEXT NOT NULL, workstream_ref TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
  owner_role TEXT NOT NULL, acceptance_criteria_json TEXT NOT NULL, effort TEXT NOT NULL,
  requirement_revision_ids_json TEXT NOT NULL, solution_component_refs_json TEXT NOT NULL,
  UNIQUE(plan_revision_id,local_ref)
);
CREATE TABLE delivery_plan_revision_dependencies (
  id TEXT PRIMARY KEY, plan_revision_id TEXT NOT NULL REFERENCES delivery_plan_revisions(id),
  predecessor_ref TEXT NOT NULL, successor_ref TEXT NOT NULL, dependency_type TEXT NOT NULL,
  UNIQUE(plan_revision_id,predecessor_ref,successor_ref)
);
CREATE TABLE delivery_plan_revision_milestones (
  id TEXT PRIMARY KEY, plan_revision_id TEXT NOT NULL REFERENCES delivery_plan_revisions(id),
  local_ref TEXT NOT NULL, title TEXT NOT NULL, exit_criteria_json TEXT NOT NULL,
  item_refs_json TEXT NOT NULL, UNIQUE(plan_revision_id,local_ref)
);
CREATE TABLE delivery_baselines (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), version INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status='FROZEN'),
  requirement_baseline_id TEXT NOT NULL REFERENCES requirement_baselines(id),
  solution_revision_id TEXT NOT NULL REFERENCES solution_revisions(id),
  delivery_plan_revision_id TEXT NOT NULL REFERENCES delivery_plan_revisions(id),
  frozen_by TEXT NOT NULL REFERENCES users(id), frozen_at TEXT NOT NULL,
  UNIQUE(project_id,version)
);

CREATE INDEX idx_solution_runs_project ON solution_ai_runs(project_id);
CREATE INDEX idx_solution_candidates_project ON solution_candidates(project_id);
CREATE INDEX idx_solutions_project ON solutions(project_id);
CREATE INDEX idx_plan_runs_project ON delivery_plan_ai_runs(project_id);
CREATE INDEX idx_plan_candidates_project ON delivery_plan_candidates(project_id);
CREATE INDEX idx_plans_project ON delivery_plans(project_id);
CREATE INDEX idx_delivery_baselines_project ON delivery_baselines(project_id);
