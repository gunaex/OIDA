# Phase 4 Gate 3 Authority

Gate 3 readiness is an application use case, never a frontend or model calculation. It blocks missing execution truth, stale QA, required result gaps, current FAIL/BLOCKED/SKIPPED, missing current-result evidence, invalid evidence, critical drift, unhealthy execution, absent package, and stale package.

Only an authenticated human `PROJECT_OWNER` can commit QA, decide exceptions, or perform Final Acceptance. AI and project members are denied. Final Acceptance stores exact baseline versions, Execution Truth hash, QA Scope revision, Acceptance Package version, current result IDs, current evidence IDs, approved exception IDs, human comment, actor, timestamp, and a membership hash.

The write is idempotent, reconciled by readback, and exposed through no update/delete API. A later request with different membership conflicts with the existing immutable acceptance.

