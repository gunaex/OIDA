import uuid

from app.auth import Actor, hash_password
from app.db import now, transaction
from app.main import app
from app.auth import current_actor
from tests.conftest import create_project


def add_user(email):
    user_id = str(uuid.uuid4())
    with transaction() as db:
        db.execute("INSERT INTO users VALUES (?,?,?,?,?,?)", (user_id, email, email, hash_password("password"), "HUMAN", now()))
    return user_id


def test_missing_auth_fails_closed(client):
    client.cookies.clear()
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/projects/prj_unknown/truth").status_code == 401


def test_cross_project_read_and_write_denied(client, owner, project):
    other_id = add_user(f"other-{uuid.uuid4()}@example.com")
    other = client.__class__(app)
    with other:
        assert other.post("/api/auth/login", json={"email": f"other-{uuid.uuid4()}@example.com", "password":"password"}).status_code == 401
    # Log the known user in using a separate client so cookies do not overlap.
    from fastapi.testclient import TestClient
    with transaction() as db:
        email = db.execute("SELECT email FROM users WHERE id=?", (other_id,)).fetchone()[0]
    with TestClient(app) as second:
        assert second.post("/api/auth/login", json={"email":email,"password":"password"}).status_code == 200
        assert second.get(f"/api/projects/{project['id']}").status_code == 404
        assert second.get(f"/api/projects/{project['id']}/context").status_code == 404
        assert second.get(f"/api/projects/{project['id']}/requirement-candidates").status_code == 404
        assert second.get(f"/api/projects/{project['id']}/requirements").status_code == 404
        assert second.post(f"/api/projects/{project['id']}/context", headers={"Idempotency-Key":"cross"},
            json={"title":"Attack", "content":"Cross-project content must never be written.", "source_type":"PASTED_TEXT"}).status_code == 404
        assert second.patch(f"/api/projects/{project['id']}/requirements/req_unknown", json={
            "title":"Attack", "statement":"The system shall reject this cross-project write.",
            "rationale":"Isolation", "priority":"MUST", "acceptance_criteria":["Denied"]}).status_code == 404


def test_invalid_project_binding_fails_closed(client, owner):
    assert client.get("/api/projects/prj_does_not_exist/truth").status_code == 404


def test_ai_actor_cannot_freeze(client, owner, project):
    with transaction() as db:
        code = "REQ-001"; req, rev = f"req_{uuid.uuid4().hex}", f"rrev_{uuid.uuid4().hex}"
        db.execute("INSERT INTO requirements VALUES (?,?,?,?,?,?,?,?,?,?,?)", (req, project["id"], code, "HUMAN", None,
            "COMMITTED", 1, owner["id"], None, now(), now()))
        db.execute("INSERT INTO requirement_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (rev, req, project["id"], 1,
            "Manual", "The system shall remain secure.", "Security", "MUST", '["Verified"]', '[]', owner["id"], now()))
    app.dependency_overrides[current_actor] = lambda: Actor(owner["id"], owner["email"], owner["display_name"], "AI")
    try:
        response = client.post(f"/api/projects/{project['id']}/requirement-baselines:freeze", headers={"Idempotency-Key":"ai-freeze"})
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_project_member_cannot_freeze(client, owner, project):
    from fastapi.testclient import TestClient
    member_id = add_user(f"member-{uuid.uuid4()}@example.com")
    with transaction() as db:
        email = db.execute("SELECT email FROM users WHERE id=?", (member_id,)).fetchone()[0]
        db.execute("INSERT INTO project_memberships VALUES (?,?,?)", (project["id"], member_id, "PROJECT_MEMBER"))
    with TestClient(app) as member:
        assert member.post("/api/auth/login", json={"email":email,"password":"password"}).status_code == 200
        response = member.post(f"/api/projects/{project['id']}/requirement-baselines:freeze",
                               headers={"Idempotency-Key":"member-freeze"})
        assert response.status_code == 403
