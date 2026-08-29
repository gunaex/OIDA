# Phase 1 Acceptance Results

## Verification executed

```text
PYTHON_COMPILE=PASS
JAVASCRIPT_SYNTAX=PASS
AUTOMATED_TESTS=17_PASS
HTTP_RUNTIME_SMOKE=PASS
LOGIN_RUNTIME_SMOKE=PASS
SECRET_PATTERN_SCAN=PASS
LIVE_AI_ACCEPTANCE=BLOCKED_NOT_CONFIGURED
```

The API Golden Flow used a temporary SQLite database and explicitly configured
deterministic test adapter. It created a project and context, materialized at least
three structured candidates, proved zero automatic requirements, edited/rejected/
accepted candidates, retried acceptance without duplication, created a manual
requirement, froze and read back exact baseline membership, edited a working
requirement, and proved the frozen member revision IDs did not change. Project Truth
then reported `GATE_1_COMPLETE` and only the Phase 2 recommendation.

Security tests proved missing auth=401; unauthorized project reads/writes=404;
context/candidates/requirements do not cross projects; invalid project reference
fails closed; PROJECT_MEMBER freeze=403; AI actor freeze=403. Known-actor denials are
audited.

AI contract tests proved valid schema/provenance and distinct invalid, timeout,
unavailable, context-incomplete, and grounding-insufficient behavior. API failure
evidence proved an unavailable provider records a FAILED AI Run and attention item,
not an empty/success state.

## Acceptance matrix

| Item | Result | Evidence |
|---|---|---|
| PROJECT_CREATE | PASS | API/UI create + idempotent readback |
| PROJECT_ACCESS_ISOLATION | PASS | cross-project security tests |
| CONTEXT_CREATE | PASS | context action + Golden Flow |
| CONTEXT_REVISION | PASS | update/stale test |
| AI_REQUIREMENT_GENERATION | PASS | provider contract + candidate materialization |
| AI_SCHEMA_VALIDATION | PASS | Pydantic contract/error tests |
| AI_PROVENANCE | PASS | exact supplied context IDs validated/stored |
| AI_FAILURE_HANDLING | PASS | five explicit failure classes and failed-run truth |
| CANDIDATE_EDIT | PASS | append revision/human-modified test |
| CANDIDATE_ACCEPT | PASS | creates one committed requirement |
| CANDIDATE_REJECT | PASS | remains historical/non-authoritative |
| CANDIDATE_REGENERATE | PASS | old preserved/superseded, new run/candidates |
| MANUAL_REQUIREMENT | PASS | HUMAN-origin committed requirement |
| IDEMPOTENT_ACCEPT | PASS | same key/same requirement; unique candidate binding |
| REQUIREMENT_VERSIONING | PASS | revision 2 append |
| BASELINE_READINESS | PASS | deterministic blockers and ready result |
| BASELINE_HUMAN_AUTHORITY | PASS | member and AI actor denied |
| BASELINE_FREEZE | PASS | FROZEN v1 and deliberate action surface |
| BASELINE_IMMUTABILITY | PASS | exact member revision IDs unchanged after edit |
| READ_AFTER_WRITE_RECONCILIATION | PASS | project, accept, and freeze readbacks |
| PROJECT_TRUTH | PASS | actual records derive compact Gate-1 projection |
| NEEDS_ATTENTION | PASS | candidate/stale/failure/readiness-derived items |
| FULL_GOLDEN_FLOW | PASS | canonical end-to-end acceptance test |

No live-provider credential was present. `LIVE_AI_ACCEPTANCE` is therefore blocked,
not passed and not replaced by a fake result.

