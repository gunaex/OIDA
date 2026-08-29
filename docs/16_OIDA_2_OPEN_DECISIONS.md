# OIDA 2.0 Open Decisions

Phase 0.1 distinguishes product blockers from choices that can be made during
Phase 1 inception. Historical evidence resolved two decisions and supplied five
recommended defaults. Three decisions remain open; none reveals a material flaw in
the Phase 0 product model and none blocks Phase 1.

| ID | Decision | Phase 0.1 result | Decision/default and rationale | Owner | Needed by |
|---|---|---|---|---|---|
| OD-01 | First real MVP project archetype | RECOMMEND_DEFAULT | Small internal software delivery with migration characteristics and explicit acceptance. OIDA 1.x migration dogfood proved cross-domain value but was too broad for the first slice. | Product sponsor | Phase 1 inception |
| OD-02 | Initial authority roles | RECOMMEND_DEFAULT | Project owner, requirement approver, delivery approver, QA owner, acceptance authority; combinations allowed unless evidence/security policy requires separation. | Governance/product | workflow design |
| OD-03 | Source formats and connectors | RECOMMEND_DEFAULT | Text/PDF upload and structured entry; one connector only when required by the proof scenario. | Product/technical | prototype scope |
| OD-04 | System ownership at launch | RECOMMEND_DEFAULT | Preserve logical Account/Document/PM/QA/Conductor ownership behind modular ports. Do not infer a microservice deployment requirement from history. | Architecture | architecture baseline |
| OD-05 | Model/provider constraints | REMAIN_OPEN | Decide residency, model support, cost, latency, availability, and tool permissions. Historical provider absence proves the need for graceful failure, not a provider choice. | Security/platform | AI spike |
| OD-06 | Evidence integrity | RECOMMEND_DEFAULT | Immutable version/hash references and explicit evidence class. Decide retention/signature/regulatory profile only from the chosen market/use case. | QA/legal | acceptance design |
| OD-07 | MVP value targets | REMAIN_OPEN | Set preparation-time reduction, correction, grounded precision, and completion targets after measuring the selected scenario's manual baseline. | Product sponsor | evaluation plan |
| OD-08 | Baseline approval semantics | RESOLVED | Role-checked activation creates an immutable baseline revision; signatures and separation of duties are optional policy. | Governance | closed in Phase 0.1 |
| OD-09 | External write policy | RESOLVED | One owner per domain; call owner APIs with authorization, idempotency, read-after-write reconciliation, and audit. Never dual-write authority. | Architecture/product | closed in Phase 0.1 |
| OD-10 | AI finding thresholds | REMAIN_OPEN | Establish confidence/severity/deduplication thresholds with Phase 1 evaluation and pilot evidence. | Product/QA | pilot |
| OD-11 | Historical recovery input | RESOLVED | `/Users/kanphong/OIODA` at head `f735fc1f05551838723edd3ee561a5c977556e32` is the reviewed historical baseline. | Product sponsor | closed in Phase 0.1 |

## Phase 1 blocker assessment

`PHASE_1_PRODUCT_BLOCKERS=0`. OD-05, OD-07, and OD-10 are significant but are
normal inception/evaluation decisions and can be closed before their respective
technical spike or pilot. Minor historical uncertainty is recorded in the addendum
and does not block the vertical slice.

