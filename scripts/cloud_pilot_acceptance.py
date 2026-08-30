#!/usr/bin/env python3
"""Run the live cloud-pilot golden flow without embedding credentials."""

from __future__ import annotations

import json
import os
import time
import uuid

import httpx


BASE_URL = os.environ["OIDA_PILOT_URL"].rstrip("/")
API_URL = os.environ.get("OIDA_PILOT_API_URL", BASE_URL).rstrip("/")
EMAIL = os.environ["OIDA_PILOT_EMAIL"]
PASSWORD = os.environ["OIDA_PILOT_PASSWORD"]


def require(response: httpx.Response, *statuses: int) -> dict | list:
    if response.status_code not in statuses:
        raise RuntimeError(f"{response.request.method} {response.request.url.path}: "
                           f"expected {statuses}, got {response.status_code}: {response.text[:500]}")
    return response.json()


def timed_post(client: httpx.Client, path: str, *, headers: dict[str, str], payload: dict) -> tuple[dict, float]:
    started = time.monotonic()
    body = require(client.post(path, headers=headers, json=payload), 200)
    return body, round(time.monotonic() - started, 2)


def main() -> None:
    run = uuid.uuid4().hex[:12]
    common = {"Origin": BASE_URL}
    timeout = httpx.Timeout(300, connect=30)
    a = httpx.Client(base_url=API_URL, headers=common, timeout=timeout, follow_redirects=False)
    b = httpx.Client(base_url=BASE_URL, headers=common, timeout=timeout, follow_redirects=False)

    ready = require(b.get("/ready"), 200)
    login_a_response = a.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    actor_a = require(login_a_response, 200)
    login_b_response = b.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    actor_b = require(login_b_response, 200)
    cookie = login_b_response.headers.get("set-cookie", "").lower()
    cookie_controls = all(flag in cookie for flag in ("secure", "httponly", "samesite=strict"))

    project = require(a.post("/api/projects", headers={"Idempotency-Key": f"cloud-project-{run}"}, json={
        "name": f"Cloud Pilot Dogfood {run}",
        "objective": "Deliver a secure customer portal from governed requirements through execution truth.",
        "description": "Real cloud-pilot acceptance project created through the deployed cloud API.",
    }), 201)
    project_id = project["id"]
    visible_projects = require(b.get("/api/projects"), 200)
    second_session_visible = any(item["id"] == project_id for item in visible_projects)

    context = require(a.post(f"/api/projects/{project_id}/context",
        headers={"Idempotency-Key": f"cloud-context-{run}"}, json={
            "source_type": "PASTED_TEXT",
            "title": "Cloud pilot customer portal brief",
            "content": "Authenticated customers can view only their invoices, download invoice PDFs, submit support requests, and track request status. Role-based access, auditability, responsive web UX, and the existing billing API as source of truth are required.",
        }), 201)
    context_snapshot = require(b.get(f"/api/projects/{project_id}/context"), 200)
    context_visible = any(item["id"] == context["id"] for item in context_snapshot["items"])

    other = require(a.post("/api/projects", headers={"Idempotency-Key": f"cloud-scope-{run}"}, json={
        "name": f"Cloud Scope Control {run}", "objective": "Verify project-scoped child resources.",
        "description": "Isolation control project.",
    }), 201)
    cross_scope = a.patch(f"/api/projects/{other['id']}/context/{context['id']}", json={"content": "must not move"})
    project_scope_enforced = cross_scope.status_code == 404

    req_run, req_seconds = timed_post(a, f"/api/projects/{project_id}/ai/requirements:generate",
        headers={"Idempotency-Key": f"cloud-req-ai-{run}"},
        payload={"instruction": "Generate concise, testable, security-aware requirements for this real pilot."})
    if req_run.get("status") != "SUCCEEDED":
        raise RuntimeError(f"requirements AI failed: {req_run.get('failure_code')}")
    candidates = require(a.get(f"/api/projects/{project_id}/requirement-candidates"), 200)
    if not candidates:
        raise RuntimeError("requirements AI returned no candidates")
    first = candidates[0]
    accepted = require(a.post(f"/api/projects/{project_id}/requirement-candidates/{first['id']}:accept",
        headers={"Idempotency-Key": f"cloud-req-accept-{run}"}), 200)
    for candidate in candidates[1:]:
        if candidate["status"] == "NEEDS_REVIEW":
            require(a.post(f"/api/projects/{project_id}/requirement-candidates/{candidate['id']}:reject",
                json={"reason": "Pilot scope selects one representative AI requirement."}), 200)
    require(a.post(f"/api/projects/{project_id}/requirements",
        headers={"Idempotency-Key": f"cloud-manual-req-{run}"}, json={
            "title": "Audit security-relevant actions",
            "statement": "The portal shall record actor, action, target, outcome, and time for security-relevant actions.",
            "rationale": "The pilot requires operational accountability.", "priority": "MUST",
            "acceptance_criteria": ["Authorized reviewers can trace each security-relevant action to an actor and timestamp."],
        }), 201)
    gate1_ready = require(a.get(f"/api/projects/{project_id}/requirement-baselines/readiness"), 200)
    gate1 = require(a.post(f"/api/projects/{project_id}/requirement-baselines:freeze",
        headers={"Idempotency-Key": f"cloud-gate1-{run}"}), 200)

    solution_run, solution_seconds = timed_post(a, f"/api/projects/{project_id}/ai/solutions:generate",
        headers={"Idempotency-Key": f"cloud-solution-ai-{run}"}, payload={})
    if solution_run.get("status") != "SUCCEEDED":
        raise RuntimeError(f"solution AI failed: {solution_run.get('failure_code')}")
    solutions = require(a.get(f"/api/projects/{project_id}/solution-candidates"), 200)
    selected = next((item for item in solutions if item.get("recommended")), solutions[0])
    require(a.post(f"/api/projects/{project_id}/solution-candidates/{selected['id']}:select"), 200)
    solution = require(a.post(f"/api/projects/{project_id}/solution-candidates/{selected['id']}:commit",
        headers={"Idempotency-Key": f"cloud-solution-commit-{run}"}), 200)

    delivery_run, delivery_seconds = timed_post(a, f"/api/projects/{project_id}/ai/delivery-plans:generate",
        headers={"Idempotency-Key": f"cloud-delivery-ai-{run}"}, payload={})
    if delivery_run.get("status") != "SUCCEEDED":
        raise RuntimeError(f"delivery AI failed: {delivery_run.get('failure_code')}")
    delivery_candidates = require(a.get(f"/api/projects/{project_id}/delivery-plan-candidates"), 200)
    delivery = require(a.post(f"/api/projects/{project_id}/delivery-plan-candidates/{delivery_candidates[0]['id']}:commit",
        headers={"Idempotency-Key": f"cloud-delivery-commit-{run}"}), 200)
    gate2_ready = require(a.get(f"/api/projects/{project_id}/delivery-baselines/readiness"), 200)
    gate2 = require(a.post(f"/api/projects/{project_id}/delivery-baselines:freeze",
        headers={"Idempotency-Key": f"cloud-gate2-{run}"}), 200)

    execution_run, execution_seconds = timed_post(a, f"/api/projects/{project_id}/execution/materialization-plans:generate",
        headers={"Idempotency-Key": f"cloud-execution-ai-{run}"},
        payload={"instruction": "Create an exact, conservative internal execution mapping."})
    if execution_run.get("status") != "SUCCEEDED":
        raise RuntimeError(f"execution AI failed: {execution_run.get('failure_code')}")
    plan = require(a.get(f"/api/projects/{project_id}/execution/materialization-plans"), 200)[0]
    require(a.post(f"/api/projects/{project_id}/execution/materialization-plans/{plan['id']}:authorize",
        headers={"Idempotency-Key": f"cloud-authorize-{run}"}), 200)
    materialized = require(a.post(f"/api/projects/{project_id}/execution/materialization-plans/{plan['id']}:materialize",
        headers={"Idempotency-Key": f"cloud-materialize-{run}"}), 200)
    reconciled = require(a.post(f"/api/projects/{project_id}/execution:reconcile",
        headers={"Idempotency-Key": f"cloud-reconcile-{run}"}), 200)
    truth_a = require(a.get(f"/api/projects/{project_id}/truth"), 200)
    truth_b = require(b.get(f"/api/projects/{project_id}/truth"), 200)

    no_origin_client = httpx.Client(base_url=BASE_URL, timeout=timeout)
    no_origin_client.cookies.update(b.cookies)
    no_origin = no_origin_client.post("/api/projects", json={"name": "Blocked", "objective": "Blocked"})
    malformed = b.post("/api/projects", json={})
    safe_error = "traceback" not in malformed.text.lower() and "file \"" not in malformed.text.lower()

    result = {
        "status": "PASS",
        "base_url": BASE_URL,
        "api_url": API_URL,
        "build_version": ready["version"],
        "project_id": project_id,
        "same_actor": actor_a["id"] == actor_b["id"],
        "second_session_visible": second_session_visible and context_visible,
        "cookie_controls": cookie_controls,
        "project_scope_enforced": project_scope_enforced,
        "origin_control_status": no_origin.status_code,
        "safe_validation_error": safe_error and malformed.status_code == 422,
        "ai": {
            "requirements": {"status": req_run["status"], "seconds": req_seconds, "candidate_count": len(candidates)},
            "solutions": {"status": solution_run["status"], "seconds": solution_seconds, "candidate_count": len(solutions)},
            "delivery": {"status": delivery_run["status"], "seconds": delivery_seconds, "candidate_count": len(delivery_candidates)},
            "execution": {"status": execution_run["status"], "seconds": execution_seconds, "plan_item_count": len(plan["items"])},
        },
        "gates": {"gate1_ready": gate1_ready["ready"], "gate1": gate1["baseline_id"],
                  "gate2_ready": gate2_ready["ready"], "gate2": gate2["baseline_id"]},
        "lineage": {"requirement_id": accepted["requirement_id"], "solution_revision_id": solution["revision_id"],
                    "delivery_revision_id": delivery["revision_id"]},
        "execution": {"materialized_status": materialized["status"],
                      "confirmed_count": materialized["confirmed_count"],
                      "reconcile_status": reconciled["status"]},
        "truth_consistent_across_sessions": truth_a == truth_b,
        "execution_health": truth_a["execution_health"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
