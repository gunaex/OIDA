from app.db import connect
from tests.conftest import complete_ai


def add_context(client, project, key="context-1"):
    response = client.post(f"/api/projects/{project['id']}/context", headers={"Idempotency-Key":key}, json={
        "source_type":"PASTED_TEXT", "title":"Customer portal brief",
        "content":"Authenticated customers can view invoices, download invoice PDFs, submit support requests, and track request status. Role based access and audit are required. The existing billing API remains source of truth. Responsive web UI is required."
    })
    assert response.status_code == 201, response.text
    return response.json()


def generate(client, project, key="generate-1"):
    response = client.post(f"/api/projects/{project['id']}/ai/requirements:generate", headers={"Idempotency-Key":key},
                           json={"instruction":"Generate concise testable requirements."})
    result = complete_ai(client, project["id"], response)
    assert result["status"] == "SUCCEEDED"
    return result


def test_full_golden_flow_and_baseline_immutability(client, owner, project):
    context = add_context(client, project)
    run = generate(client, project)

    # Candidate materialization is not authoritative.
    candidates = client.get(f"/api/projects/{project['id']}/requirement-candidates").json()
    assert len(candidates) >= 3
    assert client.get(f"/api/projects/{project['id']}/requirements").json() == []

    first, rejected = candidates[0], candidates[1]
    edit = client.patch(f"/api/projects/{project['id']}/requirement-candidates/{first['id']}", json={
        "title": "Invoice access", "statement":"The portal shall allow authenticated customers to view their invoices.",
        "rationale":"Customers need self-service access.", "priority":"MUST",
        "acceptance_criteria":["A customer sees only invoices owned by that customer."]})
    assert edit.status_code == 200 and edit.json()["human_modified"] is True

    rejection = client.post(f"/api/projects/{project['id']}/requirement-candidates/{rejected['id']}:reject", json={"reason":"Duplicate"})
    assert rejection.status_code == 200

    accepted = client.post(f"/api/projects/{project['id']}/requirement-candidates/{first['id']}:accept",
                           headers={"Idempotency-Key":"accept-1"})
    assert accepted.status_code == 200
    accepted_body = accepted.json()
    assert accepted_body["reconciliation"] == "CONFIRMED"
    retry = client.post(f"/api/projects/{project['id']}/requirement-candidates/{first['id']}:accept",
                        headers={"Idempotency-Key":"accept-1"})
    assert retry.json()["requirement_id"] == accepted_body["requirement_id"]

    manual = client.post(f"/api/projects/{project['id']}/requirements", headers={"Idempotency-Key":"manual-1"}, json={
        "title":"Audit actions", "statement":"The portal shall audit security-relevant user actions.",
        "rationale":"Operational accountability is required.", "priority":"MUST",
        "acceptance_criteria":["Audit records identify actor, action, target and time."]})
    assert manual.status_code == 201
    requirements = client.get(f"/api/projects/{project['id']}/requirements").json()
    assert len(requirements) == 2
    assert {x["origin"] for x in requirements} == {"AI", "HUMAN"}

    ready = client.get(f"/api/projects/{project['id']}/requirement-baselines/readiness").json()
    assert ready["ready"] is True
    frozen = client.post(f"/api/projects/{project['id']}/requirement-baselines:freeze",
                         headers={"Idempotency-Key":"freeze-1"})
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["membership_reconciliation"] == "CONFIRMED"
    retry_freeze = client.post(f"/api/projects/{project['id']}/requirement-baselines:freeze",
                               headers={"Idempotency-Key":"freeze-1"})
    assert retry_freeze.json()["baseline_id"] == frozen.json()["baseline_id"]

    baseline = client.get(f"/api/projects/{project['id']}/requirement-baselines/{frozen.json()['baseline_id']}").json()
    original_member_revisions = {x["requirement_id"]: x["requirement_revision_id"] for x in baseline["members"]}
    target = requirements[0]
    changed = client.patch(f"/api/projects/{project['id']}/requirements/{target['id']}", json={
        "title":target["title"], "statement":target["statement"] + " Access shall be logged.",
        "rationale":target["rationale"], "priority":target["priority"], "acceptance_criteria":target["acceptance_criteria"]})
    assert changed.status_code == 200 and changed.json()["revision"] == 2
    baseline_after = client.get(f"/api/projects/{project['id']}/requirement-baselines/{frozen.json()['baseline_id']}").json()
    assert {x["requirement_id"]: x["requirement_revision_id"] for x in baseline_after["members"]} == original_member_revisions

    truth = client.get(f"/api/projects/{project['id']}/truth").json()
    assert truth["baseline"]["status"] == "FROZEN"
    assert truth["requirement_readiness"] == "GATE_1_COMPLETE"
    assert truth["next_recommended_phase"] == "PHASE_2_DELIVERY_DESIGN_VERTICAL_SLICE"


