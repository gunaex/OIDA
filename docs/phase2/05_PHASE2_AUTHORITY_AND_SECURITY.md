# Phase 2 Authority and Security

All Phase 2 routes resolve a signed actor and exact project membership before any
domain query. Every lookup and mutation includes `project_id`; unauthorized access
returns 404 and unauthenticated access returns 401. Provider choice and credentials
are server-controlled. AI input is assembled only from exact authorized records.

AI runs can create candidates, never committed solution/plan truth and never a
baseline. Human users explicitly edit, reject, regenerate, merge, select and commit.
Only a HUMAN `PROJECT_OWNER` can freeze Gate 2. Deterministic code—not AI or UI—
enforces authority, lifecycle, exact lineage, reference integrity, cycles,
staleness, coverage, idempotency, reconciliation and baseline immutability.

Security-relevant denials use the accepted Phase 1 membership boundary. Phase 2
actions and AI run outcomes add project-scoped audit events without storing hidden
reasoning.
