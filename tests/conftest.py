import os
from pathlib import Path
import tempfile

_test_dir = tempfile.mkdtemp(prefix="oida-phase1-tests-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_test_dir}/oida.db")
os.environ["AI_PROVIDER"] = "fake"
os.environ["OIDA_SESSION_SECRET"] = "test-secret-not-for-production"
os.environ["OIDA_BOOTSTRAP_EMAIL"] = "owner@example.com"
os.environ["OIDA_BOOTSTRAP_PASSWORD"] = "change-me"

import pytest
from fastapi.testclient import TestClient

from app.main import app

_owner_password = "change-me"


def owner_password():
    return _owner_password


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


@pytest.fixture
def owner(client):
    global _owner_password
    response = client.post("/api/auth/login", json={"email": "owner@example.com", "password": _owner_password})
    assert response.status_code == 200
    if response.json().get("must_change_password"):
        replacement = "Test-owner-password-2026!"
        changed = client.post("/api/auth/password", json={"current_password":_owner_password,"new_password":replacement,"confirm_password":replacement})
        assert changed.status_code == 200, changed.text
        _owner_password = replacement
    return response.json()


def complete_ai(client, project_id, response):
    from app.jobs import run_one
    assert response.status_code == 202, response.text
    queued = response.json()
    assert queued["status"] == "QUEUED"
    completed = client.get(f"/api/projects/{project_id}/ai-runs/{queued['ai_run_id']}")
    if completed.json()["status"] not in {"COMPLETED","FAILED"}:
        assert run_one("pytest-worker")
        completed = client.get(f"/api/projects/{project_id}/ai-runs/{queued['ai_run_id']}")
    assert completed.status_code == 200, completed.text
    job = completed.json()
    assert job["status"] in {"COMPLETED", "FAILED"}
    return job["result"]


def create_project(client, suffix=""):
    response = client.post("/api/projects", headers={"Idempotency-Key": f"project-{suffix}"}, json={
        "name": f"Customer Portal {suffix}",
        "objective": "Build a secure customer self-service portal for invoice and support access.",
        "description": "Phase 1 acceptance project",
    })
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def project(client, owner, request):
    return create_project(client, request.node.name)
