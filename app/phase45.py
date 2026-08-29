from __future__ import annotations

from datetime import datetime, timezone
import json
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import Actor, current_actor, require_project
from .config import settings
from .db import connect, now, transaction
from .document_sources import (DocumentSourceError, DocumentSourceInvalid,
                               DocumentSourceUnavailable, adapter_for_document)
from .main import audit, dumps, uid

router = APIRouter(prefix="/api/projects/{project_id}/integrations", tags=["pilot-integrations"])


class DocumentBindingIn(BaseModel):
    external_project_id: str = Field(min_length=1, max_length=200)


class DocumentImportIn(BaseModel):
    document_id: str = Field(min_length=1, max_length=200)


def _owner(actor: Actor, project_id: str):
    if actor.actor_type != "HUMAN": raise HTTPException(403, "Human project owner authority is required")
    return require_project(actor, project_id, owner=True)


def _event(db, project_id, operation, status, started, failure_code=None):
    db.execute("INSERT INTO integration_events VALUES (?,?,?,?,?,?,?,?)",
               (uid("intevt"), project_id, "DOCUMENT_AGAIN", operation, status,
                round((time.monotonic() - started) * 1000, 2), failure_code, now()))


@router.get("/readiness")
def integration_readiness(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db:
        document = db.execute("SELECT status,failure_code,last_verified_at FROM document_bindings WHERE project_id=?", (project_id,)).fetchone()
        pm = db.execute("SELECT status,last_verified_at FROM execution_bindings WHERE project_id=? AND target_type='PM_AGAIN'", (project_id,)).fetchone()
    return {
        "document_again": dict(document) if document else {"status": "UNBOUND", "live_configuration": "CONFIGURED" if settings.document_again_url and settings.document_again_api_key else "BLOCKED_NOT_CONFIGURED"},
        "pm_again": dict(pm) if pm else {"status": "UNBOUND", "live_configuration": "CONFIGURED" if settings.pm_again_url and settings.pm_again_api_key else "BLOCKED_NOT_CONFIGURED"},
    }


@router.get("/document-again/projects")
def discover_document_projects(project_id: str, actor: Actor = Depends(current_actor)):
    _owner(actor, project_id)
    try: return [x.__dict__ for x in adapter_for_document().list_projects()]
    except DocumentSourceError as exc: raise HTTPException(503, detail={"code": exc.code, "message": str(exc)})


@router.post("/document-again/binding", status_code=201)
def bind_document_project(project_id: str, body: DocumentBindingIn, actor: Actor = Depends(current_actor)):
    _owner(actor, project_id); started = time.monotonic()
    with transaction() as db:
        if db.execute("SELECT 1 FROM document_bindings WHERE project_id=?", (project_id,)).fetchone():
            raise HTTPException(409, "Document Again binding already exists")
        binding_id, stamp = uid("docbind"), now()
        try:
            external = adapter_for_document().get_project(body.external_project_id)
            status, failure = "READY", None
        except DocumentSourceInvalid as exc:
            external, status, failure = None, "INVALID", exc.code
        except DocumentSourceError as exc:
            external, status, failure = None, "ERROR", exc.code
        db.execute("INSERT INTO document_bindings VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (binding_id, project_id, "DOCUMENT_AGAIN", body.external_project_id,
                    external.name if external else None, status, failure, stamp if status == "READY" else None,
                    actor.id, stamp, stamp))
        _event(db, project_id, "BIND_PROJECT", status, started, failure)
        audit(db, project_id, actor.id, "HUMAN", "DOCUMENT_BINDING_VERIFIED", "DOCUMENT_BINDING", binding_id,
              "SUCCESS" if status == "READY" else "FAILED", {"status": status, "failure_code": failure})
    return {"id": binding_id, "status": status, "external_project_id": body.external_project_id,
            "external_project_name": external.name if external else None, "failure_code": failure}


def _binding(db, project_id):
    row = db.execute("SELECT * FROM document_bindings WHERE project_id=?", (project_id,)).fetchone()
    if not row: raise HTTPException(409, "Document Again is unbound")
    if row["status"] not in {"READY", "STALE", "PARTIAL"}: raise HTTPException(409, f"Document binding is {row['status']}")
    return row


