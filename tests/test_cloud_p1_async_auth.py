import uuid

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.db import now, transaction
from app.jobs import claim, run_one
from app.main import app
from tests.test_golden_flow import add_context


def test_async_start_is_202_idempotent_and_visible_across_sessions(client, owner, project):
    add_context(client, project, "p1-async-context")
    headers={"Idempotency-Key":"p1-async-same"}
    first=client.post(f"/api/projects/{project['id']}/ai/requirements:generate",headers=headers,json={})
    retry=client.post(f"/api/projects/{project['id']}/ai/requirements:generate",headers=headers,json={})
    assert first.status_code==202 and first.json()["status"]=="QUEUED"
    assert retry.json()["ai_run_id"]==first.json()["ai_run_id"]
    listed=client.get(f"/api/projects/{project['id']}/async-ai-runs").json()
    assert listed[0]["id"]==first.json()["ai_run_id"] and listed[0]["status"]=="QUEUED"

    member_id=str(uuid.uuid4());email=f"async-{uuid.uuid4()}@example.com";password="member-password"
    with transaction() as db:
        db.execute("INSERT INTO users (id,email,display_name,password_hash,actor_type,created_at) VALUES (?,?,?,?,?,?)",
                   (member_id,email,"Async observer",hash_password(password),"HUMAN",now()))
        db.execute("INSERT INTO project_memberships VALUES (?,?,?)",(project["id"],member_id,"PROJECT_MEMBER"))
    with TestClient(app) as other:
        assert other.post("/api/auth/login",json={"email":email,"password":password}).status_code==200
        queued=other.get(f"/api/projects/{project['id']}/ai-runs/{first.json()['ai_run_id']}")
        assert queued.status_code==200 and queued.json()["status"]=="QUEUED"
        assert run_one("p1-test-worker")
        completed=other.get(f"/api/projects/{project['id']}/ai-runs/{first.json()['ai_run_id']}").json()
        assert completed["status"]=="COMPLETED" and completed["result"]["status"]=="SUCCEEDED"


def test_expired_running_job_is_reclaimed_safely(client, owner, project):
    add_context(client,project,"p1-recovery-context")
    queued=client.post(f"/api/projects/{project['id']}/ai/requirements:generate",
                       headers={"Idempotency-Key":"p1-recovery"},json={}).json()
    with transaction() as db:
        db.execute("UPDATE async_ai_jobs SET status='RUNNING',lease_owner='crashed-worker',lease_expires_at=?,attempt_count=1 WHERE id=?",
                   ("2000-01-01T00:00:00+00:00",queued["ai_run_id"]))
    assert run_one("recovery-worker")
    recovered=client.get(f"/api/projects/{project['id']}/ai-runs/{queued['ai_run_id']}").json()
    assert recovered["status"]=="COMPLETED" and recovered["attempt_count"]==2


def test_claim_is_atomic_and_duplicate_worker_cannot_claim(client,owner,project):
    add_context(client,project,"p1-claim-context")
    queued=client.post(f"/api/projects/{project['id']}/ai/requirements:generate",headers={"Idempotency-Key":"p1-claim"},json={}).json()
    first=claim("claim-worker-a")
    assert first["id"]==queued["ai_run_id"] and first["status"]=="RUNNING"
    assert claim("claim-worker-b") is None
    with transaction() as db:
        db.execute("UPDATE async_ai_jobs SET status='FAILED',failure_code='TEST_CLEANUP',lease_owner=NULL,lease_expires_at=NULL,completed_at=? WHERE id=?",(now(),queued["ai_run_id"]))


def test_first_login_is_server_locked_and_password_change_rotates_session(client):
    user_id=str(uuid.uuid4());email=f"forced-{uuid.uuid4()}@example.com";temporary="Temporary-pass-2026!";replacement="Replacement-pass-2026!"
    with transaction() as db:
        db.execute("INSERT INTO users (id,email,display_name,password_hash,actor_type,created_at,must_change_password,bootstrap_policy_applied) VALUES (?,?,?,?,?,?,?,?)",
                   (user_id,email,"Forced user",hash_password(temporary),"HUMAN",now(),1,1))
    login=client.post("/api/auth/login",json={"email":email,"password":temporary})
    assert login.status_code==200 and login.json()["must_change_password"] is True
    old_cookie=client.cookies.get("oida_session")
    assert client.get("/api/projects").status_code==403
    changed=client.post("/api/auth/password",json={"current_password":temporary,"new_password":replacement,"confirm_password":replacement})
    assert changed.status_code==200 and changed.json()["must_change_password"] is False
    assert client.get("/api/projects").status_code==200
    with TestClient(app) as stale:
        stale.cookies.set("oida_session",old_cookie)
        assert stale.get("/api/auth/me").status_code==401
    with transaction() as db:
        actions={x[0] for x in db.execute("SELECT action FROM audit_events WHERE actor_id=?",(user_id,)).fetchall()}
    assert {"PASSWORD_CHANGED","FIRST_LOGIN_PASSWORD_CHANGE_COMPLETED"}.issubset(actions)
    assert client.post("/api/auth/logout").status_code==200
    assert client.post("/api/auth/login",json={"email":email,"password":temporary}).status_code==401
    assert client.post("/api/auth/login",json={"email":email,"password":replacement}).status_code==200


def test_password_change_rejects_wrong_current_and_short_password(client):
    user_id=str(uuid.uuid4());email=f"policy-{uuid.uuid4()}@example.com";temporary="Temporary-pass-2026!"
    with transaction() as db:
        db.execute("INSERT INTO users (id,email,display_name,password_hash,actor_type,created_at,must_change_password,bootstrap_policy_applied) VALUES (?,?,?,?,?,?,?,?)",
                   (user_id,email,"Policy user",hash_password(temporary),"HUMAN",now(),1,1))
    assert client.post("/api/auth/login",json={"email":email,"password":temporary}).status_code==200
    wrong=client.post("/api/auth/password",json={"current_password":"not-the-password","new_password":"Replacement-pass-2026!","confirm_password":"Replacement-pass-2026!"})
    short=client.post("/api/auth/password",json={"current_password":temporary,"new_password":"too-short","confirm_password":"too-short"})
    assert wrong.status_code==401 and short.status_code==422
