# Phase 3 Architecture

```text
Frozen Delivery Baseline
        ↓ exact revision packet
Materialization AI adapter (advisory)
        ↓ schema + domain validation
Versioned Materialization Plan
        ↓ human review and owner authorization
Materialization use case
        ↓
ExecutionTargetAdapter
  ├─ InternalExecutionAdapter (authoritative OIDA records)
  ├─ PmAgainExecutionAdapter (honest unavailable boundary)
  └─ ManualExternalAdapter (explicit reference)
        ↓ create → read authoritative item
Execution projection → reconciliation → drift → Project Truth
```

External writes occur only through the adapter/use-case boundary. Every query and
record is project-scoped. SQLite remains sufficient for this slice; no vector DB,
graph DB, event bus or workflow engine is required.

The PM Again repository was inspected read-only. Its task APIs depend on an
interactive human session and no configured service task-write runtime was found,
so application code was neither copied nor ported.
