# OIDA 2.0 Historical Recovery Addendum

## Recovery boundary

Source `/Users/kanphong/OIODA` was inspected read-only at Git head
`f735fc1f05551838723edd3ee561a5c977556e32`. Its initial working tree was clean.
No file was modified, migrated, copied, or ported from it. Only business intent,
acceptance rules, authority boundaries, operational lessons, and failure evidence
were recovered into OIDA 2.0 documentation.

## Historical Sources Reviewed

Thirty meaningful sources were reviewed; generated artifacts, package manifests,
application implementation, and repetitive closure reports were excluded unless
needed to corroborate a requirement.

1. `README.md`
2. `OIDA-1.0-PRODUCTION-BASELINE.md`
3. `OIDA-1.0-RELEASE-NOTES.md`
4. `OIDA-1.0-USER-GUIDE-TH.md`
5. `OIDA-1.0-CAPABILITY-REGISTRY.csv`
6. `OIDA-INTEGRATION-AUDIT.md` and its evidence matrix
7. `OIDA-R17.1.2-CROSS-SERVICE-TRUTH.md`
8. `OIDA-R17.1.3-CAPABILITY-DECISION.md`
9. `OIDA-R17.1.3-PROJECT-ATTENTION.md`
10. `OIDA-R17.2-NEXT-EVOLUTION-DECISION.md`
11. `OIDA-R17.2.1-EVIDENCE-GROUNDED-AI-REVIEWER.md`
12. `OIDA-R17.3-IMPACT-INTELLIGENCE-FOUNDATION.md`
13. `OIDA-R17.4-HUMAN-CONFIRMED-IMPACT-ACTIONS.md`
14. `OIDA-R17.5-CONTROLLED-ACTION-ROUTING.md`
15. `OIDA-R17.6-CHANGE-TO-RESOLUTION-LOOP.md`
16. `OIDA-R18-PROJECT-COMMAND-CENTER.md`
17. `OIDA-R18.1-PORTFOLIO-COMMAND-CENTER.md`
18. `OIDA-R18.2-GROUNDED-DAILY-PROJECT-BRIEFING.md`
19. `OIDA-R18.3-PROACTIVE-RESOLUTION-INTELLIGENCE.md`
20. `OIDA-R19-REAL-PROJECT-DOGFOOD-HARDENING.md`
21. `services/document-again/docs/DOMAIN_MODEL.md`
22. `services/document-again/docs/REVISION_BASELINE_MODEL.md`
23. `services/document-again/docs/TRACEABILITY_MODEL.md`
24. `services/document-again/docs/ECOSYSTEM_HANDOFF_CONTRACT.md`
25. `services/pm-again/README.md` and PM ecosystem integration status
26. QA tester guidance and QA ecosystem integration status
27. Infra capability and AIRLOCK safety models
28. `services/account-again/README.md`
29. Conductor AI execution boundary
30. Conductor orchestration architecture

## Historical Intent Summary

OIDA 1.x attempted to give a human one authorized operating view across governed
documents, planning, QA, infrastructure, identity, and orchestration without
stealing domain truth. Its strongest contribution was integrity: exact-version
baselines, explicit bindings, provenance/freshness, honest partial states,
controlled owner actions, and a rigorous separation between action completion,
resolution, validation, and customer acceptance. It progressively added attention,
change/impact, briefings, portfolio, and cited AI assistance to reduce interpretation
work. Its limitation was structural: the experience accumulated many capabilities
and remained deterministic/manual-first, while AI was optional advice with no
execution authority. OIDA 2.0 preserves the integrity and business loop while
redesigning work preparation and reversible execution around AI.

## Requirement Recovery Matrix

`Action` uses the delta vocabulary requested for Phase 0.1.

