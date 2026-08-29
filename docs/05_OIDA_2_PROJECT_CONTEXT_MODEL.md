# OIDA 2.0 Project Context Model

## Definition

Project Context is the versioned, access-controlled set of information selected to
support delivery and AI work. It is assembled per task; it is not one giant prompt.

## Layers

| Layer | Examples | Authority |
|---|---|---|
| Authoritative sources | approved baselines, controlled documents, committed decisions, PM status, test results | owning person/system |
| Derived context | normalized extracts, indexes, relationship projections, computed readiness | reproducible from sources |
| AI memory | summaries, terminology, working assumptions, preferences | non-authoritative and reviewable |

Each context item records project, source owner, source/version reference, type,
effective time, sensitivity/access labels, freshness, extraction status, and hash.

## Context assembly

An AI run declares its purpose and required context types. A deterministic resolver
selects accessible authoritative versions, relevant derived items, and optional
memory within a token/size budget. The resulting immutable context manifest is
stored with the run so results can be reproduced and audited.

## Freshness and conflict

- Superseded or stale sources remain visible but are excluded by default.
- A changed source marks derived context and affected candidates stale; committed
  artifacts do not change silently.
- Conflicting authoritative sources create an unresolved conflict. Precedence must
  come from ownership policy or a human decision, never AI guesswork.
- AI may explain and propose a resolution but cannot rewrite the source.

## Minimum MVP context

Objective, scope, constraints, stakeholders/authority, source documents,
requirements baseline, delivery baseline, decisions, risks, work status,
validation results, and evidence references. Persistent AI memory is P1; MVP may
retain run-specific summaries only.

