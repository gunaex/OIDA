from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import httpx

from .config import settings


@dataclass(frozen=True)
class TargetCapabilities:
    target_type: str
    supports_owner_assignment: bool
    supports_priority: bool
    supports_milestone: bool
    supports_dependency: bool
    supports_custom_fields: bool
    supports_status_write: bool

    def as_dict(self) -> dict:
        return self.__dict__.copy()


CAPABILITIES = {
    "INTERNAL": TargetCapabilities("INTERNAL", True, True, True, True, True, True),
    # PM Again's normal task contract supports owner/priority/status. Its phase
    # field is not claimed as a full milestone/dependency model.
    "PM_AGAIN": TargetCapabilities("PM_AGAIN", True, True, False, False, True, True),
    "MANUAL_EXTERNAL": TargetCapabilities("MANUAL_EXTERNAL", True, True, True, False, False, False),
}


@dataclass
class TargetCreateRequest:
    execution_item_id: str
    project_id: str
    binding_id: Optional[str]
    title: str
    description: str
    owner_role: Optional[str]
    priority: str
    milestone_ref: Optional[str]
    dependencies: list[str]
    idempotency_key: str
    external_reference: Optional[str] = None


@dataclass
class TargetItem:
    external_id: str
    title: str
    description: str
    owner_role: Optional[str]
    priority: str
    milestone_ref: Optional[str]
    dependencies: list[str]
    status: str = "NOT_STARTED"
    external_url: Optional[str] = None


class ExecutionTargetError(Exception):
    code = "TARGET_ERROR"


class TargetUnavailable(ExecutionTargetError):
    code = "TARGET_UNAVAILABLE"


class TargetTimeout(ExecutionTargetError):
    code = "TARGET_TIMEOUT"


class TargetCreateFailed(ExecutionTargetError):
    code = "TARGET_CREATE_FAILED"


class ExecutionTargetAdapter(Protocol):
    target_type: str
    capabilities: TargetCapabilities

    def create_work_item(self, db, request: TargetCreateRequest) -> TargetItem: ...
    def get_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[TargetItem]: ...
    def update_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str, changes: dict) -> TargetItem: ...
    def list_project_work(self, db, project_id: str, binding_id: Optional[str]) -> list[TargetItem]: ...


def _row_target(row) -> TargetItem:
    import json
    return TargetItem(
        external_id=row["external_id"] or row["id"], title=row["title"], description=row["description"],
        owner_role=row["owner_role"], priority=row["priority"], milestone_ref=row["milestone_ref"],
        dependencies=json.loads(row["dependencies_json"]), status=row["status"], external_url=row["external_url"],
    )


class InternalExecutionAdapter:
    target_type = "INTERNAL"
    capabilities = CAPABILITIES[target_type]

    def create_work_item(self, db, request: TargetCreateRequest) -> TargetItem:
        row = db.execute("SELECT * FROM execution_items WHERE id=? AND project_id=?", (request.execution_item_id, request.project_id)).fetchone()
        if not row:
            raise TargetCreateFailed("Internal execution projection is unavailable")
        return _row_target(row)

    def get_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[TargetItem]:
        row = db.execute(
            "SELECT * FROM execution_items WHERE project_id=? AND target_type='INTERNAL' AND (external_id=? OR id=?)",
            (project_id, external_id, external_id),
        ).fetchone()
        return _row_target(row) if row else None

    def update_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str, changes: dict) -> TargetItem:
        allowed={"title","description","owner_role","priority","milestone_ref","status"};fields={key:value for key,value in changes.items() if key in allowed}
        if not fields: raise TargetCreateFailed("No supported Internal execution fields were supplied")
        row=db.execute("SELECT id FROM execution_items WHERE project_id=? AND target_type='INTERNAL' AND (external_id=? OR id=?)",(project_id,external_id,external_id)).fetchone()
        if not row: raise TargetCreateFailed("Internal execution item is unavailable")
        assignments=','.join(f"{key}=?" for key in fields);db.execute(f"UPDATE execution_items SET {assignments} WHERE id=?",(*fields.values(),row["id"]))
        return self.get_work_item(db,project_id,binding_id,row["id"])

    def list_project_work(self, db, project_id: str, binding_id: Optional[str]) -> list[TargetItem]:
        return [_row_target(row) for row in db.execute("SELECT * FROM execution_items WHERE project_id=? AND target_type='INTERNAL' ORDER BY created_at,id",(project_id,)).fetchall()]


