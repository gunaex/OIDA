# OIDA 2.0 AI Work Model

## Minimal concepts

**AI Run** is an immutable execution record: purpose, requested action, actor,
policy decision, model/tool configuration reference, context manifest, timestamps,
status, validation result, cost/usage metadata, and outputs.

**AI Candidate** is a reviewable proposed artifact or change produced by a run. It
contains structured content, provenance, assumptions, confidence, gaps, affected
artifacts, candidate status, and revision lineage.

**AI Action record** is created only when AI changes operational state. It records
the intended and actual change, automation level, authorization, reversibility,
before/after references, and undo/compensation outcome.

An observation or inference is a typed finding on an AI Run; it is not a separate
framework entity. A proposal becomes an AI Candidate. Execution produces an AI
Action record. Human acceptance creates or revises the appropriate domain artifact.

## Candidate lifecycle

`DRAFT → READY_FOR_REVIEW → COMMITTED` or `REJECTED`; regeneration creates a new
revision and preserves the old one. Commit is a deterministic authorized command,
not an AI state transition. Baseline and approval belong to the domain artifact.

## Controls

Users may edit, reject, regenerate with instructions, and compare material
alternatives. They can always inspect grounding and run status. Invalid or poorly
grounded output is retained for audit but cannot be committed until corrected.

## Runtime failures

`NOT_CONFIGURED`, `UNAVAILABLE`, `TIMEOUT`, `CONTEXT_INCOMPLETE`, `LOW_CONFIDENCE`,
`OUTPUT_INVALID`, `GROUNDING_INSUFFICIENT`, and `POLICY_BLOCKED` are explicit
failure/review codes. Manual work remains possible and is labeled as human-authored.

