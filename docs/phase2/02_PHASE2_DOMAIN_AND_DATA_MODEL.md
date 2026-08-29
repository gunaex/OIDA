# Phase 2 Domain and Data Model

| Record | Invariant |
|---|---|
| Solution AI Run | exact Requirement Baseline, provider/model/prompt/status/failure |
| Solution Candidate/Revision | non-authoritative, original AI retained, human revisions appended |
| Solution/Revision | stable identity; committed revision cites exact Requirement Baseline |
| Solution Coverage | explicit exact requirement-revision → component/status/explanation rows |
| Plan AI Run | exact Requirement Baseline and committed solution revision |
| Plan Candidate/Revision | structured but non-authoritative editable plan |
| Delivery Plan/Revision | stable identity and immutable committed structured revision |
| Plan Item/Dependency/Milestone | explicit queryable committed revision children |
| Delivery Baseline | exact requirement-baseline, solution-revision and plan-revision membership |

Candidate lifecycles are explicit. Solution candidates use `NEEDS_REVIEW → SELECTED
→ COMMITTED` with reject/supersede branches; plan candidates use `NEEDS_REVIEW →
COMMITTED` with reject/supersede branches. Selection is a human decision but not a
new authority gate.

Working edits append revisions. A frozen Delivery Baseline never follows working
pointers: its three exact foreign keys remain unchanged after later revisions.