| # | Historical intent | Historical source | OIDA 2.0 mapping | Classification | Action | Reason |
|---:|---|---|---|---|---|---|
| 1 | One workspace across delivery domains | Baseline §2; User Guide §§1,5 | Vision; OIDA-FR-006 | REDESIGN | COVERED_BY_EXISTING_REQUIREMENT | Keep one experience, replace module navigation with next-action flow. |
| 2 | Bounded services retain domain truth | Baseline §§3–4; Integration Audit | OIDA-INT-001; service boundaries | KEEP | EXISTING_REQUIREMENT_NEEDS_EXPANSION | Owner/reference model is proven; binding semantics were clarified. |
| 3 | Tenant/project/service access isolation fails closed | Baseline §13; Account; Conductor boundary | OIDA-NFR-002 | KEEP | NEW_REQUIREMENT_REQUIRED | Security was implicit in Phase 0 models but required an explicit testable requirement. |
| 4 | Explicit project bindings; never infer correlation | Cross-Service Truth §§3–4; Integration Audit §§4–6 | OIDA-INT-001 | ALREADY_COVERED | EXISTING_REQUIREMENT_NEEDS_EXPANSION | Existing owner references were correct; acceptance now distinguishes binding failures. |
| 5 | Governed controlled documents and versions | Document domain; Baseline §§4–6 | OIDA-FR-002/003/004 | ALREADY_COVERED | COVERED_BY_EXISTING_REQUIREMENT | Context and baselines cover the intent without reproducing the old document module. |
| 6 | Confirmed revisions and baseline bindings are immutable | Revision/Baseline Model; Baseline §13 | State and Acceptance models | KEEP | COVERED_BY_EXISTING_REQUIREMENT | Exact-version integrity remains a core invariant. |
| 7 | Requirements/designs are structured, stable objects | Document Domain Model | OIDA-FR-003/004; domain model | REDESIGN | COVERED_BY_EXISTING_REQUIREMENT | Retain structure but only promote concepts needed by the Golden Flow. |
| 8 | Stable semantic traceability survives renames/revisions | Traceability Model | OIDA-AI-004; typed-link model | ALREADY_COVERED | COVERED_BY_EXISTING_REQUIREMENT | OIDA 2.0 uses a smaller finite typed-link model. |
| 9 | Decisions, assumptions, clarifications, and changes remain visible | Document domain; User Guide | Project Context/Truth; OIDA-FR-006 | ALREADY_COVERED | COVERED_BY_EXISTING_REQUIREMENT | These are context/truth inputs, not separate approval systems. |
| 10 | Cross-service Project Truth exposes source and freshness | Cross-Service Truth; Baseline §6 | OIDA-INT-001; Project Truth Model | KEEP | COVERED_BY_EXISTING_REQUIREMENT | Historical evidence validates reference-based truth. |
| 11 | EMPTY, UNBOUND, UNKNOWN, PARTIAL, STALE, and failure differ | User Guide §6; Integration Audit §§5–6 | OIDA-AI-005; OIDA-INT-001; state model | KEEP | EXISTING_REQUIREMENT_NEEDS_EXPANSION | Honest states were strengthened in INT-001. |
| 12 | Surface high-value project attention | Project Attention; Command Center | OIDA-AI-006; OIDA-UX-001 | REDESIGN | COVERED_BY_EXISTING_REQUIREMENT | MVP detects gaps; prioritized personal queue remains P1. |
| 13 | Plan/work/schedule/dependency/effort truth belongs to PM | PM sources; Integration Audit §2 | OIDA-FR-004/005; OIDA-INT-001 | ALREADY_COVERED | COVERED_BY_EXISTING_REQUIREMENT | Materialize/reference only the subset required by delivery. |
| 14 | QA owns cases, runs, defects, evidence, sign-off, readiness | QA sources; Integration Audit §2 | OIDA-FR-007/008 | ALREADY_COVERED | EXISTING_REQUIREMENT_NEEDS_EXPANSION | Evidence class and defects were made explicit. |
| 15 | Infrastructure includes architecture, environments, feasibility, safe execution evidence | Infra capability/safety; Integration Audit §2 | delivery baseline; service boundary | REDESIGN | DEFERRED | Keep architecture/readiness needed by a project; broad provider inventory/execution waits for a proven flow. |
| 16 | Handoffs/actions are idempotent and reconciled with owner truth | Handoff Contract; Controlled Action Routing | OIDA-FR-005; OIDA-GOV-001 | KEEP | EXISTING_REQUIREMENT_NEEDS_EXPANSION | Materialization now requires read-after-write reconciliation and honest unknown result. |
| 17 | Reviewer gets exact-version evidence and deterministic change brief | AI Reviewer; Next Evolution Decision | OIDA-AI-004; OIDA-FR-008 | ALREADY_COVERED | COVERED_BY_EXISTING_REQUIREMENT | Grounded candidates and acceptance package generalize this need. |
| 18 | Recorded changes can be compared without invented history | AI Reviewer; Impact Foundation | context versioning; OIDA-AI-004 | ALREADY_COVERED | COVERED_BY_EXISTING_REQUIREMENT | Provenance and stale invalidation retain this invariant. |
| 19 | Typed one-hop impact with explicit/derived/suggested/unknown classes | Impact Foundation | OIDA-AI-007; traceability | LATER | DEFERRED | Narrow change impact is P1; no generic graph in MVP. |
| 20 | Humans confirm/reject uncertain impact relationships | Human-Confirmed Impact Actions | candidate/commit model | REDESIGN | COVERED_BY_EXISTING_REQUIREMENT | General candidate controls replace a bespoke confirmation workflow. |
| 21 | Owner mutations require preview, allowlist, permission, and audit | Controlled Action Routing | OIDA-AUTO-001; OIDA-GOV-001; OIDA-FR-005 | REDESIGN | COVERED_BY_EXISTING_REQUIREMENT | OIDA 2.0 permits reversible L3 execution under policy instead of requiring every click. |
| 22 | Successful action does not imply resolved impact | Change-to-Resolution Loop | state/acceptance models | KEEP | COVERED_BY_EXISTING_REQUIREMENT | Technical, workflow, business, and resolution semantics remain separate. |
| 23 | Command Center answers health, blocker, change, owner, next action | Command Center; User Guide §5 | OIDA-FR-006; Project Truth | ALREADY_COVERED | COVERED_BY_EXISTING_REQUIREMENT | This directly validates the workspace mental model. |
| 24 | Daily/since-review briefing and checkpoints | Daily Briefing | OIDA-UX-001 | LATER | DEFERRED | Useful attention optimization, but no persistent checkpoint needed to prove MVP. |
| 25 | Authorized portfolio prioritization and isolation | Portfolio Command Center | OIDA-FR-009 | LATER | DEFERRED | Correctly outside the single-project closed loop. |
| 26 | AI advice is cited, grounded, fail-safe, and non-authoritative | AI Reviewer; Command Center; Conductor boundary | OIDA-AI-001/004/005; OIDA-AUTH-002 | REDESIGN | COVERED_BY_EXISTING_REQUIREMENT | Preserve safety but expand AI from advice to preparation and reversible execution. |
| 27 | Governance permits waiver/risk/not-applicable with explicit authority | Baseline §§3,13; User Guide §16 | OIDA-AUTH-002/003; Acceptance Model | ALREADY_COVERED | COVERED_BY_EXISTING_REQUIREMENT | Exception policy avoids a universal hard lock or fourth routine gate. |
| 28 | TEST, INTERNAL, and CUSTOMER evidence are not interchangeable | Baseline §§3,13; User Guide §§2,16 | OIDA-FR-007/008; Acceptance Model | KEEP | EXISTING_REQUIREMENT_NEEDS_EXPANSION | Validation evidence classification is now testable in FR-007. |
| 29 | Project export/import and portable evidence packages | README; QA tester guidance | evidence references; later integration | LATER | DEFERRED | Valuable portability, not required for the initial loop. |
| 30 | Search, comments, quick notes, translation, and PWA convenience | User Guide §§3,5 | none in core MVP | DROP | NOT_REQUIRED | Useful UX options do not define the product hypothesis. |
| 31 | Capability/contract registries define a broad product surface | Capability Registry; Baseline §§5–6 | fixed requirements and typed links | DROP | NOT_REQUIRED | Historical numerical parity would revive capability explosion. |
| 32 | Resource, utilization, effort, financial/commercial optimization | PM inventory; Integration Audit | no MVP mapping | LATER | DEFERRED | Requires a validated target user/problem after the core loop. |

