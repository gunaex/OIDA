import uuid

from app.auth import Actor, current_actor, hash_password
from app.db import now, transaction
from app.main import app
from tests.test_phase3_flow import establish_gate2, generate_plan
from tests.conftest import complete_ai


def establish_execution_truth(client, project, suffix="p4"):
    establish_gate2(client, project, suffix)
    _, plan = generate_plan(client, project, suffix)
    authorized = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:authorize",
        headers={"Idempotency-Key":f"{suffix}-execute-authorize"},
    )
    assert authorized.status_code == 200, authorized.text
    materialized = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:materialize",
        headers={"Idempotency-Key":f"{suffix}-execute-materialize"},
    )
    assert materialized.status_code == 200 and materialized.json()["status"] == "MATERIALIZED", materialized.text
    reconciled = client.post(
        f"/api/projects/{project['id']}/execution:reconcile",
        headers={"Idempotency-Key":f"{suffix}-execute-reconcile"},
    )
    assert reconciled.status_code == 200 and reconciled.json()["status"] == "SUCCEEDED", reconciled.text


def generate_qa(client, project, suffix="p4"):
    generated = client.post(
        f"/api/projects/{project['id']}/qa-scopes:generate",
        headers={"Idempotency-Key":f"{suffix}-qa-generate"},
        json={"instruction":"Generate concrete validation with exact frozen coverage."},
    )
    result=complete_ai(client,project["id"],generated);assert result["status"]=="SUCCEEDED"
    scope = client.get(f"/api/projects/{project['id']}/qa-scopes").json()[0]
    return result, scope


def test_phase4_requires_execution_truth_and_ai_candidate_is_not_authoritative(client, owner, project):
    blocked = client.post(
        f"/api/projects/{project['id']}/qa-scopes:generate",
        headers={"Idempotency-Key":"p4-upstream-blocked"}, json={},
    )
    assert blocked.status_code == 409
    establish_execution_truth(client, project, "p4-boundary")
    generated, scope = generate_qa(client, project, "p4-boundary")
    assert scope["status"] == "AI_CANDIDATE" and scope["items"]
    assert all(item["materialization_status"] == "DRAFT" for item in scope["items"])
    assert client.get(f"/api/projects/{project['id']}/final-acceptances").json() == []
    denied = client.post(
        f"/api/projects/{project['id']}/qa-scopes/{generated['scope_id']}:materialize",
        headers={"Idempotency-Key":"p4-before-commit"},
    )
    assert denied.status_code == 409


