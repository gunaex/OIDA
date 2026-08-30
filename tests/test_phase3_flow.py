from app.db import connect, transaction

from tests.test_phase2_flow import establish_gate1, generate_and_commit_solution
from tests.conftest import complete_ai


def establish_gate2(client, project, suffix="p3"):
    _, gate1 = establish_gate1(client, project, suffix)
    _, solution = generate_and_commit_solution(client, project, suffix)
    generated = client.post(
        f"/api/projects/{project['id']}/ai/delivery-plans:generate",
        headers={"Idempotency-Key": f"{suffix}-plan-generate"},
        json={},
    )
    generated_result=complete_ai(client,project["id"],generated);assert generated_result["status"]=="SUCCEEDED"
    candidate = client.get(f"/api/projects/{project['id']}/delivery-plan-candidates").json()[0]
    committed = client.post(
        f"/api/projects/{project['id']}/delivery-plan-candidates/{candidate['id']}:commit",
        headers={"Idempotency-Key": f"{suffix}-plan-commit"},
    )
    assert committed.status_code == 200 and committed.json()["reconciliation"] == "CONFIRMED", committed.text
    frozen = client.post(
        f"/api/projects/{project['id']}/delivery-baselines:freeze",
        headers={"Idempotency-Key": f"{suffix}-gate2"},
    )
    assert frozen.status_code == 200, frozen.text
    return gate1, solution, committed.json(), frozen.json()


def generate_plan(client, project, suffix="p3"):
    response = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans:generate",
        headers={"Idempotency-Key": f"{suffix}-materialization-plan"},
        json={"instruction": "Create an exact, conservative execution mapping."},
    )
    result=complete_ai(client,project["id"],response);assert result["status"]=="SUCCEEDED"
    return result, client.get(f"/api/projects/{project['id']}/execution/materialization-plans").json()[0]


def test_gate2_and_human_authorization_are_hard_boundaries(client, owner, project):
    blocked = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans:generate",
        headers={"Idempotency-Key": "p3-no-gate2"},
        json={},
    )
    assert blocked.status_code == 409
    assert client.get(f"/api/projects/{project['id']}/execution/readiness").json()["ready"] is False

    establish_gate2(client, project, "p3-boundary")
    generated, plan = generate_plan(client, project, "p3-boundary")
    assert plan["status"] == "NEEDS_REVIEW"
    assert client.get(f"/api/projects/{project['id']}/execution/items").json() == []
    denied = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{generated['plan_id']}:materialize",
        headers={"Idempotency-Key": "p3-before-auth"},
    )
    assert denied.status_code == 409


def test_internal_golden_flow_exact_lineage_idempotency_reconciliation_and_truth(client, owner, project):
    gate1, solution, delivery_plan, gate2 = establish_gate2(client, project, "p3-golden")
    generated, plan = generate_plan(client, project, "p3-golden")
    assert plan["delivery_baseline_id"] == gate2["baseline_id"]
    assert plan["preview"]["enabled"] == len(plan["items"])
    assert all(item["target_type"] == "INTERNAL" and item["source_delivery_item_id"] for item in plan["items"])

    first = plan["items"][0]
    edited = client.patch(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}/items/{first['id']}",
        json={"owner_role": "Delivery Lead", "priority": "HIGH"},
    )
    assert edited.status_code == 200 and edited.json()["human_override"] is True
    assert edited.json()["current_revision"] == 2

    auth_headers = {"Idempotency-Key": "p3-golden-authorize"}
    authorized = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:authorize",
        headers=auth_headers,
    )
    retry_authorize = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:authorize",
        headers=auth_headers,
    )
    assert authorized.status_code == 200 and retry_authorize.json() == authorized.json()

    materialize_headers = {"Idempotency-Key": "p3-golden-materialize"}
    materialized = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:materialize",
        headers=materialize_headers,
    )
    retried = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:materialize",
        headers=materialize_headers,
    )
    assert materialized.status_code == 200 and materialized.json()["status"] == "MATERIALIZED", materialized.text
    assert retried.json() == materialized.json()

    items = client.get(f"/api/projects/{project['id']}/execution/items").json()
    assert len(items) == materialized.json()["confirmed_count"]
    assert len({item["materialization_item_id"] for item in items}) == len(items)
    assert len({item["execution_code"] for item in items}) == len(items)
    assert all(item["reconciliation_status"] == "CONFIRMED" for item in items)
    assert all(item["source_plan_revision_id"] == delivery_plan["revision_id"] for item in items)
    assert all(item["source_delivery_item_id"] for item in items)

    reconciled = client.post(
        f"/api/projects/{project['id']}/execution:reconcile",
        headers={"Idempotency-Key": "p3-golden-reconcile"},
    )
    assert reconciled.status_code == 200 and reconciled.json()["status"] == "SUCCEEDED", reconciled.text
    assert reconciled.json()["confirmed_count"] == len(items)
    truth = client.get(f"/api/projects/{project['id']}/truth").json()
    assert truth["delivery_baseline_id"] == gate2["baseline_id"]
    assert truth["execution_materialization_progress"]["materialized"] == len(items)
    assert truth["execution_health"] == "HEALTHY"
    assert truth["next_recommended_phase"] == "PHASE_4_QA_EVIDENCE_AND_FINAL_ACCEPTANCE"
    assert gate1["baseline_id"] and solution["revision_id"]


