# Phase 1 Architecture

```text
Browser workspace
      │ signed session + action APIs
      ▼
FastAPI HTTP / use cases
      ├── deterministic authority, lifecycle, readiness, reconciliation
      ├── Project Truth projection
      ├── RequirementAdapter ── disabled | fake-test | OpenAI
      └── SQLite repository ── versioned records + audit + idempotency
```

`app/main.py` owns application use cases and HTTP translation. `app/auth.py` owns
the replaceable local identity boundary and membership enforcement. `app/ai.py`
owns provider-neutral schemas/adapters. `app/db.py` owns connection, transaction,
and migration mechanics. Business transitions are server-side; the UI never grants
authority.

The Phase 1 AI runtime is a local adapter boundary. The optional live adapter uses
the OpenAI Responses API with Structured Outputs; the deterministic fake exists
only for local demonstration and automated contracts. A future Conductor adapter
can implement the same protocol without changing candidate/commit behavior.

No vector retrieval is needed: all active Phase 1 context is assembled
deterministically and the exact immutable context revision is recorded on each run.

