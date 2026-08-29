import pytest
from pydantic import ValidationError

from app.ai import (
    AIContextIncomplete,
    AIUnavailable,
    DeliveryPlanOutput,
    DisabledAdapter,
    FakeAdapter,
    RequirementBaselineInput,
    SolutionGenerationOutput,
)


def baseline():
    return RequirementBaselineInput("Portal","Deliver secure self-service","rbl_exact",1,[{
        "requirement_code":"REQ-001","requirement_revision_id":"rrev_exact","title":"Invoice access",
        "statement":"Customers can securely view their invoices.","priority":"MUST","acceptance_criteria":["Ownership is enforced"]}])


def test_phase2_fake_contracts_are_structured_distinct_and_grounded():
    adapter=FakeAdapter(); solutions=adapter.generate_solutions(baseline())
    assert isinstance(solutions,SolutionGenerationOutput)
    assert len(solutions.alternatives)==3 and len({x.title for x in solutions.alternatives})==3
    assert sum(1 for x in solutions.alternatives if x.recommended)==1
    for option in solutions.alternatives:
        assert {x.requirement_revision_id for x in option.requirement_coverage}=={"rrev_exact"}
    plan=adapter.generate_delivery_plan(baseline(),solutions.alternatives[0].model_dump())
    assert isinstance(plan,DeliveryPlanOutput)
    assert plan.items[0].requirement_revision_ids==["rrev_exact"]


def test_phase2_ai_unavailable_and_incomplete_are_honest():
    with pytest.raises(AIUnavailable): DisabledAdapter().generate_solutions(baseline())
    empty=RequirementBaselineInput("Portal","Objective","rbl",1,[])
    with pytest.raises(AIContextIncomplete): FakeAdapter().generate_solutions(empty)


def test_phase2_schema_rejects_malformed_output():
    with pytest.raises(ValidationError): SolutionGenerationOutput.model_validate({"alternatives":[],"findings":[]})
