# Phase 2 AI Delivery Plan Flow

```text
exact Requirement Baseline + current committed solution revision
→ DeliveryPlanOutput
→ validate refs, ownership fields, criteria, milestones and acyclic dependencies
→ non-authoritative plan candidate
→ human structured edit/add/remove/dependency change/reject/regenerate
→ explicit plan commit + relational materialization + readback
```

Items cite exact requirement revision IDs and selected solution component refs.
Unknown/cross-project references, self-dependencies, cycles, duplicate item refs and
invalid milestone membership fail closed. Effort is an S/M/L/XL class and timeline
entries are assumptions, not promises. A solution revision change makes prior plan
candidates and committed plans stale.
