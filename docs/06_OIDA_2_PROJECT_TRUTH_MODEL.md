# OIDA 2.0 Project Truth Model

## Definition

Project Truth is a read model grounded only in authoritative sources. It answers
what is approved, undecided, active, blocked, changed, tested, failed, evidenced,
and required next. AI may summarize it but cannot create it by assertion.

## Truth projection

The projection references, rather than copies ownership from:

- OIDA-owned project identity, authority policy, baselines, decisions, acceptance;
- controlled artifact versions from a document owner;
- committed execution state from the PM owner;
- validation results and evidence from the QA/evidence owner.

Every fact exposes source, source version, observed time, freshness, and owner.
Derived readiness exposes its deterministic rule and inputs. AI findings are shown
separately as findings until resolved into authoritative changes.

## Minimum views

- Definition: current objective, scope, requirements, solution, and baselines.
- Delivery: current milestones/work, blockers, dependencies, risks, and owners.
- Validation: requirement coverage, results, failures, evidence, and waivers.
- Decisions: unresolved decisions and the person with authority.
- Readiness: deterministic gate result plus AI commentary clearly labeled.

## Integrity rules

Unknown is not false, absence of failure is not success, and stale is not current.
Conflicting facts display `CONFLICTED`; unreachable owners display
`WAITING_EXTERNAL`; missing proof displays `UNCONFIRMED`. Projection lag is visible.

