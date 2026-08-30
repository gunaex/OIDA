from tests.conftest import create_project
from tests.test_phase4_flow import establish_execution_truth, generate_qa
from tests.conftest import complete_ai
from app.ai import AcceptancePackageOutput, DisabledAdapter, FakeAdapter
import app.phase4 as phase4


def commit_materialize_one(client,project,suffix):
    _,scope=generate_qa(client,project,suffix)
    committed=client.post(f"/api/projects/{project['id']}/qa-scopes/{scope['id']}:commit",headers={"Idempotency-Key":f"{suffix}-commit"})
    assert committed.status_code==200,committed.text
    materialized=client.post(f"/api/projects/{project['id']}/qa-scopes/{scope['id']}:materialize",headers={"Idempotency-Key":f"{suffix}-materialize"})
    assert materialized.status_code==200 and materialized.json()["status"]=="CONFIRMED",materialized.text
    return scope,client.get(f"/api/projects/{project['id']}/validation-items").json()[0]


def pass_and_evidence(client,project,item,suffix):
    result=client.post(f"/api/projects/{project['id']}/validation-items/{item['id']}/results",headers={"Idempotency-Key":f"{suffix}-pass"},json={"result":"PASS","observed_result":"The exact expected behavior was observed in the controlled validation run."})
    assert result.status_code==201,result.text
    evidence=client.post(f"/api/projects/{project['id']}/evidence",json={"classification":"TEST","evidence_type":"REPORT","validation_item_id":item["id"],"validation_result_id":result.json()["id"],"execution_item_id":item["execution_item_ids"][0],"requirement_revision_ids":item["requirement_revision_ids"],"title":"Controlled validation report","description":"Authentic recorded observations for this controlled validation run.","content_text":"Observed expected behavior and recorded the result against the exact current validation result."})
    assert evidence.status_code==201,evidence.text
    return result.json(),evidence.json()


def test_scope_staleness_blocks_commit(client,owner,project):
    establish_execution_truth(client,project,"p4-stale")
    _,scope=generate_qa(client,project,"p4-stale")
    execution=client.get(f"/api/projects/{project['id']}/execution/items").json()[0]
    changed=client.patch(f"/api/projects/{project['id']}/execution/items/{execution['id']}",json={"description":"A legitimate execution update that changes the exact QA source snapshot."})
    assert changed.status_code==200,changed.text
    blocked=client.post(f"/api/projects/{project['id']}/qa-scopes/{scope['id']}:commit",headers={"Idempotency-Key":"p4-stale-commit"})
    assert blocked.status_code==409 and "stale" in blocked.text.lower()


def test_cross_project_phase4_references_are_rejected(client,owner,project):
    establish_execution_truth(client,project,"p4-isolation-a");_,scope=generate_qa(client,project,"p4-isolation-a")
    other=create_project(client,"p4-isolation-b");establish_execution_truth(client,other,"p4-isolation-b");_,other_scope=generate_qa(client,other,"p4-isolation-b")
    foreign=other_scope["items"][0]
    denied=client.patch(f"/api/projects/{project['id']}/qa-scopes/{scope['id']}/items/{scope['items'][0]['id']}",json={"requirement_revision_ids":foreign["requirement_revision_ids"],"acceptance_criteria_refs":foreign["acceptance_criteria_refs"]})
    assert denied.status_code==422
    foreign_evidence=client.post(f"/api/projects/{project['id']}/evidence",json={"classification":"TEST","evidence_type":"REPORT","validation_item_id":foreign["id"],"requirement_revision_ids":foreign["requirement_revision_ids"],"title":"Foreign evidence","description":"This cross-project reference must be denied.","content_text":"Must not be stored."})
    assert foreign_evidence.status_code==422


def test_manual_acceptance_package_keeps_gate3_independent_of_ai(client,owner,project):
    establish_execution_truth(client,project,"p4-manual-package");scope,item=commit_materialize_one(client,project,"p4-manual-package");pass_and_evidence(client,project,item,"p4-manual-package")
    package=client.post(f"/api/projects/{project['id']}/acceptance-packages",headers={"Idempotency-Key":"p4-manual-package-create"},json={"executive_summary":"Human-prepared summary of exact validation, evidence and Execution Truth.","recommendation_basis":"Deterministic readiness remains authoritative; no AI recommendation was used."})
    assert package.status_code==201 and package.json()["recommendation"]=="NO_AI_RECOMMENDATION",package.text
    readiness=client.get(f"/api/projects/{project['id']}/acceptance/readiness").json()
    assert readiness["ready"] is True and readiness["acceptance_package_id"]==package.json()["package_id"]


def test_new_result_makes_acceptance_package_stale_and_preserves_history(client,owner,project):
    establish_execution_truth(client,project,"p4-package-stale");scope,item=commit_materialize_one(client,project,"p4-package-stale");pass_and_evidence(client,project,item,"p4-package-stale")
    package=client.post(f"/api/projects/{project['id']}/acceptance-packages",headers={"Idempotency-Key":"p4-package-stale-create"},json={"executive_summary":"Human-prepared exact-state Acceptance Package before a later retest.","recommendation_basis":"This exact snapshot is ready under deterministic policy at generation time."})
    assert package.status_code==201,package.text
    retest=client.post(f"/api/projects/{project['id']}/validation-items/{item['id']}/results",headers={"Idempotency-Key":"p4-package-stale-retest"},json={"result":"PASS","observed_result":"A later repeat validation also observed the expected exact behavior."})
    assert retest.status_code==201
    readiness=client.get(f"/api/projects/{project['id']}/acceptance/readiness").json()
    assert "STALE_ACCEPTANCE_PACKAGE" in readiness["blocking_items"] and "REQUIRED_EVIDENCE_MISSING" in readiness["blocking_items"]
    history=client.get(f"/api/projects/{project['id']}/validation-items/{item['id']}/results").json()
    assert len(history)==2 and history[0]["status"]=="SUPERSEDED" and history[1]["status"]=="CURRENT"