### Classification totals

`ALREADY_COVERED=10`, `KEEP=8`, `REDESIGN=7`, `DROP=2`, `LATER=5`.

### Requirement delta totals

- `COVERED_BY_EXISTING_REQUIREMENT=17`
- `EXISTING_REQUIREMENT_NEEDS_EXPANSION=6`
- `NEW_REQUIREMENT_REQUIRED=1`
- `NOT_REQUIRED=2`
- `DEFERRED=6`

Classification and delta action answer different questions but each matrix row has
exactly one value in each column; both sets reconcile independently to 32 intents.

## Important Lessons from OIDA 1.x

1. Honest absence is a feature: empty, unbound, unauthorized, stale, unavailable,
   and unknown must never collapse into a green/zero state.
2. Composition is not ownership. Explicit binding and owner provenance prevent a
   unified workspace from becoming a shared-truth database.
3. A transport/action success cannot prove workflow resolution or business
   acceptance; fresh owner evidence must be re-evaluated.
4. Immutable version/hash lineage is more valuable than proliferating approval
   states and enables grounded AI review.
5. AI grounded on a deterministic evidence pack is safer, but advisory-only AI
   leaves substantial preparation and orchestration work with humans.
6. Real-project dogfood revealed integration/auth/data friction that unit success
   and HTTP 200 responses did not; Phase 1 needs a real vertical scenario early.
