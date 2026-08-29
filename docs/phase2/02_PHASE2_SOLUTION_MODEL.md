# Phase 2 Solution Model

| Record | Invariant |
|---|---|
| Solution AI Run | exact Requirement Baseline, provider/model/prompt/status/failure |
| Solution Candidate/Revision | non-authoritative; original AI and append-only human revisions retained |
| Solution/Revision | stable `SOL-nnn`; committed revision cites exact Requirement Baseline |
| Solution Coverage | exact requirement-revision → status/component/explanation rows |

The lifecycle is `NEEDS_REVIEW → SELECTED → COMMITTED`, with `REJECTED` and
`SUPERSEDED` branches. Selection is human-controlled but is not a fourth authority
gate. A merged candidate is explicitly `HUMAN_MERGE` and records its source
candidate IDs in audit evidence.

Every option contains summary, principles, components, integrations, data flow,
security/deployment considerations, assumptions, constraints, risks, open
decisions, exact requirement coverage, pros/cons, complexity, effort, confidence
and recommendation basis. Exactly one generated option is recommended, but the
recommendation has no authority. Working edits append revisions. A new Requirement
Baseline makes work grounded in an older baseline stale.
