# Phase 1 AI Requirement Flow

```text
authorized active context
→ immutable context revision manifest
→ provider-neutral RequirementAdapter
→ parse + Pydantic schema validation
→ verify cited context IDs belong to supplied project packet
→ AI Run + candidate revisions + separate findings
→ human edit/reject/regenerate/accept
```

The candidate schema includes title, statement, rationale, priority, category,
acceptance criteria, exact context item IDs, assumptions, gaps, and HIGH/MEDIUM/LOW
confidence class. Source text is wrapped as untrusted `PROJECT_CONTEXT`; developer
policy remains separate and the AI receives no mutation tools.

`AI_PROVIDER=disabled` yields `AI_UNAVAILABLE` while manual requirements continue.
Timeout, invalid schema, incomplete context, and insufficient grounding have
separate exceptions/failure codes. Failed runs remain visible and generate an
attention item; no empty or fabricated candidate is substituted.

Regeneration preserves the instruction and prior candidate, creates a new run, and
supersedes the old unaccepted proposal only after successful materialization.
Context changes derive `stale=true` for pending candidates by comparing revisions;
stale candidates cannot be accepted and block baseline readiness until regenerated
or rejected.

```text
PHASE_1_AI_RUNTIME=LOCAL_PROVIDER_ADAPTER
FUTURE_CONDUCTOR_INTEGRATION=IMPLEMENT_REQUIREMENT_ADAPTER_PROTOCOL
```

