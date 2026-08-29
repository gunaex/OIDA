# Phase 2 Acceptance Plan

Automated acceptance covers Phase 1 regression; Gate 1 prerequisite; 2–3 distinct
alternatives and single recommendation; exact baseline/coverage provenance; human
edit/reject/regenerate/select/merge/commit; idempotency; committed solution
revisioning; solution/plan staleness; plan structure and manual item changes;
unknown, self and cyclic dependencies; exact Gate 2 membership/readback/
immutability; Project Truth; missing authentication, cross-project isolation and
AI freeze denial.

The canonical flow is secure Customer Portal: Gate 1 → alternatives → human
selection/commit → generated plan → human plan revision → plan commit → readiness
→ Gate 2 freeze → exact readback → later solution revision → prove frozen Gate 2
membership unchanged.

Live-provider acceptance is separate. Without `OPENAI_API_KEY`, structural tests
use the explicitly labeled deterministic adapter and the release reports
`LIVE_AI_ACCEPTANCE=BLOCKED_NOT_CONFIGURED`, never a fake live pass.

| Requirement | Phase 2 evidence | Status |
|---|---|---|
| OIDA-AI-001/003/004/005 | structured alternatives/plan, grounding, failures | PASS structural |
| OIDA-AUTH-001/002 | candidate controls; human-only Gate 2 | PASS |
| OIDA-GOV-001 | run/action provenance and audit | PASS |
| OIDA-FR-004 | combined exact delivery baseline | PASS |
| OIDA-FR-005 | execution materialization | DEFERRED Phase 3 |
| OIDA-INT-001 | local explicit project truth/no fake binding | PASS slice |
| OIDA-FR-006/OIDA-AI-006 | truth/stale/blocker attention | PASS slice |
| OIDA-NFR-002 | fail-closed scope/isolation | PASS |
| OIDA-NFR-001 | structural validity metrics only | PARTIAL; pilot/live eval open |
