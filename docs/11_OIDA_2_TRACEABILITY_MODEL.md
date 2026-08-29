# OIDA 2.0 Traceability Model

## Minimal typed relationship

A link contains `project_id`, `source_type/id/version`, `relationship_type`,
`target_type/id/version`, status (`PROPOSED` or `COMMITTED`), creator/run,
provenance, confidence for proposals, owner, and timestamps.

MVP relationship types are deliberately finite:

- `DERIVED_FROM`: artifact → context source
- `SATISFIED_BY`: requirement → solution/delivery element
- `IMPLEMENTED_BY`: requirement or delivery element → work item
- `VERIFIED_BY`: requirement → validation item/result
- `EVIDENCED_BY`: result/requirement → evidence
- `DEPENDS_ON`: work/delivery element → work/delivery element
- `AFFECTS`: baseline revision → downstream item (manual/deterministic MVP; AI P1)
- `INCLUDED_IN`: versioned item → baseline/acceptance package

AI may propose links. A human or policy commits them within owner authority. Every
link is inspectable and correctable; deleting a committed link creates an audited
retirement rather than erasing history.

## MVP integrity checks

Every Must requirement must be satisfied, implemented or explicitly non-build,
verified, and evidenced before unqualified readiness PASS. Broken references,
version mismatch, and coverage gaps are deterministic findings. AI explains likely
missing relationships but never fabricates evidence.

This is an adjacency/typed-link model, not a generic graph platform. Graph storage
is unnecessary unless scale and query evidence later justify it.

