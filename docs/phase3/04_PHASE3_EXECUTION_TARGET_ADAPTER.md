# Phase 3 Execution Target Adapter

The target contract exposes capabilities and `create_work_item` /
`get_work_item` boundaries. Capability declarations cover owner, priority,
milestone, dependency, custom-field and status-write support.

- `INTERNAL`: full real materialization into OIDA-owned execution records.
- `MANUAL_EXTERNAL`: explicit human reference; no implicit discovery.
- `PM_AGAIN`: explicit project binding and provider contract. The live adapter
  raises `TARGET_UNAVAILABLE` because no clean configured service API is present.

The contract suite proves confirmed readback, timeout, failure, missing readback,
semantic deduplication, modification and deletion. A deterministic external
adapter is test-only and is never reported as live PM Again.

No target failure silently falls back to Internal. Users must explicitly reroute.