def test_phase4_closed_loop_controlled_fail_retest_evidence_package_and_gate3(client, owner, project):
    establish_execution_truth(client, project, "p4-golden")
    _, scope = generate_qa(client, project, "p4-golden")
    ai_item = scope["items"][0]
    edited = client.patch(
        f"/api/projects/{project['id']}/qa-scopes/{scope['id']}/items/{ai_item['id']}",
        json={"owner_role":"Acceptance QA Lead","priority":"HIGH"},
    )
    assert edited.status_code == 200 and edited.json()["human_override"] is True
    rejected = client.post(f"/api/projects/{project['id']}/qa-scopes/{scope['id']}/items/{ai_item['id']}:reject")
    assert rejected.status_code == 200 and rejected.json()["candidate_status"] == "REJECTED"
    manual = client.post(
        f"/api/projects/{project['id']}/qa-scopes/{scope['id']}/items",
        json={
            "area":"Security and Authorization",
            "title":"Human-reviewed ownership boundary validation",
            "objective":"Verify the frozen requirement behavior and its customer ownership boundary against actual execution.",
            "preconditions":["Internal execution is reconciled"],
            "validation_method":"Exercise the successful behavior and a cross-customer negative path, recording the observed authorization response.",
            "expected_result":"The owning customer succeeds and a different customer is denied without information disclosure.",
            "validation_type":"SECURITY","execution_mode":"MANUAL","target_type":"INTERNAL",
            "requirement_revision_ids":ai_item["requirement_revision_ids"],
            "acceptance_criteria_refs":ai_item["acceptance_criteria_refs"],
            "delivery_item_ids":ai_item["delivery_item_ids"],"execution_item_ids":ai_item["execution_item_ids"],
            "required_evidence_types":["REPORT"],"priority":"HIGH","severity_if_failed":"CRITICAL",
            "owner_role":"Security QA Lead","required_for_acceptance":True,
        },
    )
    assert manual.status_code == 201 and manual.json()["origin"] == "HUMAN", manual.text
    scope_id = scope["id"]
    commit_headers={"Idempotency-Key":"p4-golden-commit"}
    committed = client.post(f"/api/projects/{project['id']}/qa-scopes/{scope_id}:commit",headers=commit_headers)
    commit_retry = client.post(f"/api/projects/{project['id']}/qa-scopes/{scope_id}:commit",headers=commit_headers)
    assert committed.status_code == 200 and commit_retry.json() == committed.json(), committed.text
    materialize_headers={"Idempotency-Key":"p4-golden-materialize"}
    materialized = client.post(f"/api/projects/{project['id']}/qa-scopes/{scope_id}:materialize",headers=materialize_headers)
    materialize_retry = client.post(f"/api/projects/{project['id']}/qa-scopes/{scope_id}:materialize",headers=materialize_headers)
    assert materialized.status_code == 200 and materialized.json()["status"] == "CONFIRMED", materialized.text
    assert materialize_retry.json() == materialized.json()
    item = next(x for x in client.get(f"/api/projects/{project['id']}/validation-items").json() if x["id"] == manual.json()["id"])

    failed = client.post(
        f"/api/projects/{project['id']}/validation-items/{item['id']}/results",
        headers={"Idempotency-Key":"p4-controlled-fail"},
        json={"result":"FAIL","observed_result":"Cross-customer request unexpectedly returned invoice metadata.","notes":"Controlled negative-path failure."},
    )
    assert failed.status_code == 201 and failed.json()["result"] == "FAIL", failed.text
    blocked_readiness = client.get(f"/api/projects/{project['id']}/acceptance/readiness").json()
    assert "REQUIRED_VALIDATION_FAIL" in blocked_readiness["blocking_items"]
    denied = client.post(
        f"/api/projects/{project['id']}/final-acceptance",
        headers={"Idempotency-Key":"p4-too-early"},
        json={"acceptance_package_id":"none","acceptance_comment":"This acceptance must remain blocked."},
    )
    assert denied.status_code == 409

    passed = client.post(
        f"/api/projects/{project['id']}/validation-items/{item['id']}/results",
        headers={"Idempotency-Key":"p4-controlled-retest"},
        json={"result":"PASS","observed_result":"Owning customer succeeded and the cross-customer request returned 403 with no invoice metadata.","notes":"Retest after boundary correction."},
    )
    assert passed.status_code == 201 and passed.json()["result_no"] == 2
    history = client.get(f"/api/projects/{project['id']}/validation-items/{item['id']}/results").json()
    assert [x["result"] for x in history] == ["FAIL","PASS"]
    assert [x["status"] for x in history] == ["SUPERSEDED","CURRENT"]
    missing = client.get(f"/api/projects/{project['id']}/acceptance/readiness").json()
    assert "REQUIRED_EVIDENCE_MISSING" in missing["blocking_items"]

    test_evidence = client.post(f"/api/projects/{project['id']}/evidence",json={
        "classification":"TEST","evidence_type":"REPORT","validation_item_id":item["id"],
        "validation_result_id":passed.json()["id"],"execution_item_id":item["execution_item_ids"][0],
        "requirement_revision_ids":item["requirement_revision_ids"],"title":"Authorization boundary retest report",
        "description":"Observed result report for the successful ownership-boundary retest.",
        "content_text":"Retest run: owner request 200; cross-customer request 403; no invoice metadata disclosed.",
    })
    assert test_evidence.status_code == 201 and len(test_evidence.json()["content_sha256"]) == 64, test_evidence.text
    internal_evidence = client.post(f"/api/projects/{project['id']}/evidence",json={
        "classification":"INTERNAL","evidence_type":"RECORD","validation_item_id":item["id"],
        "validation_result_id":passed.json()["id"],"requirement_revision_ids":item["requirement_revision_ids"],
        "title":"Internal QA review record","description":"Human review of the controlled fail and successful retest.",
        "content_text":"QA lead reviewed the immutable FAIL history and the subsequent PASS evidence.",
    })
    assert internal_evidence.status_code == 201

    package = client.post(
        f"/api/projects/{project['id']}/acceptance-packages:generate",
        headers={"Idempotency-Key":"p4-golden-package"},json={},
    )
    package_result=complete_ai(client,project["id"],package);assert package_result["status"]=="SUCCEEDED"
    ready = client.get(f"/api/projects/{project['id']}/acceptance/readiness").json()
    assert ready["ready"] is True and ready["blocking_items"] == [], ready
    final_headers={"Idempotency-Key":"p4-golden-final"}
    accepted = client.post(f"/api/projects/{project['id']}/final-acceptance",headers=final_headers,json={
        "acceptance_package_id":package_result["package_id"],
        "acceptance_comment":"I reviewed the exact baselines, immutable result history, valid evidence and deterministic readiness.",
    })
    accepted_retry = client.post(f"/api/projects/{project['id']}/final-acceptance",headers=final_headers,json={
        "acceptance_package_id":package_result["package_id"],
        "acceptance_comment":"I reviewed the exact baselines, immutable result history, valid evidence and deterministic readiness.",
    })
    assert accepted.status_code == 200 and accepted.json()["status"] == "ACCEPTED", accepted.text
    assert accepted_retry.json()["id"] == accepted.json()["id"]
    assert passed.json()["id"] in accepted.json()["validation_result_ids"]
    assert failed.json()["id"] not in accepted.json()["validation_result_ids"]
    assert test_evidence.json()["id"] in accepted.json()["evidence_ids"]
    truth = client.get(f"/api/projects/{project['id']}/truth").json()
    assert truth["gate3_status"] == "ACCEPTED" and truth["next_recommended_phase"] == "PHASE_5_CHANGE_IMPACT_REBASELINE_INTELLIGENCE"


