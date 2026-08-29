# Phase 3 Materialization Model

An AI run receives only the exact frozen source packet: baseline/version,
Requirement Baseline, solution revision, delivery-plan revision, delivery items,
dependencies, milestones and target capabilities. Output must cover all and only
the supplied item refs and may use only supplied dependency/milestone refs.

The plan is non-authoritative `NEEDS_REVIEW` work. Human edits create immutable
snapshots; routing, role, priority, milestone, dependency, enable/disable,
split/merge and manual mappings are supported. Rejection is audited. If AI fails,
a human can create an empty manual plan and add mappings.

One project owner batch-authorizes ready mappings. Blocked mappings stay visible
and excluded. Materialization is per-item rather than a distributed transaction:
confirmed, failed, unconfirmed and blocked counts determine `MATERIALIZED` versus
`PARTIAL`. The semantic plan/item key and database uniqueness make retry safe.
