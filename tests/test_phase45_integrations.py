from app.document_sources import DeterministicDocumentAdapter, DocumentRecord
from tests.conftest import create_project


def test_document_binding_import_provenance_dedup_and_staleness(client, owner, monkeypatch):
    project = create_project(client, "document-pilot")
    adapter = DeterministicDocumentAdapter()
    monkeypatch.setattr("app.phase45.adapter_for_document", lambda: adapter)

    bound = client.post(f"/api/projects/{project['id']}/integrations/document-again/binding",
                        json={"external_project_id": "doc-project-1"})
    assert bound.status_code == 201
    assert bound.json()["status"] == "READY"

    documents = client.get(f"/api/projects/{project['id']}/integrations/document-again/documents")
    assert documents.status_code == 200
    assert documents.json()[0]["revision_id"] == "rev-1"

    first = client.post(f"/api/projects/{project['id']}/integrations/document-again/import",
                        json={"document_id": "doc-1"})
    duplicate = client.post(f"/api/projects/{project['id']}/integrations/document-again/import",
                            json={"document_id": "doc-1"})
    assert first.status_code == 201
    assert duplicate.json()["deduplicated"] is True
    assert first.json()["content_sha256"]

    adapter.documents["doc-project-1"] = [DocumentRecord("doc-1", "Pilot brief", "rev-2", 2,
                                                           "A newer approved brief with changed acceptance scope.")]
    refreshed = client.post(f"/api/projects/{project['id']}/integrations/document-again:refresh")
    assert refreshed.json() == {"status": "STALE", "checked": 1, "attention": 1, "automatic_rebaseline": False}
    refs = client.get(f"/api/projects/{project['id']}/integrations/document-again/sources").json()
    assert refs[0]["status"] == "STALE"
    assert refs[0]["external_revision_id"] == "rev-1"


def test_document_cross_project_isolation_and_live_readiness(client, owner, monkeypatch):
    one = create_project(client, "doc-one")
    two = create_project(client, "doc-two")
    adapter = DeterministicDocumentAdapter()
    monkeypatch.setattr("app.phase45.adapter_for_document", lambda: adapter)
    client.post(f"/api/projects/{one['id']}/integrations/document-again/binding", json={"external_project_id":"doc-project-1"})
    client.post(f"/api/projects/{one['id']}/integrations/document-again/import", json={"document_id":"doc-1"})
    assert client.get(f"/api/projects/{two['id']}/integrations/document-again/sources").json() == []
    readiness = client.get(f"/api/projects/{two['id']}/integrations/readiness").json()
    assert readiness["document_again"]["status"] == "UNBOUND"
    assert readiness["pm_again"]["status"] == "UNBOUND"
