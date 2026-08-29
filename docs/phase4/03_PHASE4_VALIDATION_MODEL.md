# Phase 4 Validation Model

Committed active items materialize through a capability-declared validation target. Internal materialization creates an authoritative OIDA record, uses an idempotency key, and must pass read-after-write confirmation. Failed, blocked, and unconfirmed target operations remain visible; OIDA never silently reroutes them.

Each run appends a `validation_results` row with a monotonically increasing result number. The previous row is retained as superseded history and the new row becomes current. Required items pass Gate 3 only with current `PASS`, unless the project owner explicitly approves an exception for an actual current `FAIL` or `BLOCKED` result. Required `SKIPPED` is not treated as pass.

Manual result entry requires an authenticated human. Automated or external result ingestion is denied until a trusted service identity and replay-safe ingestion boundary exist.

