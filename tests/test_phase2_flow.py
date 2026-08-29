import copy


def establish_gate1(client, project, suffix="p2"):
    requirement = client.post(f"/api/projects/{project['id']}/requirements",
        headers={"Idempotency-Key":f"{suffix}-manual"}, json={
            "title":"Secure invoice access",
            "statement":"The portal shall let an authenticated customer view only invoices owned by that customer.",
            "rationale":"Customers require secure self-service access.", "priority":"MUST",
            "acceptance_criteria":["A customer cannot view another customer's invoice."]})
    assert requirement.status_code == 201, requirement.text
    frozen = client.post(f"/api/projects/{project['id']}/requirement-baselines:freeze",
        headers={"Idempotency-Key":f"{suffix}-gate1"})
    assert frozen.status_code == 200, frozen.text
    return requirement.json(), frozen.json()


def generate_and_commit_solution(client, project, suffix="p2"):
    generated = client.post(f"/api/projects/{project['id']}/ai/solutions:generate",
        headers={"Idempotency-Key":f"{suffix}-solutions"}, json={})
    assert generated.status_code == 200 and generated.json()["status"] == "SUCCEEDED", generated.text
    candidates = client.get(f"/api/projects/{project['id']}/solution-candidates").json()
    assert 2 <= len(candidates) <= 3
    selected = candidates[0]
    assert client.post(f"/api/projects/{project['id']}/solution-candidates/{selected['id']}:select").status_code == 200
    committed = client.post(f"/api/projects/{project['id']}/solution-candidates/{selected['id']}:commit",
        headers={"Idempotency-Key":f"{suffix}-commit-solution"})
    assert committed.status_code == 200, committed.text
    return candidates, committed.json()


def test_solution_requires_gate1_and_generates_comparable_grounded_options(client, owner, project):
    blocked = client.post(f"/api/projects/{project['id']}/ai/solutions:generate",
        headers={"Idempotency-Key":"no-gate1"}, json={})
    assert blocked.status_code == 409
    requirement, baseline = establish_gate1(client, project, "alternatives")
    candidates, committed = generate_and_commit_solution(client, project, "alternatives")
    assert len({x["title"] for x in candidates}) == len(candidates)
    assert sum(1 for x in candidates if x["recommended"]) == 1
    expected_revision = requirement["revision_id"]
    for candidate in candidates:
        assert candidate["requirement_baseline_id"] == baseline["baseline_id"]
        assert {x["requirement_revision_id"] for x in candidate["content"]["requirement_coverage"]} == {expected_revision}
        assert candidate["status"] != "COMMITTED" or candidate["id"] == candidates[0]["id"]
    assert committed["requirement_baseline_id"] == baseline["baseline_id"]


def test_solution_edit_reject_regenerate_merge_and_commit_idempotency(client, owner, project):
    establish_gate1(client, project, "controls")
    generated = client.post(f"/api/projects/{project['id']}/ai/solutions:generate",
        headers={"Idempotency-Key":"controls-gen"}, json={}).json()
    candidates = client.get(f"/api/projects/{project['id']}/solution-candidates").json()
    edited = copy.deepcopy(candidates[0]["content"]); edited["summary"] += " Human-reviewed."
    response = client.patch(f"/api/projects/{project['id']}/solution-candidates/{candidates[0]['id']}", json={"content":edited})
    assert response.status_code == 200 and response.json()["human_modified"] is True
    assert client.post(f"/api/projects/{project['id']}/solution-candidates/{candidates[1]['id']}:reject", json={"reason":"Trade-off rejected"}).status_code == 200
    regenerated = client.post(f"/api/projects/{project['id']}/solution-candidates/{candidates[2]['id']}:regenerate",
        headers={"Idempotency-Key":"controls-regen"}, json={"instruction":"Reduce coordination risk"})
    assert regenerated.status_code == 200 and regenerated.json()["status"] == "SUCCEEDED"
    merged = client.post(f"/api/projects/{project['id']}/solution-candidates:merge",
        headers={"Idempotency-Key":"controls-merge"}, json={"candidate_ids":[candidates[0]["id"],candidates[1]["id"]],"title":"Human composite"})
    assert merged.status_code == 201 and merged.json()["origin"] == "HUMAN_MERGE"
    merge_id = merged.json()["id"]
    assert client.post(f"/api/projects/{project['id']}/solution-candidates/{merge_id}:select").status_code == 200
    first = client.post(f"/api/projects/{project['id']}/solution-candidates/{merge_id}:commit", headers={"Idempotency-Key":"controls-commit"})
    retry = client.post(f"/api/projects/{project['id']}/solution-candidates/{merge_id}:commit", headers={"Idempotency-Key":"controls-commit"})
    assert first.status_code == 200 and retry.json()["solution_id"] == first.json()["solution_id"]
    assert generated["requirement_baseline_id"] == first.json()["requirement_baseline_id"]


