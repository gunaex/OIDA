# Phase 3 Security and Authority

Gate 2 is required and immutable. AI can prepare candidates but cannot authorize
or create execution independently. Only a human project owner can authorize a
batch or create a PM binding. Every route resolves signed identity and project
membership; item, lineage and binding queries include project scope and fail
closed on cross-project references.

External identity is scoped by project, target type and binding—not trusted by raw
external ID alone. Provider and target credentials remain server-side. `.env` and
acceptance databases are ignored by Git; keys are not logged or documented.

Audited events include AI generation, human plan edits/rejection, authorization,
create request/result, manual/link actions, reconciliation, drift detection,
acknowledgement and resolution.
