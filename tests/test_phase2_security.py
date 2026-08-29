import uuid

from fastapi.testclient import TestClient

from app.auth import Actor, current_actor, hash_password
from app.db import now, transaction
from app.main import app
from tests.conftest import create_project
from tests.test_phase2_flow import establish_gate1, generate_and_commit_solution


def test_phase2_cross_project_reads_and_writes_fail_closed(client, owner, project):
    establish_gate1(client, project, "p2-security")
    generate_and_commit_solution(client, project, "p2-security")
    user_id, email = str(uuid.uuid4()), f"p2-other-{uuid.uuid4()}@example.com"
    with transaction() as db:
        db.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", (user_id,email,email,hash_password("password"),"HUMAN",now()))
    with TestClient(app) as other:
        assert other.post("/api/auth/login",json={"email":email,"password":"password"}).status_code == 200
        for path in ["solution-readiness","solution-candidates","solutions","delivery-plan-candidates","delivery-plans","delivery-baselines/readiness"]:
            assert other.get(f"/api/projects/{project['id']}/{path}").status_code == 404
        assert other.post(f"/api/projects/{project['id']}/ai/solutions:generate",headers={"Idempotency-Key":"cross-p2"},json={}).status_code == 404


def test_only_human_owner_can_freeze_gate2(client, owner, project):
    establish_gate1(client, project, "p2-authority")
    generate_and_commit_solution(client, project, "p2-authority")
    generated=client.post(f"/api/projects/{project['id']}/ai/delivery-plans:generate",headers={"Idempotency-Key":"p2-auth-plan"},json={}).json()
    assert client.post(f"/api/projects/{project['id']}/delivery-plan-candidates/{generated['candidate_id']}:commit",headers={"Idempotency-Key":"p2-auth-commit"}).status_code == 200
    app.dependency_overrides[current_actor]=lambda:Actor(owner["id"],owner["email"],owner["display_name"],"AI")
    try:
        denied=client.post(f"/api/projects/{project['id']}/delivery-baselines:freeze",headers={"Idempotency-Key":"ai-gate2"})
        assert denied.status_code == 403
    finally:
        app.dependency_overrides.clear()
