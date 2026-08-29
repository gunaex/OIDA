import pytest
from pydantic import ValidationError

from app.ai import (
    AIInvalidOutput,
    AcceptanceFoundationInput,
    AcceptancePackageOutput,
    OpenAIAdapter,
    QAFoundationInput,
    QAScopeOutput,
)


def qa_foundation():
    return QAFoundationInput(
        "Portal", "Deliver secure self-service", "rbase-1", 1, "dbase-1", 1,
        "srev-1", "prev-1", "snapshot-1",
        [{"requirement_revision_id":"rrev-1","requirement_code":"REQ-001","title":"Secure access",
          "statement":"Only the owning customer can access invoices.","priority":"MUST",
          "acceptance_criteria":["Other customers receive no invoice data"]}],
        [{"id":"ditem-1","requirement_revision_ids":["rrev-1"]}],
        [{"id":"exec-1","source_delivery_item_id":"ditem-1"}],
        {"execution_health":"HEALTHY"}, [], [{"target_type":"INTERNAL","binding_state":"READY"}],
    )


def valid_scope(requirement="rrev-1"):
    return QAScopeOutput.model_validate({
        "summary":"Concrete security validation grounded in frozen truth.",
        "validation_areas":["Security"], "risks":[], "gaps":[], "findings":[],
        "items":[{"area":"Security","title":"Validate customer ownership boundary",
          "objective":"Verify invoice access honors the exact frozen customer ownership boundary.",
          "preconditions":["Execution is available"],
          "validation_method":"Request the invoice as its owner and as a different authenticated customer.",
          "expected_result":"The owner succeeds and the other customer receives no invoice data.",
          "validation_type":"SECURITY","execution_mode":"MANUAL","target_type":"INTERNAL",
          "requirement_revision_ids":[requirement],
          "acceptance_criteria_refs":[{"requirement_revision_id":requirement,"criterion_index":0}],
          "delivery_item_ids":["ditem-1"],"execution_item_ids":["exec-1"],
          "required_evidence_types":["REPORT"],"priority":"HIGH","severity_if_failed":"CRITICAL",
          "owner_role":"Security QA Lead","required_for_acceptance":True,"warnings":[]}],
    })


def acceptance_foundation():
    return AcceptanceFoundationInput(
        "Portal","Deliver secure self-service","rbase-1","dbase-1","qa-1",2,
        {"execution_health":"HEALTHY"},{"total":1,"covered":1},{"total":1,"fail":1},
        {"valid":0,"missing":1},[{"validation_item_id":"val-fail"}],[],
        [{"validation_item_id":"val-fail"}],[],[],
        {"ready":False,"blocking_items":["REQUIRED_VALIDATION_FAIL","REQUIRED_EVIDENCE_MISSING"]},
    )


def test_phase4_structured_schemas_reject_malformed_output():
    with pytest.raises(ValidationError):
        QAScopeOutput.model_validate({"summary":"short","items":[]})
    with pytest.raises(ValidationError):
        AcceptancePackageOutput.model_validate({"executive_summary":"missing required fields"})


def test_openai_qa_transport_returns_structured_candidate(monkeypatch):
    adapter=OpenAIAdapter();monkeypatch.setattr(adapter,"_ensure_configured",lambda:None)
    monkeypatch.setattr(adapter,"_structured",lambda *args,**kwargs:valid_scope())
    assert adapter.generate_qa_scope(qa_foundation()).items[0].requirement_revision_ids == ["rrev-1"]


def test_acceptance_contract_exposes_failure_and_missing_evidence(monkeypatch):
    adapter=OpenAIAdapter();monkeypatch.setattr(adapter,"_ensure_configured",lambda:None)
    output=AcceptancePackageOutput.model_validate({
        "executive_summary":"The authoritative failed validation and evidence gap block acceptance.",
        "requirement_readiness":"One of one requirements has validation coverage.",
        "validation_readiness":"The required validation currently has a critical failure.",
        "evidence_readiness":"Required report evidence is currently missing.",
        "execution_readiness":"Execution Truth is healthy and reconciled.",
        "critical_failure_validation_item_ids":["val-fail"],
        "critical_blockers":["REQUIRED_VALIDATION_FAIL","REQUIRED_EVIDENCE_MISSING"],
        "missing_evidence_validation_item_ids":["val-fail"],"residual_risks":[],
        "acceptance_recommendation":"RECOMMEND_NOT_ACCEPT",
        "recommendation_basis":"Deterministic blockers remain authoritative and prevent final acceptance.","findings":[],
    })
    monkeypatch.setattr(adapter,"_structured",lambda *args,**kwargs:output)
    actual=adapter.generate_acceptance_package(acceptance_foundation())
    assert actual.critical_failure_validation_item_ids == ["val-fail"]
    assert actual.missing_evidence_validation_item_ids == ["val-fail"]