def test_phase2_full_golden_flow_gate2_exact_membership_and_truth(client, owner, project):
    _, gate1 = establish_gate1(client, project, "golden2")
    _, solution = generate_and_commit_solution(client, project, "golden2")
    generated = client.post(f"/api/projects/{project['id']}/ai/delivery-plans:generate",
        headers={"Idempotency-Key":"golden2-plan-gen"}, json={})
    assert generated.status_code == 200 and generated.json()["status"] == "SUCCEEDED", generated.text
    candidate = client.get(f"/api/projects/{project['id']}/delivery-plan-candidates").json()[0]
    assert candidate["solution_revision_id"] == solution["revision_id"]
    content = copy.deepcopy(candidate["content"])
    content["planning_summary"] += " Human reviewed."
    edited = client.patch(f"/api/projects/{project['id']}/delivery-plan-candidates/{candidate['id']}", json={"content":content})
    assert edited.status_code == 200 and edited.json()["human_modified"] is True
    plan = client.post(f"/api/projects/{project['id']}/delivery-plan-candidates/{candidate['id']}:commit",
        headers={"Idempotency-Key":"golden2-plan-commit"})
    assert plan.status_code == 200 and plan.json()["reconciliation"] == "CONFIRMED", plan.text
    readiness = client.get(f"/api/projects/{project['id']}/delivery-baselines/readiness").json()
    assert readiness["ready"] is True and readiness["blocking_items"] == []
    frozen = client.post(f"/api/projects/{project['id']}/delivery-baselines:freeze",
        headers={"Idempotency-Key":"golden2-freeze"})
    assert frozen.status_code == 200, frozen.text
    retry = client.post(f"/api/projects/{project['id']}/delivery-baselines:freeze",
        headers={"Idempotency-Key":"golden2-freeze"})
    assert retry.json()["baseline_id"] == frozen.json()["baseline_id"]
    exact = client.get(f"/api/projects/{project['id']}/delivery-baselines/{frozen.json()['baseline_id']}").json()
    assert exact["requirement_baseline_id"] == gate1["baseline_id"]
    assert exact["solution_revision_id"] == solution["revision_id"]
    assert exact["delivery_plan_revision_id"] == plan.json()["revision_id"]
    committed_solution = client.get(f"/api/projects/{project['id']}/solutions").json()[0]
    changed_solution = copy.deepcopy(committed_solution["content"])
    changed_solution["summary"] += " A later working revision."
    assert client.patch(f"/api/projects/{project['id']}/solutions/{solution['solution_id']}", json={"content":changed_solution}).status_code == 200
    frozen_after = client.get(f"/api/projects/{project['id']}/delivery-baselines/{frozen.json()['baseline_id']}").json()
    assert frozen_after["solution_revision_id"] == exact["solution_revision_id"]
    assert frozen_after["delivery_plan_revision_id"] == exact["delivery_plan_revision_id"]
    truth = client.get(f"/api/projects/{project['id']}/truth").json()
    assert truth["delivery_readiness"] == "GATE_2_COMPLETE"
    assert truth["delivery_baseline"]["status"] == "FROZEN"
    assert truth["next_recommended_phase"] == "PHASE_3_EXECUTION_AND_VALIDATION"


def test_plan_dependency_validation_and_solution_revision_staleness(client, owner, project):
    establish_gate1(client, project, "stale2")
    candidates, solution = generate_and_commit_solution(client, project, "stale2")
    generated = client.post(f"/api/projects/{project['id']}/ai/delivery-plans:generate",
        headers={"Idempotency-Key":"stale2-plan"}, json={}).json()
    candidate = client.get(f"/api/projects/{project['id']}/delivery-plan-candidates").json()[0]
    item_ref = candidate["content"]["items"][0]["ref"]
    self_cycle = client.put(f"/api/projects/{project['id']}/delivery-plan-candidates/{candidate['id']}/dependencies",
        json={"dependencies":[{"predecessor_ref":item_ref,"successor_ref":item_ref,"dependency_type":"FINISH_TO_START"}]})
    assert self_cycle.status_code == 422
    committed_content = client.get(f"/api/projects/{project['id']}/solutions").json()[0]["content"]
    committed_content["summary"] += " New committed working revision."
    revised = client.patch(f"/api/projects/{project['id']}/solutions/{solution['solution_id']}", json={"content":committed_content})
    assert revised.status_code == 200
    now_stale = client.get(f"/api/projects/{project['id']}/delivery-plan-candidates").json()[0]
    assert now_stale["stale"] is True
    blocked = client.post(f"/api/projects/{project['id']}/delivery-plan-candidates/{candidate['id']}:commit",
        headers={"Idempotency-Key":"stale2-commit"})
    assert blocked.status_code == 409