class ManualExternalAdapter:
    target_type = "MANUAL_EXTERNAL"
    capabilities = CAPABILITIES[target_type]

    def create_work_item(self, db, request: TargetCreateRequest) -> TargetItem:
        if not request.external_reference:
            raise TargetCreateFailed("Manual external work requires an explicit reference")
        return TargetItem(request.external_reference, request.title, request.description, request.owner_role,
                          request.priority, request.milestone_ref, request.dependencies)

    def get_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[TargetItem]:
        row = db.execute(
            "SELECT * FROM execution_items WHERE project_id=? AND target_type='MANUAL_EXTERNAL' AND external_id=?",
            (project_id, external_id),
        ).fetchone()
        return _row_target(row) if row else None

    def update_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str, changes: dict) -> TargetItem:
        raise TargetUnavailable("Manual external work must be changed in its owning system")

    def list_project_work(self, db, project_id: str, binding_id: Optional[str]) -> list[TargetItem]:
        return [_row_target(row) for row in db.execute("SELECT * FROM execution_items WHERE project_id=? AND target_type='MANUAL_EXTERNAL' ORDER BY created_at,id",(project_id,)).fetchall()]


class PmAgainExecutionAdapter:
    """Authorized service-user adapter to PM Again's normal project/task API."""
    target_type = "PM_AGAIN"
    capabilities = CAPABILITIES[target_type]

    def __init__(self):
        if not settings.pm_again_configured:
            raise TargetUnavailable("PM Again URL and service credential are required")
        self.base = settings.pm_again_url.rstrip("/")
        headers = {"Authorization": f"Bearer {settings.pm_again_api_key}"} if settings.pm_again_api_key else {}
        self.client = httpx.Client(base_url=self.base, headers=headers,
                                   timeout=settings.integration_timeout_seconds)
        if not settings.pm_again_api_key:
            try:
                response = self.client.post("/api/auth/login", json={
                    "email": settings.pm_again_email,
                    "password": settings.pm_again_password,
                })
            except httpx.HTTPError as exc:
                raise TargetUnavailable("PM Again service account login was unavailable") from exc
            if response.status_code != 200:
                raise TargetUnavailable("PM Again service account authentication failed")
            if response.json().get("must_change_password"):
                raise TargetUnavailable("PM Again service account requires a password change")

    def _request(self, method: str, path: str, json_body=None):
        try:
            response = self.client.request(method, path, json=json_body)
        except httpx.TimeoutException as exc:
            raise TargetTimeout("PM Again timed out; reconciliation is required") from exc
        if response.status_code == 404: return None
        if response.status_code >= 400:
            raise TargetCreateFailed(f"PM Again returned HTTP {response.status_code}")
        return response.json()

    def _binding(self, db, project_id, binding_id):
        row = db.execute("SELECT * FROM execution_bindings WHERE id=? AND project_id=? AND target_type='PM_AGAIN'",
                         (binding_id, project_id)).fetchone()
        if not row or row["status"] != "READY": raise TargetUnavailable("PM Again binding is not READY")
        return row

    def verify_project(self, external_project_id: str) -> dict:
        value = self._request("GET", f"/api/projects/{external_project_id}")
        if not value: raise TargetUnavailable("PM Again project was not found")
        return value

    @staticmethod
    def _item(x) -> TargetItem:
        status = {"Todo":"NOT_STARTED", "InProgress":"IN_PROGRESS", "Blocked":"BLOCKED",
                  "Done":"COMPLETED", "Cancelled":"CANCELLED"}.get(x.get("status"), "NOT_STARTED")
        description = x.get("description") or x.get("desc") or ""
        description = description.split("\n\nOIDA-IDEMPOTENCY: ", 1)[0]
        return TargetItem(str(x["id"]), x.get("title", ""), description,
                          x.get("owner") or x.get("owner_role"),
                          {"High":"HIGH", "Med":"MEDIUM", "Low":"LOW"}.get(x.get("priority"), x.get("priority", "MEDIUM")),
                          None, [], status, x.get("url"))

    def create_work_item(self, db, request: TargetCreateRequest) -> TargetItem:
        binding = self._binding(db, request.project_id, request.binding_id)
        # Stable OIDA key lets a retry recover an ambiguous create without duplication.
        stable_key = request.idempotency_key
        for raw in self._list_project_work(binding):
            description = raw.get("description") or raw.get("desc") or ""
            if f"OIDA-IDEMPOTENCY: {stable_key}" in description:
                return self._item(raw)
        body = {"title": request.title,
                "description": f"{request.description}\n\nOIDA-IDEMPOTENCY: {stable_key}",
                "owner": request.owner_role,
                "priority": {"HIGH":"High", "MEDIUM":"Med", "LOW":"Low"}.get(request.priority, "Med"),
                "status": "Todo", "phase": request.milestone_ref}
        value = self._request("POST", f"/api/{binding['external_project_id']}/tasks", body)
        if not value: raise TargetCreateFailed("PM Again create returned no item")
        return self._item(value)

    def get_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[TargetItem]:
        return next((x for x in self.list_project_work(db, project_id, binding_id) if x.external_id == str(external_id)), None)

    def update_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str, changes: dict) -> TargetItem:
        binding = self._binding(db, project_id, binding_id)
        body = dict(changes)
        if "owner_role" in body: body["owner"] = body.pop("owner_role")
        if "priority" in body: body["priority"] = {"HIGH":"High", "MEDIUM":"Med", "LOW":"Low"}.get(body["priority"], body["priority"])
        if "status" in body: body["status"] = {"NOT_STARTED":"Todo", "IN_PROGRESS":"InProgress", "BLOCKED":"Blocked", "COMPLETED":"Done", "CANCELLED":"Cancelled"}.get(body["status"], body["status"])
        value = self._request("PUT", f"/api/{binding['external_project_id']}/tasks/{external_id}", body)
        if not value: raise TargetCreateFailed("PM Again task is unavailable")
        return self._item(value)

    def list_project_work(self, db, project_id: str, binding_id: Optional[str]) -> list[TargetItem]:
        binding = self._binding(db, project_id, binding_id)
        return [self._item(x) for x in self._list_project_work(binding)]

    def _list_project_work(self, binding) -> list[dict]:
        return self._request("GET", f"/api/{binding['external_project_id']}/tasks") or []