7. Capability and contract growth made the system rigorous but harder to experience
   as one flow. OIDA 2.0 must keep contracts subordinate to product outcomes.

## Requirements Added or Modified

### Added

- `OIDA-NFR-002 Access isolation and fail-closed security` makes tenant, project,
  actor, service identity, AI-context isolation, and denial auditing testable.

### Modified

- `OIDA-FR-005` now requires owner-boundary execution, idempotency,
  read-after-write reconciliation, and an explicit unknown-result state.
- `OIDA-INT-001` now requires explicit bindings and distinguishes unbound, invalid,
  unauthorized, unavailable, empty, partial, and stale truth.
- `OIDA-FR-007` now includes defects and evidence class and prohibits treating test
  evidence as internal/customer acceptance evidence.

Requirements changed from 27 to 28: one new MVP requirement and three modified MVP
requirements. No new authority gate or new service is implied.

## Requirements Deliberately Not Carried Forward

- The 31-capability registry and numerous versioned contracts are evidence, not an
  OIDA 2.0 product skeleton.
- Full PM editors, QA administration/runner internals, Infra provider inventory and
  production execution, and specialist import/export remain delegated or deferred.
- Portfolio, daily checkpoints, global search, collaboration threads, quick notes,
  translation, PWA, and dashboard parity are not MVP requirements.
- AI advisory-only and “human must click every write” are not retained. Authority is
  preserved through policy, reversibility, audit, exception review, and L0 gates.
- OIDA 1.x schemas, APIs, database models, state names, service topology, and code
  were not copied or adopted.

## AI-First Transformations

| Historical human work | AI can now do | Human control required | Gate? | Default level |
|---|---|---|---|---|
| Read and decompose briefs | extract structured requirements and gaps | edit/reject/commit baseline | Yes, Gate 1 | L2 |
| Compare documents and assemble sources | create grounded diffs/context manifests | resolve source conflict | No; exception | L4/L2 |
| Draft UR/DR/architecture separately | prepare one solution/delivery candidate | select/edit/commit | Yes, Gate 2 | L2 |
| Build tasks and tests by hand | materialize idempotent work/validation items | review exceptions/undo | No | L3 |
| Maintain trace links manually | propose grounded typed links and find gaps | correct/commit material links | No | L2/L4 |
| Inspect QA coverage and evidence | generate scope and analyze missing/failed proof | own results and waivers | Waiver only | L2/L4 |
| Check many status screens | summarize Project Truth and detect blocker/drift | resolve exceptions | No | L4 |
| Perform initial change-impact analysis | propose affected items/revalidation | confirm material impact | No; P1 | L2 |
| Assemble acceptance evidence | prepare readiness and frozen package | accept/reject/return | Yes, Gate 3 | L1 |
| Interpret routine owner-action outcomes | reconcile and re-evaluate result | handle unknown/irreversible outcomes | No routine gate | L3/L4 |