def test_context_change_marks_candidate_stale_and_blocks_accept(client, owner, project):
    item = add_context(client, project, "stale-context")
    generate(client, project, "stale-generate")
    candidate = client.get(f"/api/projects/{project['id']}/requirement-candidates").json()[0]
    assert client.patch(f"/api/projects/{project['id']}/context/{item['id']}", json={"content":item["content"] + " Timeline is six months."}).status_code == 200
    candidate = client.get(f"/api/projects/{project['id']}/requirement-candidates").json()[0]
    assert candidate["stale"] is True
    blocked = client.post(f"/api/projects/{project['id']}/requirement-candidates/{candidate['id']}:accept",
                          headers={"Idempotency-Key":"stale-accept"})
    assert blocked.status_code == 409
    truth = client.get(f"/api/projects/{project['id']}/truth").json()
    assert truth["ai"]["stale_candidate_count"] > 0


def test_regenerate_preserves_and_supersedes_candidate(client, owner, project):
    add_context(client, project, "regen-context")
    generate(client, project, "regen-first")
    old = client.get(f"/api/projects/{project['id']}/requirement-candidates").json()[0]
    response = client.post(f"/api/projects/{project['id']}/requirement-candidates/{old['id']}:regenerate",
        headers={"Idempotency-Key":"regen-action"}, json={"instruction":"Focus on security."})
    result=complete_ai(client,project["id"],response);assert result["status"]=="SUCCEEDED"
    candidates = client.get(f"/api/projects/{project['id']}/requirement-candidates").json()
    preserved = next(x for x in candidates if x["id"] == old["id"])
    assert preserved["status"] == "SUPERSEDED"
    assert any(x["supersedes_candidate_id"] == old["id"] for x in candidates)


def test_ai_unavailable_is_recorded_not_empty_success(client, owner, project, monkeypatch):
    from app.ai import DisabledAdapter
    monkeypatch.setattr("app.main.adapter_for", lambda: DisabledAdapter())
    add_context(client, project, "disabled-context")
    response = client.post(f"/api/projects/{project['id']}/ai/requirements:generate",
        headers={"Idempotency-Key":"disabled-ai"}, json={})
    result = complete_ai(client, project["id"], response)
    assert result["status"] == "FAILED"
    assert result["failure_code"] == "AI_UNAVAILABLE"
    truth = client.get(f"/api/projects/{project['id']}/truth").json()
    assert truth["ai"]["latest_run_status"] == "FAILED"
    assert any(x["type"] == "AI_FAILURE" for x in truth["attention"])


def test_generate_retry_is_idempotent(client, owner, project):
    add_context(client, project, "idem-context")
    first = generate(client, project, "same-generation")
    second = generate(client, project, "same-generation")
    assert second["ai_run_id"] == first["ai_run_id"]
    candidates = client.get(f"/api/projects/{project['id']}/requirement-candidates").json()
    assert len(candidates) == len(first["candidate_ids"])
