import pytest
import httpx
from types import SimpleNamespace

from app.execution_targets import (
    DeterministicExternalAdapter,
    PmAgainExecutionAdapter,
    TargetCreateFailed,
    TargetCreateRequest,
    TargetTimeout,
    TargetUnavailable,
)


def request():
    return TargetCreateRequest(
        execution_item_id="exec-1",
        project_id="project-1",
        binding_id="binding-1",
        title="Build secure invoice flow",
        description="Implement the frozen delivery item with exact lineage.",
        owner_role="Delivery Lead",
        priority="HIGH",
        milestone_ref="milestone-1",
        dependencies=[],
        idempotency_key="plan:item",
    )


def test_target_contract_create_readback_and_semantic_deduplication():
    adapter = DeterministicExternalAdapter()
    first = adapter.create_work_item(None, request())
    second = adapter.create_work_item(None, request())
    assert first.external_id == second.external_id
    assert adapter.creates == 1
    assert adapter.get_work_item(None, "project-1", "binding-1", first.external_id) == first
    updated = adapter.update_work_item(None, "project-1", "binding-1", first.external_id, {"priority":"LOW"})
    assert updated.priority == "LOW" and adapter.list_project_work(None,"project-1","binding-1") == [updated]


@pytest.mark.parametrize(
    ("mode", "error"),
    [("timeout", TargetTimeout), ("failure", TargetCreateFailed)],
)
def test_target_contract_reports_write_failures(mode, error):
    with pytest.raises(error):
        DeterministicExternalAdapter(mode).create_work_item(None, request())


def test_target_contract_reports_unconfirmed_readback():
    adapter = DeterministicExternalAdapter("readback_missing")
    created = adapter.create_work_item(None, request())
    assert adapter.get_work_item(None, "project-1", "binding-1", created.external_id) is None


def test_target_contract_surfaces_changed_and_deleted_items():
    adapter = DeterministicExternalAdapter()
    created = adapter.create_work_item(None, request())
    adapter.items[created.external_id].owner_role = "Changed Owner"
    assert adapter.get_work_item(None, "project-1", "binding-1", created.external_id).owner_role == "Changed Owner"
    del adapter.items[created.external_id]
    assert adapter.get_work_item(None, "project-1", "binding-1", created.external_id) is None


def test_pm_again_service_user_login_and_project_verification(monkeypatch):
    requests = []
    transport = httpx.MockTransport(lambda request: _pm_response(request, requests))
    original_client = httpx.Client
    monkeypatch.setattr("app.execution_targets.settings", SimpleNamespace(
        pm_again_configured=True, pm_again_url="https://pm.example",
        pm_again_api_key="", pm_again_email="oida-service@example.com",
        pm_again_password="runtime-only-password", integration_timeout_seconds=5,
    ))
    monkeypatch.setattr("app.execution_targets.httpx.Client",
                        lambda **kwargs: original_client(transport=transport, **kwargs))
    adapter = PmAgainExecutionAdapter()
    assert adapter.verify_project("pilot") == {"slug": "pilot", "name": "Pilot"}
    assert requests == ["POST /api/auth/login", "GET /api/projects/pilot"]


def _pm_response(request, requests):
    requests.append(f"{request.method} {request.url.path}")
    if request.url.path == "/api/auth/login":
        return httpx.Response(200, headers={"set-cookie": "access_token=test; Path=/; HttpOnly"},
                              json={"must_change_password": False})
    if request.url.path == "/api/projects/pilot":
        assert "access_token=test" in request.headers.get("cookie", "")
        return httpx.Response(200, json={"slug": "pilot", "name": "Pilot"})
    return httpx.Response(404)


def test_pm_again_service_user_auth_failure_is_fail_closed(monkeypatch):
    original_client = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={"detail": "denied"}))
    monkeypatch.setattr("app.execution_targets.settings", SimpleNamespace(
        pm_again_configured=True, pm_again_url="https://pm.example",
        pm_again_api_key="", pm_again_email="oida-service@example.com",
        pm_again_password="never-logged", integration_timeout_seconds=5,
    ))
    monkeypatch.setattr("app.execution_targets.httpx.Client",
                        lambda **kwargs: original_client(transport=transport, **kwargs))
    with pytest.raises(TargetUnavailable, match="authentication failed"):
        PmAgainExecutionAdapter()


def test_pm_again_projection_hides_transport_lineage_marker():
    item = PmAgainExecutionAdapter._item({
        "id": 42, "title": "Pilot task",
        "desc": "Business description\n\nOIDA-IDEMPOTENCY: plan:item",
        "owner": "Delivery Lead", "priority": "High", "status": "Todo",
    })
    assert item.description == "Business description"


def test_pm_again_create_uses_live_description_field_and_lineage_marker(monkeypatch):
    adapter = object.__new__(PmAgainExecutionAdapter)
    captured = {}
    monkeypatch.setattr(adapter, "_binding", lambda db, project_id, binding_id: {"external_project_id": "pilot"})
    monkeypatch.setattr(adapter, "_list_project_work", lambda binding: [])
    def request(method, path, json_body=None):
        captured.update({"method": method, "path": path, "body": json_body})
        return {"id": 7, **json_body}
    monkeypatch.setattr(adapter, "_request", request)
    created = adapter.create_work_item(None, globals()["request"]())
    assert captured["body"]["description"].endswith("OIDA-IDEMPOTENCY: plan:item")
    assert "desc" not in captured["body"]
    assert created.description == "Implement the frozen delivery item with exact lineage."
