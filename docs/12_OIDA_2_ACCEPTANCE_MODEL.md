# OIDA 2.0 Acceptance Model

## Separate meanings

- **Technical success:** an operation or system behaved according to technical
  criteria (for example an AI run succeeded or tests executed).
- **Workflow success:** required workflow steps and deterministic gates completed.
- **Business success:** the accepted outcome meets authorized business criteria.
- **Resolution:** an issue was closed by fix, deferment, waiver, or rejection; it
  does not imply success.

## Readiness package

The immutable package manifest references project frame, requirement and delivery
baseline versions, decisions, risks, work state, validation coverage/results,
evidence, changes since baseline, failures, waivers, residual risks, and freshness.
AI drafts a plain-language assessment, but deterministic gate results and source
facts remain separately visible.

## Gate result

`READY`, `READY_WITH_EXCEPTIONS`, or `NOT_READY`. READY requires complete mandatory
traceability, no failed mandatory validation, current evidence, no unresolved
blocking decision/conflict, and named acceptance authority. Exceptions require a
specific authorized waiver and residual-risk owner.

## Decision

Only the named human authority can `ACCEPT`, `REJECT`, or `RETURN_FOR_REWORK` with
comment. The record includes actor, authority basis, time, package hash, decision,
and any conditions. A later correction creates a new decision/version; audit
history is immutable.

