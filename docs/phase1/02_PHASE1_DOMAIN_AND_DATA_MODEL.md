# Phase 1 Domain and Data Model

| Record | Authority and invariant |
|---|---|
| User / Membership | local identity; every project read/write joins membership |
| Project | owns frame, context revision, readable requirement sequence |
| Context Item | authoritative user source; edit increments item and project revisions |
| AI Run | immutable runtime metadata and context revision; AI actor is distinct |
| Candidate / Candidate Revision | non-authoritative proposal; original output is retained |
| Requirement / Requirement Revision | committed human-controlled truth; stable `REQ-nnn` identity |
| Requirement Baseline / Member | human-frozen version pointing to exact revision IDs |
| Audit Event | actor/action/target/result evidence |
| Idempotency Record | same actor/project/action/key returns the original result |

Candidate lifecycle is `NEEDS_REVIEW → ACCEPTED | REJECTED | SUPERSEDED`.
Human edits append candidate revisions and set `human_modified`. Acceptance creates
one requirement due to both idempotency and a unique candidate link.

A requirement edit always appends a revision and updates only its working pointer.
Existing baseline members remain bound to prior revision IDs. Rebaselining is
structurally supported by increasing baseline version but advanced change workflow
is deferred.

The SQL migration contains only Phase 1 records and direct `project_id` scoping on
context, AI, candidate, requirement revision, baseline, and audit records.

