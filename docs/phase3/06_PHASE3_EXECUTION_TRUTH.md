# Phase 3 Execution Truth

Execution Truth is derived, not manually painted green. It exposes frozen source
identity, plan status, materialized/total/unmaterialized counts, binding state,
execution statuses, reconciliation counts, freshness, drift, blockers, health and
the next useful action. The same projection extends Project Truth.

The workspace Execution screen shows what will be created, target, owner role,
priority, milestone, warnings and state; after materialization it shows actual
execution, external link where present, reconciliation and drift. It focuses on
exceptions rather than requiring approval of every correct mapping.

Phase 4 is recommended only when all frozen source items have execution coverage,
no active blocker remains and reconciliation is healthy. This recommendation does
not perform QA, evidence acceptance or Gate 3.
