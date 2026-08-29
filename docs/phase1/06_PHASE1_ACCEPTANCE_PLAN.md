# Phase 1 Acceptance Plan

Automated suites cover AI schema/failure contracts, candidate non-authority,
edit/reject/regenerate/accept/manual creation, idempotent generation/accept/freeze,
requirement revisions, exact immutable baseline membership, Project Truth,
context staleness, missing authorization, cross-project reads/writes, member and AI
freeze denial, invalid project references, and read-after-write confirmation.

The canonical project is Customer Self-Service Portal with invoice, support,
RBAC, audit, responsive UI, and billing-source constraints. Its business flow is:
sign in → create → add context → generate structured candidates → edit one → reject
one → accept one → add manual requirement → freeze → retrieve exact baseline → edit
working requirement → prove frozen member unchanged → see Gate 1 complete in Truth.

Live AI is separate from deterministic acceptance. If `OPENAI_API_KEY` is not
available, report `LIVE_AI_ACCEPTANCE=BLOCKED_NOT_CONFIGURED`; do not convert fake
adapter success into a live-provider claim.

### Phase 1 trace matrix

| Requirement | Relevance | Implementation / test | Status |
|---|---|---|---|
| OIDA-FR-001 | Direct | project frame/create; golden flow | PASS |
| OIDA-FR-002 | Direct | context items/revisions/provenance | PASS |
| OIDA-AI-001 | Slice | requirement first-pass adapter | PASS |
| OIDA-AI-002 | Direct | findings and grounded candidate analysis | PASS |
| OIDA-FR-003 | Direct | structured candidate/requirement schema | PASS |
| OIDA-AUTH-001 | Direct | edit/reject/regenerate/accept | PASS |
| OIDA-AI-003 | Optional | explicit alternative/compare mode | DEFERRED |
| OIDA-AI-004 | Direct | exact context source IDs + grounding validation | PASS |
| OIDA-AI-005 | Direct | disabled/timeout/invalid/incomplete/grounding states | PASS |
| OIDA-AUTO-001 | Slice | human Gate 1; AI L2 only | PASS |
| OIDA-AUTH-002 | Direct | human-owner freeze | PASS |
| OIDA-GOV-001 | Direct | AI/action audit records | PASS |
| OIDA-FR-004 | No | Gate 2 delivery baseline | DEFERRED |
| OIDA-FR-005 | Pattern | idempotency and reconciliation on Phase 1 owner writes | PASS |
| OIDA-INT-001 | Slice | explicit local project scope; no fake external bindings | PASS |
| OIDA-FR-006 | Slice | Gate-1 Project Truth/next action | PASS |
| OIDA-AI-006 | Slice | context gaps/stale/blocker attention | PASS |
| OIDA-FR-007 | No | QA/evidence classification | DEFERRED |
| OIDA-FR-008 | No | Gate 3 package | DEFERRED |
| OIDA-AUTH-003 | No | final acceptance | DEFERRED |
| OIDA-NFR-002 | Direct | fail-closed session/membership/project isolation tests | PASS |
| OIDA-AI-007 | No | P1 change impact | DEFERRED |
| OIDA-UX-001 | Slice | minimal derived Needs Attention only | PASS |
| OIDA-AI-008 | No | persistent memory | DEFERRED |
| OIDA-INT-002 | No | PM/QA sync | DEFERRED |
| OIDA-NFR-001 | Partial | workflow correctness tests; product value metrics need pilot | PARTIAL |
| OIDA-FR-009 | No | portfolio | DEFERRED |
| OIDA-AI-009 | No | agent teams | DEFERRED |

