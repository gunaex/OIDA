# Phase 2 Delivery Plan Model

| Record | Invariant |
|---|---|
| Plan AI Run | exact Requirement Baseline and committed solution revision |
| Plan Candidate/Revision | structured, editable and non-authoritative |
| Delivery Plan/Revision | stable `PLAN-nnn`; immutable committed structured revision |
| Revision Item | workstream, owner role, criteria, effort and exact trace refs |
| Revision Dependency | explicit predecessor/successor/type within one plan revision |
| Revision Milestone | exit criteria and exact item refs |

The plan contains workstreams, items, milestones, dependencies, risks, assumptions,
effort classes and timeline assumptions. Items must reference exact baseline
requirement revision IDs and committed solution component refs. Unknown or
cross-project refs, duplicates, self-dependencies, cycles and invalid milestone
membership fail closed.

Humans can edit the whole structure, add/remove items and replace dependencies.
Each change appends a candidate revision. Plan commit materializes queryable item,
dependency and milestone rows and reconciles the exact item count. A solution
revision change makes older candidate/committed plans stale.
