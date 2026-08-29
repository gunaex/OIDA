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


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


@pytest.fixture
def owner(client):
    response = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "change-me"})
    assert response.status_code == 200
    return response.json()


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
