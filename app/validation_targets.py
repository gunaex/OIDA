from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class ValidationTargetCapabilities:
    target_type: str
    supports_result_read: bool
    supports_evidence_reference: bool
    supports_owner_assignment: bool
    supports_automation: bool

    def as_dict(self) -> dict:
        return self.__dict__.copy()


CAPABILITIES = {
    "INTERNAL": ValidationTargetCapabilities("INTERNAL", True, True, True, False),
    "QA_AGAIN": ValidationTargetCapabilities("QA_AGAIN", True, True, True, True),
    "MANUAL_EXTERNAL": ValidationTargetCapabilities("MANUAL_EXTERNAL", True, True, True, False),
}


@dataclass
class ValidationCreateRequest:
    validation_item_id: str
    project_id: str
    binding_id: Optional[str]
    title: str
    objective: str
    expected_result: str
    owner_role: str
    idempotency_key: str
    external_reference: Optional[str] = None


@dataclass
class ValidationTargetItem:
    external_id: str
    title: str
    objective: str
    expected_result: str
    owner_role: str
    status: str = "NOT_STARTED"
    external_url: Optional[str] = None


class ValidationTargetError(Exception):
    code = "VALIDATION_TARGET_ERROR"


class ValidationTargetUnavailable(ValidationTargetError):
    code = "VALIDATION_TARGET_UNAVAILABLE"


class ValidationTargetTimeout(ValidationTargetError):
    code = "VALIDATION_TARGET_TIMEOUT"


class ValidationTargetCreateFailed(ValidationTargetError):
    code = "VALIDATION_TARGET_CREATE_FAILED"


class ValidationTargetAdapter(Protocol):
    target_type: str
    capabilities: ValidationTargetCapabilities
    def create_validation_item(self, db, request: ValidationCreateRequest) -> ValidationTargetItem: ...
    def get_validation_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[ValidationTargetItem]: ...
    def list_project_validation(self, db, project_id: str, binding_id: Optional[str]) -> list[ValidationTargetItem]: ...
    def get_evidence_reference(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[str]: ...


def _from_row(row) -> ValidationTargetItem:
    return ValidationTargetItem(row["external_id"] or row["id"],row["title"],row["objective"],row["expected_result"],row["owner_role"],row["execution_status"],row["external_url"])


class InternalValidationAdapter:
    target_type="INTERNAL";capabilities=CAPABILITIES[target_type]
    def create_validation_item(self, db, request: ValidationCreateRequest) -> ValidationTargetItem:
        row=db.execute("SELECT * FROM validation_items WHERE id=? AND project_id=?",(request.validation_item_id,request.project_id)).fetchone()
        if not row:raise ValidationTargetCreateFailed("Internal validation item is unavailable")
        return _from_row(row)
    def get_validation_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[ValidationTargetItem]:
        row=db.execute("SELECT * FROM validation_items WHERE project_id=? AND target_type='INTERNAL' AND (external_id=? OR id=?)",(project_id,external_id,external_id)).fetchone()
        return _from_row(row) if row else None
    def list_project_validation(self, db, project_id: str, binding_id: Optional[str]) -> list[ValidationTargetItem]:
        return [_from_row(x) for x in db.execute("SELECT * FROM validation_items WHERE project_id=? AND target_type='INTERNAL'",(project_id,)).fetchall()]
    def get_evidence_reference(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[str]:
        row=db.execute("SELECT storage_reference FROM evidence_records WHERE project_id=? AND validation_item_id=? AND status='VALID' ORDER BY created_at DESC LIMIT 1",(project_id,external_id)).fetchone();return row[0] if row else None


class ManualExternalValidationAdapter:
    target_type="MANUAL_EXTERNAL";capabilities=CAPABILITIES[target_type]
    def create_validation_item(self, db, request: ValidationCreateRequest) -> ValidationTargetItem:
        if not request.external_reference:raise ValidationTargetCreateFailed("Manual external validation requires an explicit reference")
        return ValidationTargetItem(request.external_reference,request.title,request.objective,request.expected_result,request.owner_role,external_url=request.external_reference if request.external_reference.startswith("https://") else None)
    def get_validation_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[ValidationTargetItem]:
        row=db.execute("SELECT * FROM validation_items WHERE project_id=? AND target_type='MANUAL_EXTERNAL' AND external_id=?",(project_id,external_id)).fetchone();return _from_row(row) if row else None
    def list_project_validation(self, db, project_id: str, binding_id: Optional[str]) -> list[ValidationTargetItem]:
        return [_from_row(x) for x in db.execute("SELECT * FROM validation_items WHERE project_id=? AND target_type='MANUAL_EXTERNAL'",(project_id,)).fetchall()]
    def get_evidence_reference(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[str]:return None


class QAAgainValidationAdapter:
    """Contract boundary only: QA Again accepts CONDUCTOR_MAIN service identity, not OIDA."""
    target_type="QA_AGAIN";capabilities=CAPABILITIES[target_type]
    def _blocked(self):raise ValidationTargetUnavailable("QA Again has no authorized OIDA service binding in this environment")
    def create_validation_item(self, db, request: ValidationCreateRequest) -> ValidationTargetItem:self._blocked()
    def get_validation_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[ValidationTargetItem]:self._blocked()
    def list_project_validation(self, db, project_id: str, binding_id: Optional[str]) -> list[ValidationTargetItem]:self._blocked()
    def get_evidence_reference(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[str]:self._blocked()


class DeterministicValidationAdapter:
    """Test-only QA Again contract adapter; never reported as live."""
    target_type="QA_AGAIN";capabilities=CAPABILITIES[target_type]
    def __init__(self,mode="confirmed"):self.mode=mode;self.items={};self.creates=0
    def create_validation_item(self, db, request: ValidationCreateRequest) -> ValidationTargetItem:
        if self.mode=="timeout":raise ValidationTargetTimeout("simulated QA target timeout")
        if self.mode=="failure":raise ValidationTargetCreateFailed("simulated QA target failure")
        external_id=f"qa-{request.idempotency_key}"
        if external_id not in self.items:self.creates+=1;self.items[external_id]=ValidationTargetItem(external_id,request.title,request.objective,request.expected_result,request.owner_role,external_url=f"https://qa.invalid/items/{external_id}")
        return self.items[external_id]
    def get_validation_item(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[ValidationTargetItem]:
        return None if self.mode=="readback_missing" else self.items.get(external_id)
    def list_project_validation(self, db, project_id: str, binding_id: Optional[str]) -> list[ValidationTargetItem]:return list(self.items.values())
    def get_evidence_reference(self, db, project_id: str, binding_id: Optional[str], external_id: str) -> Optional[str]:return None


def adapter_for_validation_target(target_type: str) -> ValidationTargetAdapter:
    if target_type=="INTERNAL":return InternalValidationAdapter()
    if target_type=="MANUAL_EXTERNAL":return ManualExternalValidationAdapter()
    if target_type=="QA_AGAIN":return QAAgainValidationAdapter()
    raise ValidationTargetUnavailable("Unsupported validation target")
