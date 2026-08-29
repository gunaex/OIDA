PRAGMA foreign_keys = ON;

CREATE TABLE document_bindings (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  provider TEXT NOT NULL CHECK(provider='DOCUMENT_AGAIN'),
  external_project_id TEXT NOT NULL,
  external_project_name TEXT,
  status TEXT NOT NULL CHECK(status IN ('UNBOUND','INVALID','READY','PARTIAL','STALE','ERROR')),
  failure_code TEXT,
  last_verified_at TEXT,
  created_by TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id,provider)
);

CREATE TABLE document_source_refs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  binding_id TEXT NOT NULL REFERENCES document_bindings(id),
  context_item_id TEXT NOT NULL REFERENCES project_context_items(id),
  external_document_id TEXT NOT NULL,
  external_document_title TEXT NOT NULL,
  external_revision_id TEXT NOT NULL,
  external_revision_number INTEGER,
  content_sha256 TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('READY','STALE','ERROR','DISCONNECTED')),
  last_checked_at TEXT,
  imported_by TEXT NOT NULL REFERENCES users(id),
  imported_at TEXT NOT NULL,
  UNIQUE(binding_id,external_document_id,external_revision_id)
);

CREATE TABLE integration_events (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  provider TEXT NOT NULL,
  operation TEXT NOT NULL,
  status TEXT NOT NULL,
  duration_ms REAL,
  failure_code TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_document_bindings_project ON document_bindings(project_id);
CREATE INDEX idx_document_refs_project ON document_source_refs(project_id,status);
CREATE INDEX idx_integration_events_project ON integration_events(project_id,created_at);