## Golden Flow Impact

`GOLDEN_FLOW_CHANGED=NO`. Historical evidence strengthens the existing Frame →
Define → Shape/Plan → Execute/Observe → Validate/Accept flow. It adds three
cross-cutting integrity clarifications—access isolation, explicit bindings, and
owner-result reconciliation—but no user stage.

## Authority Gate Review

The three-gate model remains valid:

1. Requirement Baseline protects definition authority.
2. Delivery Baseline protects solution/plan/validation commitment.
3. Final Acceptance protects business authority.

No fourth routine gate is justified. Production go-live, destructive Infra change,
commercial commitment, legal approval, and risk waiver are action-specific L0
policies when in scope; they are not additional Golden Flow gates. OIDA 1.x's many
human confirmations can be represented by candidate review, exception handling,
and policy-bounded reversible automation without approval fatigue.

## Open Decision Review

| Decision | Result | Historical evidence / Phase 0.1 disposition |
|---|---|---|
| OD-01 Project archetype | RECOMMEND_DEFAULT | Use a small software-delivery scenario with migration characteristics; OIDA 1.x proved migration exercises cross-domain truth but was operationally broad. |
| OD-02 Authority roles | RECOMMEND_DEFAULT | Start with the five defined roles; permit combination except when evidence/security policy requires separation. |
| OD-03 Source formats/connectors | RECOMMEND_DEFAULT | Text/PDF plus structured entry; add one connector only for the proof scenario. |
| OD-04 Launch ownership | RECOMMEND_DEFAULT | Preserve logical Account/Document/PM/QA/Conductor ownership through modular ports; deployment decomposition remains an architecture decision. |
| OD-05 Model/provider constraints | REMAIN_OPEN | Historical provider-not-configured evidence validates graceful failure but cannot choose residency/cost/provider. |
| OD-06 Evidence integrity | RECOMMEND_DEFAULT | Immutable version/hash references and explicit evidence class by default; retention/regulatory profile remains open only if target market requires it. |
| OD-07 Value targets | REMAIN_OPEN | History offers operational evidence, not a manual-effort baseline for AI-first value. |
| OD-08 Baseline approval | RESOLVED | Role-checked activation with immutable revision; signatures/separation only by policy. |
| OD-09 External writes | RESOLVED | One owner per domain, owner API only, idempotency and reconciliation; no dual-write authority. |
| OD-10 Finding thresholds | REMAIN_OPEN | Tune with Phase 1 evaluation/pilot evidence. |
| OD-11 Historical sources | RESOLVED | `/Users/kanphong/OIODA` at the recorded head is the reviewed historical baseline. |

None of the remaining open decisions reveals a flaw in purpose, Golden Flow,
authority, context, truth, ownership, or MVP boundary. They do not block Phase 1;
they become inception/evaluation decisions.

## Phase 0.1 Historical Recovery Final Report

```text
HISTORICAL_RECOVERY=PASS
HISTORICAL_SOURCES=30
HISTORICAL_INTENTS_RECOVERED=32

ALREADY_COVERED=10
KEEP=8
REDESIGN=7
DROP=2
LATER=5

EXISTING_REQUIREMENTS_BEFORE=27
EXISTING_REQUIREMENTS_AFTER=28
NEW_REQUIREMENTS=1
MODIFIED_REQUIREMENTS=3

GOLDEN_FLOW_CHANGED=NO
AUTHORITY_GATES_BEFORE=3
AUTHORITY_GATES_AFTER=3

AI_FIRST_DIRECTION_PRESERVED=YES
MVP_REVALIDATED=YES

APPLICATION_CODE_ADDED=NO

PHASE_0_ACCEPTANCE=PASS
PHASE_1_READY=YES
```

Important recovered intent is integrity across bounded truth, exact versions,
controlled owner actions, and acceptance evidence. Capability/module parity,
advisory-only AI, and approval-per-action were deliberately not carried forward.
One security requirement was added and three requirements were strengthened. The
Golden Flow and three authority gates survived review unchanged. Phase 1 can begin
with the remaining provider, metrics, and tuning choices handled during inception.