def test_partial_materialization_unlinked_work_and_drift_acknowledgement(client, owner, project):
    establish_gate2(client, project, "p3-partial")
    _, plan = generate_plan(client, project, "p3-partial")
    binding = client.post(
        f"/api/projects/{project['id']}/execution/bindings/pm-again",
        json={"external_project_id": "contract-test-project"},
    ).json()
    routed = client.patch(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}/items/{plan['items'][0]['id']}",
        json={"target_type": "PM_AGAIN", "binding_id": binding["id"]},
    )
    assert routed.status_code == 200 and routed.json()["status"] == "BLOCKED"

    # A separate ready item proves partial execution: blocked target work is never silently dropped.
    source_id = plan["items"][0]["source_delivery_item_id"]
    manual = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}/items",
        json={
            "source_delivery_item_id": source_id,
            "execution_title": "Internal fallback coordination",
            "execution_description": "Coordinate the internal execution fallback while external routing remains blocked.",
            "owner_role": "Delivery Lead",
            "acceptance_hint": "Fallback work is visible and assigned.",
        },
    )
    assert manual.status_code == 201 and manual.json()["status"] == "PLANNED"
    authorized = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:authorize",
        headers={"Idempotency-Key": "p3-partial-authorize"},
    )
    assert authorized.json()["blocked_item_count"] == 1
    materialized = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:materialize",
        headers={"Idempotency-Key": "p3-partial-materialize"},
    )
    assert materialized.json()["status"] == "PARTIAL"
    assert materialized.json()["blocked_count"] == 1 and materialized.json()["confirmed_count"] == 1

    unlinked = client.post(
        f"/api/projects/{project['id']}/execution/items",
        json={
            "title": "Urgent production coordination",
            "description": "Coordinate urgent production work before its delivery-plan link is confirmed.",
            "owner_role": "Incident Lead",
            "priority": "HIGH",
        },
    )
    assert unlinked.status_code == 201 and unlinked.json()["link_state"] == "UNLINKED"
    reconcile = client.post(
        f"/api/projects/{project['id']}/execution:reconcile",
        headers={"Idempotency-Key": "p3-partial-reconcile"},
    )
    assert reconcile.status_code == 200 and reconcile.json()["status"] == "PARTIAL"
    drift = client.get(f"/api/projects/{project['id']}/execution/drift").json()
    unlinked_drift = next(item for item in drift if item["execution_item_id"] == unlinked.json()["id"] and item["drift_type"] == "UNLINKED_EXECUTION")
    acknowledged = client.post(f"/api/projects/{project['id']}/execution/drift/{unlinked_drift['id']}:acknowledge")
    assert acknowledged.status_code == 200 and acknowledged.json()["status"] == "ACKNOWLEDGED"
    linked = client.post(
        f"/api/projects/{project['id']}/execution/items/{unlinked.json()['id']}:link",
        json={"source_delivery_item_id": source_id},
    )
    assert linked.status_code == 200 and linked.json()["link_state"] == "LINKED"


def test_internal_change_is_detected_as_authorized_plan_drift(client, owner, project):
    establish_gate2(client, project, "p3-drift")
    _, plan = generate_plan(client, project, "p3-drift")
    client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:authorize",
        headers={"Idempotency-Key": "p3-drift-authorize"},
    )
    client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:materialize",
        headers={"Idempotency-Key": "p3-drift-materialize"},
    )
    item = client.get(f"/api/projects/{project['id']}/execution/items").json()[0]
    changed = client.patch(
        f"/api/projects/{project['id']}/execution/items/{item['id']}",
        json={"owner_role": "Unapproved External Owner"},
    )
    assert changed.status_code == 200 and changed.json()["current_revision"] == 2
    reconciled = client.post(
        f"/api/projects/{project['id']}/execution:reconcile",
        headers={"Idempotency-Key": "p3-drift-reconcile"},
    )
    assert reconciled.json()["mismatch_count"] == 1
    drift = client.get(f"/api/projects/{project['id']}/execution/drift").json()
    assert any(record["drift_type"] == "OWNER_DRIFT" and record["execution_item_id"] == item["id"] for record in drift)


