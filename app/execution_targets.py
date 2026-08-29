from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


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
    "PM_AGAIN": TargetCapabilities("PM_AGAIN", True, True, True, True, False, True),
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
    """Contract boundary only; PM Again has no configured service task-write API in this environment."""
    target_type = "PM_AGAIN"
    capabilities = CAPABILITIES[target_type]

    def create_work_item(self, db, request: TargetCreateRequest) -> TargetItem:
        raise TargetUnavailable("PM Again service task-write integration is not configured")

    def get_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[TargetItem]:
        raise TargetUnavailable("PM Again service task-read integration is not configured")

    def update_work_item(self, db, project_id: str, binding_id: Optional[str], external_id: str, changes: dict) -> TargetItem:
        raise TargetUnavailable("PM Again service task-update integration is not configured")

    def list_project_work(self, db, project_id: str, binding_id: Optional[str]) -> list[TargetItem]:
        raise TargetUnavailable("PM Again service task-list integration is not configured")


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
