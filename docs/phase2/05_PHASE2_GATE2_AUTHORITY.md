# Phase 2 Gate 2 Authority

Gate 2 readiness is deterministic. It requires:

- the latest frozen Requirement Baseline;
- a committed current solution grounded in that exact baseline;
- a committed current plan grounded in that solution revision and baseline;
- no `REQUIRED_BEFORE_BASELINE` solution decision;
- every Must requirement covered;
- valid plan ownership, trace refs, milestones and acyclic dependencies.

Only a HUMAN `PROJECT_OWNER` can freeze Gate 2. AI can prepare candidates only; it
cannot select, commit or freeze. Freeze requires an idempotency key, writes an audit
request and result, stores exact Requirement Baseline, solution revision and plan
revision IDs, then reconciles those IDs by readback. A failed check returns explicit
blockers and does not create a partial baseline.

Every protected route first resolves signed identity and exact project membership.
Queries and actions carry `project_id`; unauthorized projects return 404. Provider
choice and credentials stay server-side. Authority, state transitions, integrity,
staleness and immutability are never delegated to AI or the browser.
