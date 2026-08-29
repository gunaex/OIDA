from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time
from typing import Protocol

import httpx

from .config import settings


class DocumentSourceError(Exception):
    code = "DOCUMENT_SOURCE_ERROR"


class DocumentSourceUnavailable(DocumentSourceError):
    code = "BLOCKED_NOT_CONFIGURED"


class DocumentSourceInvalid(DocumentSourceError):
    code = "INVALID_BINDING"


@dataclass(frozen=True)
class DocumentProject:
    id: str
    name: str


@dataclass(frozen=True)
class DocumentRecord:
    id: str
    title: str
    revision_id: str
    revision_number: int | None
    content: str = ""

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class DocumentSourceAdapter(Protocol):
    provider: str
    def list_projects(self) -> list[DocumentProject]: ...
    def get_project(self, external_project_id: str) -> DocumentProject: ...
    def list_documents(self, external_project_id: str) -> list[DocumentRecord]: ...
    def get_document(self, external_project_id: str, document_id: str) -> DocumentRecord: ...


class DocumentAgainAdapter:
    provider = "DOCUMENT_AGAIN"

    def __init__(self):
        if not settings.document_again_url or not settings.document_again_api_key:
            raise DocumentSourceUnavailable("Document Again URL and API key are required")
        self.base = settings.document_again_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.document_again_api_key}",
            "X-Account-Id": settings.document_again_account_id,
            "X-Tenant-Id": settings.document_again_tenant_id,
        }

    def _get(self, path: str):
        try:
            response = httpx.get(f"{self.base}{path}", headers=self.headers,
                                 timeout=settings.integration_timeout_seconds)
        except httpx.TimeoutException as exc:
            raise DocumentSourceError("Document Again timed out") from exc
        if response.status_code == 404:
            raise DocumentSourceInvalid("Document Again object was not found")
        if response.status_code >= 400:
            raise DocumentSourceError(f"Document Again returned HTTP {response.status_code}")
        return response.json()

    def list_projects(self) -> list[DocumentProject]:
        return [DocumentProject(str(x["id"]), x.get("name") or x.get("title") or str(x["id"]))
                for x in self._get("/api/projects")]

    def get_project(self, external_project_id: str) -> DocumentProject:
        x = self._get(f"/api/projects/{external_project_id}")
        return DocumentProject(str(x["id"]), x.get("name") or x.get("title") or str(x["id"]))

    def list_documents(self, external_project_id: str) -> list[DocumentRecord]:
        artifacts = self._get(f"/api/projects/{external_project_id}/artifacts")
        result = []
        for item in artifacts:
            artifact = self._get(f"/api/artifacts/{item['id']}")
            revisions = artifact.get("revisions") or []
            latest = revisions[-1] if revisions else {}
            result.append(DocumentRecord(str(item["id"]), item.get("title") or item.get("name") or str(item["id"]),
                                         str(latest.get("id") or ""), latest.get("revision")))
        return result

    def get_document(self, external_project_id: str, document_id: str) -> DocumentRecord:
        artifact = self._get(f"/api/artifacts/{document_id}")
        if str(artifact.get("project_id")) != str(external_project_id):
            raise DocumentSourceInvalid("Document is outside the bound project")
        revisions = artifact.get("revisions") or []
        if not revisions:
            raise DocumentSourceInvalid("Document has no revision")
        revision = revisions[-1]
        payload = self._get(f"/api/revisions/{revision['id']}/document")
        content = payload.get("content") or payload.get("text") or payload.get("markdown") or ""
        return DocumentRecord(str(document_id), artifact.get("title") or artifact.get("name") or str(document_id),
                              str(revision["id"]), revision.get("revision"), content)


class DeterministicDocumentAdapter:
    provider = "DOCUMENT_AGAIN"

    def __init__(self, projects=None, documents=None, mode="confirmed"):
        self.projects = projects or [DocumentProject("doc-project-1", "Pilot Documents")]
        self.documents = documents or {
            "doc-project-1": [DocumentRecord("doc-1", "Pilot brief", "rev-1", 1,
                                               "Pilot brief with approved scope and measurable acceptance criteria.")]
        }
        self.mode = mode

    def _guard(self):
        if self.mode == "failure": raise DocumentSourceError("simulated provider failure")

    def list_projects(self): self._guard(); return list(self.projects)
    def get_project(self, external_project_id):
        self._guard()
        for project in self.projects:
            if project.id == external_project_id: return project
        raise DocumentSourceInvalid("project not found")
    def list_documents(self, external_project_id):
        self.get_project(external_project_id); return list(self.documents.get(external_project_id, []))
    def get_document(self, external_project_id, document_id):
        for document in self.list_documents(external_project_id):
            if document.id == document_id: return document
        raise DocumentSourceInvalid("document not found")


def adapter_for_document() -> DocumentSourceAdapter:
    return DocumentAgainAdapter()
