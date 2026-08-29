# Phase 4 Architecture

The browser workspace calls action-oriented FastAPI use cases. `phase4.py` owns QA, validation, evidence, package, and Gate 3 policy; `ai.py` owns provider-neutral structured AI contracts; `validation_targets.py` owns target capabilities and read-after-write behavior. Migration 005 adds normalized, project-scoped tables rather than a generic JSON object store.

The flow is:

```text
Frozen baselines + Execution Truth
  → advisory QA candidate
  → human-reviewed committed QA Scope
  → target materialization/readback
  → append-only observations and evidence
  → deterministic readiness snapshot
  → advisory or manual Acceptance Package
  → owner-only immutable Final Acceptance
```

Every transition revalidates project ownership and exact source IDs. Staleness is computed from the frozen delivery membership and an Execution Truth snapshot hash.

