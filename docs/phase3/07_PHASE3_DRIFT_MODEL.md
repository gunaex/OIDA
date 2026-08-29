# Phase 3 Drift Model

Deterministic drift types are `MISSING_EXECUTION`, `EXTERNAL_ITEM_MISSING`,
`SCOPE_DRIFT`, `OWNER_DRIFT`, `DEPENDENCY_DRIFT`, `MILESTONE_DRIFT`,
`UNLINKED_EXECUTION` and `STATUS_STALE`. Severity is INFO, WARNING or CRITICAL.

Stable project-scoped detection keys deduplicate recurring findings. Open drift
may be acknowledged by a human, but acknowledgement does not change the frozen
baseline or target work. A later clean reconciliation resolves records that are no
longer applicable. High-impact drift is never auto-fixed.

The live golden flow changed one Internal owner, detected one `OWNER_DRIFT`,
recorded a partial reconciliation, acknowledged it, restored the authorized owner
and then resolved the record with a 24/24 clean reconciliation.
