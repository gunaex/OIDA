# Phase 1 Scope

## Objective

Prove Gate 1 through a real local product surface: an authorized human creates a
project, adds source context, asks an AI adapter for structured candidates, edits,
rejects, regenerates, accepts, adds a manual requirement, and freezes an immutable
Requirement Baseline reflected by Project Truth.

## Included

Project and membership; signed local session; project-scoped context and revision;
AI run/candidate/provenance/finding records; candidate revisions and controls;
committed requirement identities/revisions; deterministic baseline readiness;
human-owner freeze; exact baseline membership; audit/idempotency/reconciliation;
Gate-1 Project Truth and attention; browser workspace and action APIs.

## Excluded

File parsing beyond pasted text, delivery/architecture/PM/QA/Infra, Gate 2/3,
evidence management, change impact, portfolio, notifications, memory, autonomous
agents, Conductor integration, vectors, graphs, event bus, and workflow engine.

## Reversible defaults

- SQLite relational storage; a future adapter can replace infrastructure without
  changing domain semantics.
- Local signed-cookie identity with PROJECT_OWNER/PROJECT_MEMBER; Account Again can
  replace the identity port later.
- Provider adapter local to OIDA; future Conductor integration replaces the adapter
  behind `RequirementAdapter`.
- Pasted text only; binary ingestion is an honest known gap.

