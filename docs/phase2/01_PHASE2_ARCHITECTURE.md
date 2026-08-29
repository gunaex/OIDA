# Phase 2 Architecture

```text
Browser: Solution / Delivery / Project Truth
        │ signed session + project-scoped actions
        ▼
FastAPI Phase 2 router
  ├─ deterministic lineage, coverage, dependency and gate validation
  ├─ provider-neutral AI adapter (disabled | fake-test | OpenAI)
  ├─ append-only candidate/committed revisions
  └─ SQLite relational records + audit + idempotency
```

`app/phase2.py` contains the new bounded use cases and routes. Phase 1 routes stay
in `app/main.py`; the only integration is router registration and a derived Phase 2
Project Truth projection. `app/ai.py` extends the existing provider boundary with
solution and delivery-plan contracts. `002_phase2_delivery_design.sql` is additive;
the accepted Phase 1 migration is unchanged.

The optional live adapter uses the OpenAI Responses API with strict Structured
Outputs. Static policy is in the developer message, dynamic baseline/solution data
is explicitly untrusted, and the application revalidates exact IDs and graph
integrity. The server chooses provider/model and keeps credentials server-side.
