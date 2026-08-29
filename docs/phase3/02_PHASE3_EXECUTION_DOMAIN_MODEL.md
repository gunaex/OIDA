# Phase 3 Execution Domain Model

`execution_items` are actual work records, not AI candidates. Stable `EXEC-nnn`
codes are project-local. Each materialized item stores the exact materialization
item, frozen delivery item and delivery-plan revision, target/binding/external
identity, expected authorized fields, observed reconciliation state and revision.

Internal status is OIDA-authoritative: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`,
`COMPLETED`, or `CANCELLED`. External status is a projection owned by the target.
Manual work starts `UNLINKED` until a human links it to an item in the current
frozen Delivery Baseline.

Revisions preserve practical internal edit history. Unique materialization-item
and target identity constraints prevent duplicates. Gate 2 rows and upstream
revisions are referenced, never modified.
