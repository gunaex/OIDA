# PM Materialization

The delivery baseline and reviewed materialization plan remain authoritative in OIDA. Only an authorized plan may create PM tasks. Each request carries a stable `plan:item` lineage marker; retries search for that marker before creating. Create success is provisional until readback.

Timeouts are UNCONFIRMED/reconcilable. Reconciliation detects missing external tasks, scope/owner drift, stale status, and unlinked execution. Unsupported native dependency/milestone capabilities are visible rather than silently treated as delivered.