def test_plan_manual_add_remove_and_unknown_dependency_are_validated(client, owner, project):
    establish_gate1(client, project, "manual-plan")
    generate_and_commit_solution(client, project, "manual-plan")
    generated = client.post(f"/api/projects/{project['id']}/ai/delivery-plans:generate",
        headers={"Idempotency-Key":"manual-plan-gen"}, json={}).json()
    candidate = client.get(f"/api/projects/{project['id']}/delivery-plan-candidates").json()[0]
    first = candidate["content"]["items"][0]
    manual = copy.deepcopy(first)
    manual.update({"ref":"item-manual","title":"Human-added rollout review","description":"Review rollout readiness with the accountable delivery owner."})
    added = client.post(f"/api/projects/{project['id']}/delivery-plan-candidates/{generated['candidate_id']}/items", json={"item":manual})
    assert added.status_code == 200
    unknown = client.put(f"/api/projects/{project['id']}/delivery-plan-candidates/{generated['candidate_id']}/dependencies", json={"dependencies":[
        {"predecessor_ref":first["ref"],"successor_ref":"other-project-item","dependency_type":"FINISH_TO_START"}]})
    assert unknown.status_code == 422
    removed = client.delete(f"/api/projects/{project['id']}/delivery-plan-candidates/{generated['candidate_id']}/items/item-manual")
    assert removed.status_code == 200 and removed.json()["removed_item_ref"] == "item-manual"


def test_new_requirement_baseline_makes_solution_candidate_stale(client, owner, project):
    establish_gate1(client, project, "rebaseline")
    result = client.post(f"/api/projects/{project['id']}/ai/solutions:generate",
        headers={"Idempotency-Key":"rebaseline-solutions"}, json={}).json()
    candidate_id = result["candidate_ids"][0]
    extra = client.post(f"/api/projects/{project['id']}/requirements", headers={"Idempotency-Key":"rebaseline-extra"}, json={
        "title":"Responsive access","statement":"The portal shall support responsive access on current mobile browsers.",
        "rationale":"Customers use mobile devices.","priority":"SHOULD","acceptance_criteria":["Core invoice flow works at 360px width."]})
    assert extra.status_code == 201
    second = client.post(f"/api/projects/{project['id']}/requirement-baselines:freeze", headers={"Idempotency-Key":"rebaseline-gate1-v2"})
    assert second.status_code == 200 and second.json()["version"] == 2
    stale = next(x for x in client.get(f"/api/projects/{project['id']}/solution-candidates").json() if x["id"] == candidate_id)
    assert stale["stale"] is True
    assert client.post(f"/api/projects/{project['id']}/solution-candidates/{candidate_id}:select").status_code == 409


def test_invalid_solution_coverage_is_rejected(client, owner, project):
    establish_gate1(client, project, "bad-coverage")
    result = client.post(f"/api/projects/{project['id']}/ai/solutions:generate",
        headers={"Idempotency-Key":"bad-coverage-gen"}, json={}).json()
    candidate = client.get(f"/api/projects/{project['id']}/solution-candidates").json()[0]
    content = copy.deepcopy(candidate["content"])
    content["requirement_coverage"] = []
    response = client.patch(f"/api/projects/{project['id']}/solution-candidates/{result['candidate_ids'][0]}", json={"content":content})
    assert response.status_code == 422


def test_solution_ai_failure_is_recorded_and_visible(client, owner, project, monkeypatch):
    from app.ai import DisabledAdapter
    establish_gate1(client, project, "p2-disabled")
    monkeypatch.setattr("app.phase2.adapter_for", lambda: DisabledAdapter())
    response = client.post(f"/api/projects/{project['id']}/ai/solutions:generate",
        headers={"Idempotency-Key":"p2-disabled-gen"}, json={})
    assert response.status_code == 200
    assert response.json()["status"] == "FAILED" and response.json()["failure_code"] == "AI_UNAVAILABLE"
    runs = client.get(f"/api/projects/{project['id']}/design-ai-runs").json()
    assert runs[0]["status"] == "FAILED" and runs[0]["run_type"] == "SOLUTION"
    truth = client.get(f"/api/projects/{project['id']}/truth").json()
    assert truth["design_ai"]["latest_solution_failure_code"] == "AI_UNAVAILABLE"
    assert any(x["type"] == "SOLUTION_AI_FAILURE" for x in truth["attention"])