def test_ai_unavailable_does_not_create_scope_and_manual_fallback_remains(client,owner,project,monkeypatch):
    establish_execution_truth(client,project,"p4-ai-unavailable")
    monkeypatch.setattr(phase4,"adapter_for",lambda:DisabledAdapter())
    failed=client.post(f"/api/projects/{project['id']}/qa-scopes:generate",headers={"Idempotency-Key":"p4-ai-unavailable-generate"},json={})
    failed_result=complete_ai(client,project["id"],failed);assert failed_result["failure_code"]=="AI_UNAVAILABLE"
    assert client.get(f"/api/projects/{project['id']}/qa-scopes").json()==[]
    manual=client.post(f"/api/projects/{project['id']}/qa-scopes",headers={"Idempotency-Key":"p4-ai-unavailable-manual"},json={"summary":"Human-prepared fallback scope after a bounded AI provider failure."})
    assert manual.status_code==201 and manual.json()["origin"]=="HUMAN"


def test_acceptance_ai_cannot_omit_authoritative_failure(client,owner,project,monkeypatch):
    establish_execution_truth(client,project,"p4-ai-omission");scope,item=commit_materialize_one(client,project,"p4-ai-omission")
    failed=client.post(f"/api/projects/{project['id']}/validation-items/{item['id']}/results",headers={"Idempotency-Key":"p4-ai-omission-fail"},json={"result":"FAIL","observed_result":"The controlled negative path exposed data to the wrong customer."})
    assert failed.status_code==201
    class OmissionAdapter(FakeAdapter):
        def generate_acceptance_package(self,foundation,instruction=""):
            return AcceptancePackageOutput.model_validate({"executive_summary":"This deliberately unsafe summary attempts to hide the known failure.","requirement_readiness":"Frozen requirement coverage is present.","validation_readiness":"Validation was performed but details are omitted.","evidence_readiness":"Evidence status is represented incompletely.","execution_readiness":"Execution Truth is currently healthy.","critical_failure_validation_item_ids":[],"critical_blockers":[],"missing_evidence_validation_item_ids":[],"residual_risks":[],"acceptance_recommendation":"RECOMMEND_ACCEPT","recommendation_basis":"This unsafe model answer contradicts deterministic application truth and must be rejected.","findings":[]})
    monkeypatch.setattr(phase4,"adapter_for",lambda:OmissionAdapter())
    package=client.post(f"/api/projects/{project['id']}/acceptance-packages:generate",headers={"Idempotency-Key":"p4-ai-omission-package"},json={})
    package_result=complete_ai(client,project["id"],package);assert package_result["status"]=="FAILED" and package_result["failure_code"]=="AI_OUTPUT_INVALID"
    assert client.get(f"/api/projects/{project['id']}/acceptance-packages").json()==[]


def test_owner_approved_exception_is_explicit_exact_gate3_membership(client,owner,project):
    establish_execution_truth(client,project,"p4-exception");scope,item=commit_materialize_one(client,project,"p4-exception")
    blocked=client.post(f"/api/projects/{project['id']}/validation-items/{item['id']}/results",headers={"Idempotency-Key":"p4-exception-blocked"},json={"result":"BLOCKED","observed_result":"A required external test condition was unavailable during the bounded acceptance window."})
    assert blocked.status_code==201
    exception=client.post(f"/api/projects/{project['id']}/acceptance-exceptions",json={"validation_item_id":item["id"],"validation_result_id":blocked.json()["id"],"reason":"The project owner explicitly accepts this bounded validation exception.","risk":"The unexecuted condition may expose a behavior gap after acceptance."})
    assert exception.status_code==201 and exception.json()["status"]=="PENDING"
    decision=client.post(f"/api/projects/{project['id']}/acceptance-exceptions/{exception.json()['id']}:decide",json={"decision":"APPROVED"})
    assert decision.status_code==200 and decision.json()["status"]=="APPROVED"
    package=client.post(f"/api/projects/{project['id']}/acceptance-packages",headers={"Idempotency-Key":"p4-exception-package"},json={"executive_summary":"The owner-approved exception and its retained risk are represented explicitly.","recommendation_basis":"Deterministic policy recognizes the exact approved exception without changing its result."})
    assert package.status_code==201 and package.json()["deterministic_ready"] is True,package.text
    final=client.post(f"/api/projects/{project['id']}/final-acceptance",headers={"Idempotency-Key":"p4-exception-final"},json={"acceptance_package_id":package.json()["package_id"],"acceptance_comment":"I accept this exact package and the explicit approved exception risk."})
    assert final.status_code==200 and final.json()["exception_ids"]==[exception.json()["id"]]
