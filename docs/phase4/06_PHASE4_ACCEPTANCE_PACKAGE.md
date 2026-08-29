# Phase 4 Acceptance Package

An Acceptance Package is a versioned summary of exact baselines, QA Scope revision, Execution Truth hash, validation snapshot, evidence state, failures, blockers, missing evidence, residual risks, and recommendation. AI provenance and telemetry are persisted. A human can prepare the same deterministic package with `NO_AI_RECOMMENDATION`, so model availability never controls Gate 3.

Application validation requires critical failure IDs, missing-evidence IDs, and blocker codes to exactly equal authoritative state. AI cannot omit or invent membership and cannot recommend acceptance while deterministic blockers exist. Any result, evidence, execution, or scope change makes the package stale.

Live package v1 exposed the controlled FAIL and returned `RECOMMEND_NOT_ACCEPT`. After re-test, v2 exposed a stale planning-risk phrase; it was not accepted. Prompt and equality contracts were tightened. Live v3 reconciled planning risks against current evidence, returned exact empty blocker membership, and became the accepted current package.