def test_evidence_security_status_history_and_safe_reference(client, owner, project):
    establish_execution_truth(client, project, "p4-evidence")
    _, scope = generate_qa(client, project, "p4-evidence")
    item = scope["items"][0]
    unsafe = client.post(f"/api/projects/{project['id']}/evidence",json={
        "classification":"CUSTOMER","evidence_type":"DOCUMENT","validation_item_id":item["id"],
        "requirement_revision_ids":item["requirement_revision_ids"],"title":"Unsafe evidence",
        "description":"This local path must be rejected.","external_reference":"file:///etc/passwd",
    })
    assert unsafe.status_code == 422
    evidence = client.post(f"/api/projects/{project['id']}/evidence",json={
        "classification":"CUSTOMER","evidence_type":"APPROVAL","validation_item_id":item["id"],
        "requirement_revision_ids":item["requirement_revision_ids"],"title":"Customer model example",
        "description":"A legitimate modeled stakeholder approval reference.","external_reference":"urn:approval:test-fixture-1",
    })
    assert evidence.status_code == 201
    invalid = client.patch(f"/api/projects/{project['id']}/evidence/{evidence.json()['id']}/status",json={"status":"INVALID","reason":"Approval was withdrawn."})
    assert invalid.status_code == 200 and invalid.json()["status"] == "INVALID"


def test_ai_and_project_member_cannot_perform_gate3_authority(client, owner, project):
    establish_execution_truth(client, project, "p4-authority")
    _, scope = generate_qa(client, project, "p4-authority")
    app.dependency_overrides[current_actor] = lambda: Actor(owner["id"],owner["email"],owner["display_name"],"AI")
    try:
        denied = client.post(f"/api/projects/{project['id']}/final-acceptance",headers={"Idempotency-Key":"p4-ai-final"},json={"acceptance_package_id":"none","acceptance_comment":"AI must never perform final acceptance."})
        assert denied.status_code == 403
    finally:
        app.dependency_overrides.clear()

    member_id=str(uuid.uuid4());email=f"p4-member-{uuid.uuid4()}@example.com"
    with transaction() as db:
        db.execute("INSERT INTO users (id,email,display_name,password_hash,actor_type,created_at) VALUES (?,?,?,?,?,?)",(member_id,email,email,hash_password("password"),"HUMAN",now()))
        db.execute("INSERT INTO project_memberships VALUES (?,?,?)",(project["id"],member_id,"PROJECT_MEMBER"))
    from fastapi.testclient import TestClient
    with TestClient(app) as member:
        assert member.post("/api/auth/login",json={"email":email,"password":"password"}).status_code == 200
        denied=member.post(f"/api/projects/{project['id']}/qa-scopes/{scope['id']}:commit",headers={"Idempotency-Key":"p4-member-commit"})
        assert denied.status_code == 403