class DeterministicExternalAdapter:
    """In-memory adapter for contract tests. It is never reported as live PM Again."""
    target_type = "PM_AGAIN"
    capabilities = CAPABILITIES[target_type]

    def __init__(self, mode: str = "confirmed"):
        self.mode = mode
        self.items: dict[str, TargetItem] = {}
        self.creates = 0

    def create_work_item(self, db, request: TargetCreateRequest) -> TargetItem:
        if self.mode == "timeout":
            raise TargetTimeout("simulated target timeout")
        if self.mode == "failure":
            raise TargetCreateFailed("simulated target failure")
        external_id = f"pm-{request.idempotency_key}"
        if external_id not in self.items:
            self.creates += 1
            self.items[external_id] = TargetItem(external_id, request.title, request.description, request.owner_role,
                                                 request.priority, request.milestone_ref, request.dependencies,
                                                 external_url=f"https://pm.invalid/tasks/{external_id}")
        return self.items[external_id]

    def verify_project(self, external_project_id: str) -> dict:
        if self.mode == "failure": raise TargetUnavailable("simulated target failure")
        return {"id": external_project_id, "name": "Deterministic PM Project"}

    def get_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[TargetItem]:
        if self.mode == "readback_missing":
            return None
        return self.items.get(external_id)

    def update_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str, changes: dict) -> TargetItem:
        item=self.items.get(external_id)
        if not item: raise TargetCreateFailed("simulated target item is unavailable")
        for key,value in changes.items():
            if hasattr(item,key):setattr(item,key,value)
        return item

    def list_project_work(self, db, project_id: str, binding_id: Optional[str]) -> list[TargetItem]:
        return list(self.items.values())


def adapter_for_target(target_type: str) -> ExecutionTargetAdapter:
    if target_type == "INTERNAL":
        return InternalExecutionAdapter()
    if target_type == "MANUAL_EXTERNAL":
        return ManualExternalAdapter()
    if target_type == "PM_AGAIN":
        return PmAgainExecutionAdapter()
    raise TargetUnavailable("Unsupported execution target")
