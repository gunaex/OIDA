# PM Again Integration

PM Again remains execution owner. OIDA reuses Phase 3 `execution_bindings` and calls the normal project/task contract using an explicitly configured authorized human/API token. It does not impersonate Conductor Main or use PM Again's trusted ecosystem intake route.

Capability truth is partial: owner, priority, status, and stable OIDA lineage are supported; native milestones and dependencies are not claimed. Statuses normalize from Todo/InProgress/Blocked/Done/Cancelled. Materialization still requires OIDA project-owner authorization, uses stable idempotency lineage, and requires readback.
