# OIDA 2.0 Golden Flow

## Final MVP flow

1. **Frame** — A delivery lead creates the project, states objective, scope,
   constraints, stakeholders, and desired acceptance outcome, then adds sources.
2. **Understand and define** — AI indexes sources, reports missing/conflicting
   context, and produces grounded requirement candidates with acceptance criteria.
   A human resolves material gaps and commits the requirement baseline.
3. **Shape solution and delivery** — AI produces one recommended solution outline
   (plus an alternative only where trade-offs are material), risks, delivery plan,
   and validation scope. Humans edit and commit a combined delivery baseline.
4. **Execute and observe** — The system materializes work and validation items.
   People or connected tools update execution and test results. AI detects blockers,
   drift, missing coverage, and evidence gaps; reversible low-risk updates follow
   policy and exceptions request attention.
5. **Validate and accept** — Evidence is attached to requirements and validation
   results. AI prepares a readiness assessment and acceptance package, explicitly
   listing failures and residual risks. An authorized human accepts, rejects, or
   returns the project for rework.

## Why this is smaller than the initial hypothesis

Requirements and context understanding are one review cycle. Architecture,
solution, plan, and QA scope share one delivery-baseline gate rather than four
approval gates. Work materialization is part of execution, not a separate user
stage. Evidence preparation and validation are one readiness activity.

## Integrity gates

- Requirement baseline: objective, scope, acceptance criteria, conflicts, and
  assumptions are reviewable and committed.
- Delivery baseline: solution, risks, milestones, work, and validation coverage are
  mutually consistent and committed.
- Acceptance: required evidence is present; failures, waivers, and residual risks
  are explicit; only an authorized human decides.

## Alternate paths

AI failure permits manual drafting and deterministic workflow controls. A failed
gate returns to the owning stage without deleting history. A baseline change
creates a revision and marks affected downstream items for review; full impact
intelligence is P1.

## Phase 0.1 historical revalidation

OIDA 1.x evidence validates explicit owner bindings, immutable versions, honest
partial states, and reconciliation after owner actions. These are cross-cutting
controls, not new user stages. The Golden Flow and its three authority gates remain
unchanged. Production go-live, destructive infrastructure change, commercial/legal
commitment, and risk waiver use action-specific human-only policy when applicable;
they do not become a fourth routine delivery gate.