def test_external_unconfirmed_retry_is_deduplicated_and_missing_is_detected(client, owner, project, monkeypatch):
    from app.execution_targets import DeterministicExternalAdapter, adapter_for_target as real_adapter_for_target

    establish_gate2(client, project, "p3-external-contract")
    _, plan = generate_plan(client, project, "p3-external-contract")
    adapter = DeterministicExternalAdapter("readback_missing")
    monkeypatch.setattr("app.phase3.adapter_for_target", lambda target: adapter if target == "PM_AGAIN" else real_adapter_for_target(target))
    binding = client.post(
        f"/api/projects/{project['id']}/execution/bindings/pm-again",
        json={"external_project_id": "mock-contract-project"},
    ).json()
    verified = client.post(f"/api/projects/{project['id']}/execution/bindings/{binding['id']}:verify")
    assert verified.status_code == 200 and verified.json()["status"] == "READY"
    routed = client.patch(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}/items/{plan['items'][0]['id']}",
        json={"target_type": "PM_AGAIN", "binding_id": binding["id"]},
    )
    assert routed.json()["status"] == "PLANNED"
    client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:authorize",
        headers={"Idempotency-Key": "p3-external-authorize"},
    )
    first = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:materialize",
        headers={"Idempotency-Key": "p3-external-first"},
    )
    assert first.json()["unconfirmed_count"] == 1 and adapter.creates == 1
    adapter.mode = "confirmed"
    retry = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:materialize",
        headers={"Idempotency-Key": "p3-external-safe-retry"},
    )
    assert retry.json()["status"] == "MATERIALIZED" and retry.json()["confirmed_count"] == 1
    assert adapter.creates == 1
    execution = client.get(f"/api/projects/{project['id']}/execution/items").json()[0]
    with transaction() as db:
        db.execute("UPDATE execution_items SET last_verified_at='2000-01-01T00:00:00+00:00' WHERE id=?", (execution["id"],))
    stale_truth = client.get(f"/api/projects/{project['id']}/execution/truth").json()
    assert stale_truth["execution_freshness"]["stale_item_count"] == 1
    assert "TARGET_DATA_STALE" in stale_truth["execution_blockers"]
    del adapter.items[execution["external_id"]]
    missing = client.post(
        f"/api/projects/{project['id']}/execution:reconcile",
        headers={"Idempotency-Key": "p3-external-missing"},
    )
    assert missing.json()["missing_count"] == 1
    assert any(x["drift_type"] == "EXTERNAL_ITEM_MISSING" for x in client.get(f"/api/projects/{project['id']}/execution/drift").json())


def test_phase3_project_scope_is_enforced(client, owner, project):
    from tests.conftest import create_project

    establish_gate2(client, project, "p3-scope")
    _, plan = generate_plan(client, project, "p3-scope")
    other = create_project(client, "p3-scope-other")
    assert client.get(f"/api/projects/{other['id']}/execution/materialization-plans").json() == []
    cross = client.patch(
        f"/api/projects/{other['id']}/execution/materialization-plans/{plan['id']}/items/{plan['items'][0]['id']}",
        json={"priority": "LOW"},
    )
    assert cross.status_code == 404


def test_materialization_ai_failure_is_recorded_without_execution_corruption(client, owner, project, monkeypatch):
    from app.ai import DisabledAdapter

    establish_gate2(client, project, "p3-ai-failure")
    monkeypatch.setattr("app.phase3.adapter_for", lambda: DisabledAdapter())
    response = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans:generate",
        headers={"Idempotency-Key": "p3-ai-failure-generate"},
        json={},
    )
    result=complete_ai(client,project["id"],response)
    assert result["status"] == "FAILED" and result["failure_code"] == "AI_UNAVAILABLE"
    assert client.get(f"/api/projects/{project['id']}/execution/materialization-plans").json() == []
    assert client.get(f"/api/projects/{project['id']}/execution/items").json() == []
    manual = client.post(
        f"/api/projects/{project['id']}/execution/materialization-plans",
        headers={"Idempotency-Key": "p3-manual-fallback"},
        json={"summary": "Human fallback after the live AI provider was unavailable."},
    )
    assert manual.status_code == 201 and manual.json()["origin"] == "HUMAN"
    assert client.get(f"/api/projects/{project['id']}/execution/materialization-plans").json()[0]["items"] == []


def test_ai_actor_cannot_authorize_execution(client, owner, project):
    from app.auth import Actor, current_actor
    from app.main import app

    establish_gate2(client, project, "p3-ai-authority")
    _, plan = generate_plan(client, project, "p3-ai-authority")
    app.dependency_overrides[current_actor] = lambda: Actor(owner["id"], owner["email"], owner["display_name"], "AI")
    try:
        denied = client.post(
            f"/api/projects/{project['id']}/execution/materialization-plans/{plan['id']}:authorize",
            headers={"Idempotency-Key": "p3-ai-authorize-denied"},
        )
        assert denied.status_code == 403
        assert client.get(f"/api/projects/{project['id']}/execution/items").json() == []
    finally:
        app.dependency_overrides.clear()
