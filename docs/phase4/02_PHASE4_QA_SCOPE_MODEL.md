# Phase 4 QA Scope Model

`qa_scopes` records the exact Requirement and Delivery Baselines, delivery-plan revision, Execution Truth hash, reconciliation run, origin, status, and current revision. `qa_scope_revisions` preserves review snapshots. A scope cannot materialize until a human project owner commits it.

Validation items contain actionable objective, preconditions, method, expected result, type, execution mode, target, evidence policy, severity, owner role, and acceptance requirement. Normalized link tables preserve exact requirement revision and criterion index, delivery item, and execution item mappings. Commit requires all frozen requirements and every frozen acceptance criterion to be covered by active items.

AI output starts as `AI_CANDIDATE`. Human edits create revisions, rejection remains visible, and human-authored replacement items retain their own origin. Any Execution Truth change makes the candidate stale and blocks commit.

