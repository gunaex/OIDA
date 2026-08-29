# Phase 2 AI Solution Flow

```text
latest frozen Requirement Baseline
→ exact member/revision packet
→ SolutionGenerationOutput (2–3 alternatives)
→ schema + exact coverage/component validation
→ non-authoritative candidates
→ human compare/edit/reject/regenerate/select/merge
→ explicit solution commit + readback
```

Each option contains summary, principles, components, integrations, data flow,
security/deployment considerations, assumptions, constraints, risks, open
decisions, exact requirement coverage, pros/cons, complexity, effort, confidence
and recommendation basis. Alternatives must be materially distinct and exactly one
is recommended. Recommendation never performs selection.

Generation before Gate 1 is blocked. Candidate coverage must equal the exact
baseline member revision set; unknown component references fail validation. A new
Requirement Baseline makes older candidates and committed solutions stale.
