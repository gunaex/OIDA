# OIDA 2.0 Service Boundaries

Boundaries follow product ownership; they do not define the navigation model. MVP
may begin as a modular deployment—the table is logical ownership, not a mandate
for microservices.

| Boundary | Owns | Must not own |
|---|---|---|
| OIDA Core | project workspace/composition, baseline and decision semantics, typed cross-domain links, automation policy, acceptance, context manifests, truth projection | copies of all documents/tasks/tests; model runtime internals |
| Account Again | identities, organizations, memberships, roles, entitlements, access policy primitives | project workflow or artifact approval meaning |
| Document Again | controlled document/artifact content, versions, publication/revision | project truth projection or acceptance decision |
| PM Again | materialized work, milestones, dependencies, execution ownership/status | requirement or solution authority |
| QA Again | validation scope/items, executions, results, defects, QA evidence | business acceptance or risk acceptance |
| Conductor Again | model routing/execution, tool orchestration, grounding support, run telemetry/evaluation | product workflow, baseline/approval semantics, project truth |
| Infra capability | environment/deployment architecture references, readiness dependencies, implementation work, technical evidence required by a delivery baseline | generic asset inventory absent a Golden Flow need |

## Integration contract

OIDA stores stable references, versions, observed timestamps, freshness, and
ownership. Commands carry idempotency keys and expected versions. Reads expose
`READY`, `DEGRADED`, `NOT_CONFIGURED`, `BLOCKED_AUTH`, `WAITING_EXTERNAL`, or
`ERROR`. Conflicts and retries are visible; a successful transport response is not
business success.

## MVP choice

Use OIDA-owned records for the closed loop until an external owner is actually
connected, behind explicit ports. Do not invent six deployed services merely to
match conceptual boundaries. Identity may be external; documents, PM, and QA may
start as referenced adapters or minimal owned modules while preserving future
authority boundaries.

