import pytest
from pydantic import ValidationError

from app.ai import (
    AIInvalidOutput,
    ExecutionBaselineInput,
    MaterializationPlanOutput,
    OpenAIAdapter,
)


def execution_baseline():
    return ExecutionBaselineInput(
        project_name="Portal",
        objective="Deliver secure invoice self-service",
        delivery_baseline_id="dbase-exact",
        delivery_baseline_version=1,
        requirement_baseline_id="rbase-exact",
        solution_revision_id="srev-exact",
        delivery_plan_revision_id="prev-exact",
        delivery_items=[{
            "id":"ditem-exact", "local_ref":"item-1", "title":"Deliver invoice access",
            "description":"Implement secure invoice access for the owning customer.",
            "owner_role":"Delivery Team", "effort":"M", "acceptance_criteria":["Ownership is enforced"],
        }],
        dependencies=[],
        milestones=[{"ref":"ms-ready","title":"Ready","item_refs":["item-1"]}],
        target_capabilities=[{"target_type":"INTERNAL","binding_state":"READY"}],
    )


def valid_output(source_ref="item-1"):
    return MaterializationPlanOutput.model_validate({
        "plan_summary":"A grounded one-to-one execution materialization.",
        "items":[{
            "source_delivery_item_ref":source_ref, "target_type":"INTERNAL",
            "execution_title":"Deliver invoice access",
            "execution_description":"Implement secure invoice access for the owning customer.",
            "suggested_owner_role":"Delivery Team", "priority":"MEDIUM", "milestone_ref":"ms-ready",
            "dependencies":[], "execution_type":"BUILD", "acceptance_hint":"Ownership is enforced",
            "warnings":[], "split_rationale":None,
        }],
        "routing_warnings":[], "unresolved_items":[], "findings":[],
    })


def test_materialization_schema_rejects_malformed_output():
    with pytest.raises(ValidationError):
        MaterializationPlanOutput.model_validate({"plan_summary":"too short","items":[]})


def test_materialization_domain_validation_rejects_unknown_frozen_reference(monkeypatch):
    adapter = OpenAIAdapter()
    monkeypatch.setattr(adapter, "_ensure_configured", lambda: None)
    monkeypatch.setattr(adapter, "_structured", lambda *args, **kwargs: valid_output("other-project-item"))
    with pytest.raises(AIInvalidOutput):
        adapter.generate_materialization_plan(execution_baseline())