@router.get("/document-again/documents")
def list_documents(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db: binding = _binding(db, project_id)
    try: return [x.__dict__ for x in adapter_for_document().list_documents(binding["external_project_id"])]
    except DocumentSourceError as exc: raise HTTPException(503, detail={"code": exc.code, "message": str(exc)})


@router.post("/document-again/import", status_code=201)
def import_document(project_id: str, body: DocumentImportIn, actor: Actor = Depends(current_actor)):
    _owner(actor, project_id); started = time.monotonic()
    with transaction() as db:
        binding = _binding(db, project_id)
        try: document = adapter_for_document().get_document(binding["external_project_id"], body.document_id)
        except DocumentSourceError as exc:
            _event(db, project_id, "IMPORT_DOCUMENT", "ERROR", started, exc.code)
            raise HTTPException(503, detail={"code": exc.code, "message": str(exc)})
        existing = db.execute("SELECT r.*,c.title FROM document_source_refs r JOIN project_context_items c ON c.id=r.context_item_id WHERE r.binding_id=? AND r.external_document_id=? AND r.external_revision_id=?",
                              (binding["id"], document.id, document.revision_id)).fetchone()
        if existing:
            return {"id": existing["id"], "context_item_id": existing["context_item_id"], "status": existing["status"], "deduplicated": True}
        if len(document.content) < 10: raise HTTPException(422, "Document content is empty or too short")
        context_id, ref_id, stamp = uid("ctx"), uid("docref"), now()
        db.execute("INSERT INTO project_context_items VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (context_id, project_id, "DOCUMENT", document.title, document.content, "ACTIVE", 1, actor.id, stamp, stamp))
        db.execute("UPDATE projects SET context_revision=context_revision+1,updated_at=? WHERE id=?", (stamp, project_id))
        db.execute("INSERT INTO document_source_refs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (ref_id, project_id, binding["id"], context_id, document.id, document.title,
                    document.revision_id, document.revision_number, document.sha256, "READY", stamp,
                    actor.id, stamp))
        _event(db, project_id, "IMPORT_DOCUMENT", "READY", started)
        audit(db, project_id, actor.id, "HUMAN", "DOCUMENT_REVISION_IMPORTED", "DOCUMENT_SOURCE_REF", ref_id,
              detail={"external_document_id": document.id, "external_revision_id": document.revision_id,
                      "content_sha256": document.sha256})
    return {"id": ref_id, "context_item_id": context_id, "status": "READY", "revision_id": document.revision_id,
            "content_sha256": document.sha256, "deduplicated": False}


@router.post("/document-again:refresh")
def refresh_documents(project_id: str, actor: Actor = Depends(current_actor)):
    _owner(actor, project_id); changed = 0; checked = 0
    with transaction() as db:
        binding = _binding(db, project_id); adapter = adapter_for_document()
        for ref in db.execute("SELECT * FROM document_source_refs WHERE project_id=? AND status!='DISCONNECTED'", (project_id,)).fetchall():
            checked += 1
            try:
                current = adapter.get_document(binding["external_project_id"], ref["external_document_id"])
                status = "STALE" if current.revision_id != ref["external_revision_id"] or current.sha256 != ref["content_sha256"] else "READY"
            except DocumentSourceError: status = "ERROR"
            if status != "READY": changed += 1
            db.execute("UPDATE document_source_refs SET status=?,last_checked_at=? WHERE id=?", (status, now(), ref["id"]))
        aggregate = "STALE" if any(x[0] == "STALE" for x in db.execute("SELECT status FROM document_source_refs WHERE project_id=?", (project_id,))) else "READY"
        db.execute("UPDATE document_bindings SET status=?,last_verified_at=?,updated_at=? WHERE id=?", (aggregate, now(), now(), binding["id"]))
        audit(db, project_id, actor.id, "HUMAN", "DOCUMENT_SOURCES_REFRESHED", "DOCUMENT_BINDING", binding["id"], detail={"checked": checked, "attention": changed})
    return {"status": aggregate, "checked": checked, "attention": changed, "automatic_rebaseline": False}


@router.get("/document-again/sources")
def source_provenance(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db:
        rows = db.execute("SELECT r.*,c.title context_title FROM document_source_refs r JOIN project_context_items c ON c.id=r.context_item_id WHERE r.project_id=? ORDER BY r.imported_at", (project_id,)).fetchall()
        baseline = db.execute("SELECT frozen_at FROM requirement_baselines WHERE project_id=? ORDER BY version DESC LIMIT 1", (project_id,)).fetchone()
    return [{**dict(x), "newer_than_requirement_baseline": bool(baseline and x["imported_at"] > baseline["frozen_at"])} for x in rows]


def integration_truth_projection(project_id: str) -> dict:
    with connect() as db:
        binding = db.execute("SELECT status,last_verified_at,failure_code FROM document_bindings WHERE project_id=?", (project_id,)).fetchone()
        refs = {x["status"]: x["n"] for x in db.execute("SELECT status,COUNT(*) n FROM document_source_refs WHERE project_id=? GROUP BY status", (project_id,)).fetchall()}
    status = binding["status"] if binding else "UNBOUND"
    return {"document_binding_status": status, "document_sources": {"ready": refs.get("READY", 0), "stale": refs.get("STALE", 0), "error": refs.get("ERROR", 0)},
            "document_live_status": "CONFIGURED" if settings.document_again_url and settings.document_again_api_key else "BLOCKED_NOT_CONFIGURED"}
