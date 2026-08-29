from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
import time
import uuid
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai import AIError, ContextInput, adapter_for
from .auth import Actor, bootstrap_user, current_actor, issue_session, require_project, verify_password
from .config import settings
from .db import connect, migrate, now, transaction

log = logging.getLogger("oida")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def dumps(value) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def unpack(row):
    if row is None: return None
    data = dict(row)
    for key in list(data):
        if key.endswith("_json"):
            data[key[:-5]] = json.loads(data.pop(key))
    return data


def audit(db, project_id, actor_id, actor_type, action, target_type, target_id, result="SUCCESS", detail=None):
    db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?)", (
        uid("aud"), project_id, actor_id, actor_type, action, target_type, target_id,
        result, dumps(detail or {}), now()))
    log.info(dumps({"project_id": project_id, "actor_id": actor_id, "actor_type": actor_type,
                    "action": action, "target_id": target_id, "result": result}))


def idem_get(db, project, actor, action, key):
    row = db.execute("SELECT response_json FROM idempotency_records WHERE project_scope=? AND actor_id=? AND action=? AND idempotency_key=?",
                     (project, actor, action, key)).fetchone()
    return json.loads(row[0]) if row else None


def idem_put(db, project, actor, action, key, response):
    db.execute("INSERT INTO idempotency_records VALUES (?,?,?,?,?,?)",
               (project, actor, action, key, dumps(response), now()))


def require_key(value: Optional[str]) -> str:
    if not value or len(value) > 200: raise HTTPException(400, "A valid Idempotency-Key header is required")
    return value


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate()
    bootstrap_user()
    yield


app = FastAPI(title="OIDA 2.0", version="2.0-phase2", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory="web"), name="assets")


class LoginIn(BaseModel):
    email: str
    password: str


class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    objective: str = Field(min_length=10, max_length=4000)
    description: str = Field(default="", max_length=10000)


class ContextIn(BaseModel):
    source_type: Literal["PROJECT_OBJECTIVE","PASTED_TEXT","USER_NOTE","DOCUMENT","SYSTEM"] = "PASTED_TEXT"
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=10, max_length=200_000)


class ContextPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    content: Optional[str] = Field(default=None, min_length=10, max_length=200_000)


class GenerateIn(BaseModel):
    instruction: str = Field(default="", max_length=2000)


class CandidatePatch(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    statement: str = Field(min_length=10, max_length=4000)
    rationale: str = Field(min_length=3, max_length=2000)
    priority: Literal["MUST","SHOULD","COULD"]
    acceptance_criteria: list[str] = Field(min_length=1, max_length=12)


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class RequirementIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    statement: str = Field(min_length=10, max_length=4000)
    rationale: str = Field(min_length=3, max_length=2000)
    priority: Literal["MUST","SHOULD","COULD"] = "MUST"
    acceptance_criteria: list[str] = Field(min_length=1, max_length=12)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(Path("web/index.html"))


@app.get("/healthz")
def health(): return {"status": "READY", "phase": 2}


@app.post("/api/auth/login")
def login(body: LoginIn, response: Response):
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (body.email.lower(),)).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    response.set_cookie("oida_session", issue_session(row["id"]), httponly=True, samesite="strict",
                        secure=settings.cookie_secure, max_age=43200)
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"], "actor_type": "HUMAN"}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("oida_session")
    return {"status": "SIGNED_OUT"}


@app.get("/api/auth/me")
def me(actor: Actor = Depends(current_actor)): return actor.__dict__


@app.get("/api/projects")
def list_projects(actor: Actor = Depends(current_actor)):
    with connect() as db:
        rows = db.execute("SELECT p.*,m.role FROM projects p JOIN project_memberships m ON m.project_id=p.id WHERE m.user_id=? ORDER BY p.created_at DESC", (actor.id,)).fetchall()
    return [dict(x) for x in rows]


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectIn, idempotency_key: Optional[str] = Header(None), actor: Actor = Depends(current_actor)):
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, "NEW_PROJECT", actor.id, "CREATE_PROJECT", key)
        if previous: return previous
        stamp, project_id = now(), uid("prj")
        db.execute("INSERT INTO projects (id,tenant_id,name,objective,description,state,context_revision,next_requirement_number,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (project_id, "local", body.name, body.objective,
            body.description, "ACTIVE", 0, 1, actor.id, stamp, stamp))
        db.execute("INSERT INTO project_memberships VALUES (?,?,?)", (project_id, actor.id, "PROJECT_OWNER"))
        result = {"id": project_id, "name": body.name, "objective": body.objective, "description": body.description,
                  "state": "ACTIVE", "context_revision": 0, "role": "PROJECT_OWNER"}
        audit(db, project_id, actor.id, "HUMAN", "PROJECT_CREATED", "PROJECT", project_id)
        idem_put(db, "NEW_PROJECT", actor.id, "CREATE_PROJECT", key, result)
    with connect() as db:
        confirmed = db.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
    if not confirmed: raise HTTPException(500, "Project creation could not be reconciled")
    return result


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, actor: Actor = Depends(current_actor)):
    return dict(require_project(actor, project_id))


@app.get("/api/projects/{project_id}/context")
def list_context(project_id: str, actor: Actor = Depends(current_actor)):
    project = require_project(actor, project_id)
    with connect() as db:
        rows = db.execute("SELECT * FROM project_context_items WHERE project_id=? AND status='ACTIVE' ORDER BY created_at", (project_id,)).fetchall()
    return {"context_revision": project["context_revision"], "items": [dict(x) for x in rows]}


@app.post("/api/projects/{project_id}/context", status_code=201)
def add_context(project_id: str, body: ContextIn, idempotency_key: Optional[str] = Header(None), actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    if body.source_type not in {"PROJECT_OBJECTIVE","PASTED_TEXT","USER_NOTE","DOCUMENT","SYSTEM"}:
        raise HTTPException(422, "Unsupported source_type")
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, project_id, actor.id, "ADD_CONTEXT", key)
        if previous: return previous
        stamp, item_id = now(), uid("ctx")
        db.execute("INSERT INTO project_context_items VALUES (?,?,?,?,?,?,?,?,?,?)", (item_id, project_id, body.source_type,
            body.title, body.content, "ACTIVE", 1, actor.id, stamp, stamp))
        db.execute("UPDATE projects SET context_revision=context_revision+1,updated_at=? WHERE id=?", (stamp, project_id))
        revision = db.execute("SELECT context_revision FROM projects WHERE id=?", (project_id,)).fetchone()[0]
        result = {"id": item_id, "project_id": project_id, "source_type": body.source_type, "title": body.title,
                  "content": body.content, "status": "ACTIVE", "version": 1, "context_revision": revision}
        audit(db, project_id, actor.id, "HUMAN", "CONTEXT_ADDED", "CONTEXT_ITEM", item_id, detail={"context_revision": revision})
        idem_put(db, project_id, actor.id, "ADD_CONTEXT", key, result)
    return result


@app.patch("/api/projects/{project_id}/context/{item_id}")
def update_context(project_id: str, item_id: str, body: ContextPatch, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with transaction() as db:
        row = db.execute("SELECT * FROM project_context_items WHERE id=? AND project_id=?", (item_id, project_id)).fetchone()
        if not row: raise HTTPException(404, "Context item not found")
        title, content, stamp = body.title or row["title"], body.content or row["content"], now()
        db.execute("UPDATE project_context_items SET title=?,content=?,version=version+1,updated_at=? WHERE id=? AND project_id=?",
                   (title, content, stamp, item_id, project_id))
        db.execute("UPDATE projects SET context_revision=context_revision+1,updated_at=? WHERE id=?", (stamp, project_id))
        revision = db.execute("SELECT context_revision FROM projects WHERE id=?", (project_id,)).fetchone()[0]
        audit(db, project_id, actor.id, "HUMAN", "CONTEXT_UPDATED", "CONTEXT_ITEM", item_id, detail={"context_revision": revision})
        result = db.execute("SELECT * FROM project_context_items WHERE id=? AND project_id=?", (item_id, project_id)).fetchone()
    return {**dict(result), "context_revision": revision}


def generate_use_case(db, project_id: str, actor: Actor, body: GenerateIn, supersedes: Optional[str] = None):
    project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    items = [dict(x) for x in db.execute("SELECT * FROM project_context_items WHERE project_id=? AND status='ACTIVE' ORDER BY created_at", (project_id,)).fetchall()]
    run_id, stamp = uid("airun"), now()
    adapter = adapter_for()
    db.execute("INSERT INTO ai_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (run_id, project_id, actor.id, "AI", adapter.provider,
        adapter.model, "requirement-generation/v1", body.instruction, project["context_revision"], "RUNNING", None, "[]", stamp, None))
    audit(db, project_id, f"ai:{run_id}", "AI", "AI_REQUIREMENT_RUN_STARTED", "AI_RUN", run_id)
    started = time.monotonic()
    try:
        output = adapter.generate(ContextInput(project["name"], project["objective"], project["context_revision"], items), body.instruction)
        known = {x["id"] for x in items}
        if any(not set(x.source_context_item_ids).issubset(known) for x in output.candidates):
            from .ai import AIGroundingInsufficient
            raise AIGroundingInsufficient("Candidate provenance is outside current project context")
        candidate_ids = []
        for item in output.candidates:
            candidate_id = uid("cand")
            normalized = item.model_dump()
            db.execute("INSERT INTO requirement_candidates (id,project_id,ai_run_id,title,statement,rationale,priority,category,acceptance_criteria_json,source_ids_json,assumptions_json,gaps_json,confidence,grounding,status,human_modified,current_revision,original_ai_json,supersedes_candidate_id,rejection_reason,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                candidate_id, project_id, run_id, item.title, item.requirement_statement, item.rationale, item.priority,
                item.category, dumps(item.acceptance_criteria), dumps(item.source_context_item_ids), dumps(item.assumptions),
                dumps(item.questions_or_gaps), item.confidence, "SUFFICIENT", "NEEDS_REVIEW", 0, 1, dumps(normalized),
                supersedes, None, stamp, stamp))
            db.execute("INSERT INTO candidate_revisions VALUES (?,?,?,?,?,?,?,?)", (uid("crev"), candidate_id, project_id, 1,
                dumps(normalized), f"ai:{run_id}", "AI", stamp))
            candidate_ids.append(candidate_id)
        db.execute("UPDATE ai_runs SET status='SUCCEEDED',findings_json=?,completed_at=? WHERE id=?", (dumps(output.findings), now(), run_id))
        audit(db, project_id, f"ai:{run_id}", "AI", "AI_REQUIREMENT_RUN_COMPLETED", "AI_RUN", run_id,
              detail={"candidate_count": len(candidate_ids), "duration_ms": round((time.monotonic()-started)*1000, 2)})
        return {"ai_run_id": run_id, "status": "SUCCEEDED", "candidate_ids": candidate_ids, "findings": output.findings,
                "provider": adapter.provider, "model": adapter.model, "context_revision": project["context_revision"]}
    except AIError as exc:
        db.execute("UPDATE ai_runs SET status='FAILED',failure_code=?,completed_at=? WHERE id=?", (exc.code, now(), run_id))
        audit(db, project_id, f"ai:{run_id}", "AI", "AI_REQUIREMENT_RUN_FAILED", "AI_RUN", run_id, "FAILED", {"failure_code": exc.code})
        return {"ai_run_id": run_id, "status": "FAILED", "failure_code": exc.code, "message": str(exc),
                "provider": adapter.provider, "context_revision": project["context_revision"]}


@app.post("/api/projects/{project_id}/ai/requirements:generate")
def generate_requirements(project_id: str, body: GenerateIn, idempotency_key: Optional[str] = Header(None), actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, project_id, actor.id, "GENERATE_REQUIREMENTS", key)
        if previous: return previous
        result = generate_use_case(db, project_id, actor, body)
        idem_put(db, project_id, actor.id, "GENERATE_REQUIREMENTS", key, result)
    return result


@app.get("/api/projects/{project_id}/ai-runs")
def list_runs(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db:
        rows = db.execute("SELECT * FROM ai_runs WHERE project_id=? ORDER BY started_at DESC", (project_id,)).fetchall()
    return [unpack(x) for x in rows]


@app.get("/api/projects/{project_id}/requirement-candidates")
def list_candidates(project_id: str, actor: Actor = Depends(current_actor)):
    project = require_project(actor, project_id)
    with connect() as db:
        rows = db.execute("SELECT c.*,r.context_revision AS ai_context_revision FROM requirement_candidates c JOIN ai_runs r ON r.id=c.ai_run_id WHERE c.project_id=? ORDER BY c.created_at", (project_id,)).fetchall()
    result = []
    for row in rows:
        item = unpack(row)
        item["stale"] = item["ai_context_revision"] < project["context_revision"] and item["status"] == "NEEDS_REVIEW"
        result.append(item)
    return result


@app.patch("/api/projects/{project_id}/requirement-candidates/{candidate_id}")
def edit_candidate(project_id: str, candidate_id: str, body: CandidatePatch, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    if body.priority not in {"MUST","SHOULD","COULD"}: raise HTTPException(422, "Invalid priority")
    with transaction() as db:
        row = db.execute("SELECT * FROM requirement_candidates WHERE id=? AND project_id=?", (candidate_id, project_id)).fetchone()
        if not row: raise HTTPException(404, "Candidate not found")
        if row["status"] != "NEEDS_REVIEW": raise HTTPException(409, "Only candidates needing review can be edited")
        revision, stamp = row["current_revision"] + 1, now()
        current = {"title": body.title, "requirement_statement": body.statement, "rationale": body.rationale,
                   "priority": body.priority, "category": row["category"], "acceptance_criteria": body.acceptance_criteria,
                   "source_context_item_ids": json.loads(row["source_ids_json"]), "assumptions": json.loads(row["assumptions_json"]),
                   "questions_or_gaps": json.loads(row["gaps_json"]), "confidence": row["confidence"]}
        db.execute("UPDATE requirement_candidates SET title=?,statement=?,rationale=?,priority=?,acceptance_criteria_json=?,human_modified=1,current_revision=?,updated_at=? WHERE id=? AND project_id=?",
                   (body.title, body.statement, body.rationale, body.priority, dumps(body.acceptance_criteria), revision, stamp, candidate_id, project_id))
        db.execute("INSERT INTO candidate_revisions VALUES (?,?,?,?,?,?,?,?)", (uid("crev"), candidate_id, project_id, revision,
            dumps(current), actor.id, "HUMAN", stamp))
        audit(db, project_id, actor.id, "HUMAN", "CANDIDATE_EDITED", "REQUIREMENT_CANDIDATE", candidate_id, detail={"revision": revision})
    return {"id": candidate_id, "status": "NEEDS_REVIEW", "human_modified": True, "current_revision": revision}


def next_requirement(db, project_id):
    number = db.execute("SELECT next_requirement_number FROM projects WHERE id=?", (project_id,)).fetchone()[0]
    db.execute("UPDATE projects SET next_requirement_number=next_requirement_number+1,updated_at=? WHERE id=?", (now(), project_id))
    return f"REQ-{number:03d}"


@app.post("/api/projects/{project_id}/requirement-candidates/{candidate_id}:accept")
def accept_candidate(project_id: str, candidate_id: str, idempotency_key: Optional[str] = Header(None), actor: Actor = Depends(current_actor)):
    project = require_project(actor, project_id)
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, project_id, actor.id, "ACCEPT_CANDIDATE", key)
        if previous: return previous
        candidate = db.execute("SELECT c.*,r.context_revision AS ai_context_revision FROM requirement_candidates c JOIN ai_runs r ON r.id=c.ai_run_id WHERE c.id=? AND c.project_id=?", (candidate_id, project_id)).fetchone()
        if not candidate: raise HTTPException(404, "Candidate not found")
        existing = db.execute("SELECT * FROM requirements WHERE source_candidate_id=? AND project_id=?", (candidate_id, project_id)).fetchone()
        if existing:
            result = {"requirement_id": existing["id"], "requirement_code": existing["requirement_code"], "reconciliation": "CONFIRMED"}
            idem_put(db, project_id, actor.id, "ACCEPT_CANDIDATE", key, result)
            return result
        if candidate["status"] != "NEEDS_REVIEW": raise HTTPException(409, "Candidate is not available for acceptance")
        if candidate["ai_context_revision"] < project["context_revision"]: raise HTTPException(409, "Candidate is stale; regenerate it before acceptance")
        req_id, rev_id, stamp, code = uid("req"), uid("rrev"), now(), next_requirement(db, project_id)
        db.execute("INSERT INTO requirements VALUES (?,?,?,?,?,?,?,?,?,?,?)", (req_id, project_id, code, "AI", candidate_id,
            "COMMITTED", 1, actor.id, actor.id, stamp, stamp))
        db.execute("INSERT INTO requirement_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (rev_id, req_id, project_id, 1,
            candidate["title"], candidate["statement"], candidate["rationale"], candidate["priority"],
            candidate["acceptance_criteria_json"], candidate["source_ids_json"], actor.id, stamp))
        db.execute("UPDATE requirement_candidates SET status='ACCEPTED',updated_at=? WHERE id=? AND project_id=?", (stamp, candidate_id, project_id))
        result = {"requirement_id": req_id, "requirement_code": code, "revision_id": rev_id, "revision": 1, "reconciliation": "CONFIRMED"}
        audit(db, project_id, actor.id, "HUMAN", "CANDIDATE_ACCEPTED", "REQUIREMENT_CANDIDATE", candidate_id, detail=result)
        idem_put(db, project_id, actor.id, "ACCEPT_CANDIDATE", key, result)
    with connect() as db:
        readback = db.execute("SELECT r.id,rr.id revision_id FROM requirements r JOIN requirement_revisions rr ON rr.requirement_id=r.id AND rr.revision=r.current_revision WHERE r.id=? AND r.project_id=?", (req_id, project_id)).fetchone()
    if not readback or readback["revision_id"] != rev_id: raise HTTPException(503, "ACTION_SUCCEEDED_RESOLUTION_UNCONFIRMED")
    return result


@app.post("/api/projects/{project_id}/requirement-candidates/{candidate_id}:reject")
def reject_candidate(project_id: str, candidate_id: str, body: RejectIn, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with transaction() as db:
        row = db.execute("SELECT status FROM requirement_candidates WHERE id=? AND project_id=?", (candidate_id, project_id)).fetchone()
        if not row: raise HTTPException(404, "Candidate not found")
        if row["status"] == "ACCEPTED": raise HTTPException(409, "Committed candidate cannot be rejected")
        db.execute("UPDATE requirement_candidates SET status='REJECTED',rejection_reason=?,updated_at=? WHERE id=? AND project_id=?",
                   (body.reason, now(), candidate_id, project_id))
        audit(db, project_id, actor.id, "HUMAN", "CANDIDATE_REJECTED", "REQUIREMENT_CANDIDATE", candidate_id, detail={"reason": body.reason})
    return {"id": candidate_id, "status": "REJECTED"}


@app.post("/api/projects/{project_id}/requirement-candidates/{candidate_id}:regenerate")
def regenerate_candidate(project_id: str, candidate_id: str, body: GenerateIn, idempotency_key: Optional[str] = Header(None), actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, project_id, actor.id, "REGENERATE_CANDIDATE", key)
        if previous: return previous
        row = db.execute("SELECT status FROM requirement_candidates WHERE id=? AND project_id=?", (candidate_id, project_id)).fetchone()
        if not row: raise HTTPException(404, "Candidate not found")
        result = generate_use_case(db, project_id, actor, body, candidate_id)
        if result["status"] == "SUCCEEDED":
            db.execute("UPDATE requirement_candidates SET status='SUPERSEDED',updated_at=? WHERE id=? AND project_id=? AND status!='ACCEPTED'", (now(), candidate_id, project_id))
        audit(db, project_id, actor.id, "HUMAN", "CANDIDATE_REGENERATED", "REQUIREMENT_CANDIDATE", candidate_id, result=result["status"])
        idem_put(db, project_id, actor.id, "REGENERATE_CANDIDATE", key, result)
    return result


def requirement_view(row):
    return unpack(row)


@app.get("/api/projects/{project_id}/requirements")
def list_requirements(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db:
        rows = db.execute("SELECT r.*,rr.id revision_id,rr.title,rr.statement,rr.rationale,rr.priority,rr.acceptance_criteria_json,rr.source_ids_json "
            "FROM requirements r JOIN requirement_revisions rr ON rr.requirement_id=r.id AND rr.revision=r.current_revision WHERE r.project_id=? ORDER BY r.requirement_code", (project_id,)).fetchall()
    return [requirement_view(x) for x in rows]


def create_manual_use_case(db, project_id, actor, body):
    req_id, rev_id, stamp, code = uid("req"), uid("rrev"), now(), next_requirement(db, project_id)
    db.execute("INSERT INTO requirements VALUES (?,?,?,?,?,?,?,?,?,?,?)", (req_id, project_id, code, "HUMAN", None,
        "COMMITTED", 1, actor.id, None, stamp, stamp))
    db.execute("INSERT INTO requirement_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (rev_id, req_id, project_id, 1,
        body.title, body.statement, body.rationale, body.priority, dumps(body.acceptance_criteria), "[]", actor.id, stamp))
    audit(db, project_id, actor.id, "HUMAN", "REQUIREMENT_CREATED", "REQUIREMENT", req_id, detail={"origin": "HUMAN", "requirement_code": code})
    return {"requirement_id": req_id, "requirement_code": code, "revision_id": rev_id, "revision": 1, "origin": "HUMAN"}


@app.post("/api/projects/{project_id}/requirements", status_code=201)
def create_manual_requirement(project_id: str, body: RequirementIn, idempotency_key: Optional[str] = Header(None), actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, project_id, actor.id, "CREATE_MANUAL_REQUIREMENT", key)
        if previous: return previous
        result = create_manual_use_case(db, project_id, actor, body)
        idem_put(db, project_id, actor.id, "CREATE_MANUAL_REQUIREMENT", key, result)
    return result


@app.patch("/api/projects/{project_id}/requirements/{requirement_id}")
def edit_requirement(project_id: str, requirement_id: str, body: RequirementIn, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with transaction() as db:
        row = db.execute("SELECT * FROM requirements WHERE id=? AND project_id=?", (requirement_id, project_id)).fetchone()
        if not row: raise HTTPException(404, "Requirement not found")
        revision, rev_id, stamp = row["current_revision"] + 1, uid("rrev"), now()
        old_sources = db.execute("SELECT source_ids_json FROM requirement_revisions WHERE requirement_id=? AND revision=?", (requirement_id, row["current_revision"])).fetchone()[0]
        db.execute("INSERT INTO requirement_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (rev_id, requirement_id, project_id,
            revision, body.title, body.statement, body.rationale, body.priority, dumps(body.acceptance_criteria), old_sources, actor.id, stamp))
        db.execute("UPDATE requirements SET current_revision=?,updated_at=? WHERE id=? AND project_id=?", (revision, stamp, requirement_id, project_id))
        audit(db, project_id, actor.id, "HUMAN", "REQUIREMENT_EDITED", "REQUIREMENT", requirement_id, detail={"revision": revision})
    return {"requirement_id": requirement_id, "revision_id": rev_id, "revision": revision}


def baseline_readiness(db, project_id):
    count = db.execute("SELECT COUNT(*) FROM requirements WHERE project_id=? AND status='COMMITTED'", (project_id,)).fetchone()[0]
    project = db.execute("SELECT state,context_revision FROM projects WHERE id=?", (project_id,)).fetchone()
    stale = db.execute("SELECT COUNT(*) FROM requirement_candidates c JOIN ai_runs r ON r.id=c.ai_run_id WHERE c.project_id=? AND c.status='NEEDS_REVIEW' AND r.context_revision<?", (project_id, project["context_revision"])).fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM requirement_candidates WHERE project_id=? AND status='NEEDS_REVIEW'", (project_id,)).fetchone()[0]
    invalid = db.execute("SELECT COUNT(*) FROM requirement_revisions rr JOIN requirements r ON r.id=rr.requirement_id AND r.current_revision=rr.revision WHERE r.project_id=? AND (trim(rr.statement)='' OR trim(rr.title)='' OR rr.acceptance_criteria_json='[]')", (project_id,)).fetchone()[0]
    blockers = []
    if count == 0: blockers.append("NO_COMMITTED_REQUIREMENTS")
    if invalid: blockers.append("UNRESOLVED_REQUIRED_FIELDS")
    if stale: blockers.append("STALE_REQUIRED_CANDIDATE_DEPENDENCY")
    if project["state"] != "ACTIVE": blockers.append("INVALID_PROJECT_STATE")
    return {"ready": not blockers, "committed_requirement_count": count, "pending_candidate_count": pending,
            "stale_candidate_count": stale, "blocking_items": blockers}


@app.get("/api/projects/{project_id}/requirement-baselines/readiness")
def get_readiness(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db: return baseline_readiness(db, project_id)


@app.post("/api/projects/{project_id}/requirement-baselines:freeze")
def freeze_baseline(project_id: str, idempotency_key: Optional[str] = Header(None), actor: Actor = Depends(current_actor)):
    require_project(actor, project_id, owner=True)
    if actor.actor_type != "HUMAN": raise HTTPException(403, "Only a human project owner can freeze Gate 1")
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, project_id, actor.id, "FREEZE_REQUIREMENT_BASELINE", key)
        if previous: return previous
        audit(db, project_id, actor.id, "HUMAN", "BASELINE_FREEZE_REQUESTED", "REQUIREMENT_BASELINE", None)
        readiness = baseline_readiness(db, project_id)
        if not readiness["ready"]: raise HTTPException(409, {"message": "Requirement baseline is blocked", **readiness})
        version = db.execute("SELECT COALESCE(MAX(version),0)+1 FROM requirement_baselines WHERE project_id=?", (project_id,)).fetchone()[0]
        baseline_id, stamp = uid("rbl"), now()
        db.execute("INSERT INTO requirement_baselines VALUES (?,?,?,?,?,?)", (baseline_id, project_id, version, "FROZEN", actor.id, stamp))
        rows = db.execute("SELECT r.id,r.requirement_code,rr.id revision_id FROM requirements r JOIN requirement_revisions rr ON rr.requirement_id=r.id AND rr.revision=r.current_revision WHERE r.project_id=? AND r.status='COMMITTED' ORDER BY r.requirement_code", (project_id,)).fetchall()
        for row in rows:
            db.execute("INSERT INTO requirement_baseline_members VALUES (?,?,?,?)", (baseline_id, row["id"], row["revision_id"], row["requirement_code"]))
        result = {"baseline_id": baseline_id, "version": version, "status": "FROZEN", "frozen_by": actor.id,
                  "frozen_at": stamp, "requirement_count": len(rows), "membership_reconciliation": "CONFIRMED"}
        audit(db, project_id, actor.id, "HUMAN", "BASELINE_FROZEN", "REQUIREMENT_BASELINE", baseline_id, detail=result)
        idem_put(db, project_id, actor.id, "FREEZE_REQUIREMENT_BASELINE", key, result)
    with connect() as db:
        baseline = db.execute("SELECT * FROM requirement_baselines WHERE id=? AND project_id=?", (baseline_id, project_id)).fetchone()
        members = db.execute("SELECT COUNT(*) FROM requirement_baseline_members WHERE baseline_id=?", (baseline_id,)).fetchone()[0]
    if not baseline or baseline["status"] != "FROZEN" or members != len(rows):
        raise HTTPException(503, "ACTION_SUCCEEDED_RESOLUTION_UNCONFIRMED")
    return result


@app.get("/api/projects/{project_id}/requirement-baselines")
def list_baselines(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db:
        baselines = db.execute("SELECT b.*,COUNT(m.requirement_id) requirement_count FROM requirement_baselines b LEFT JOIN requirement_baseline_members m ON m.baseline_id=b.id WHERE b.project_id=? GROUP BY b.id ORDER BY b.version DESC", (project_id,)).fetchall()
    return [dict(x) for x in baselines]


@app.get("/api/projects/{project_id}/requirement-baselines/{baseline_id}")
def get_baseline(project_id: str, baseline_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db:
        baseline = db.execute("SELECT * FROM requirement_baselines WHERE id=? AND project_id=?", (baseline_id, project_id)).fetchone()
        if not baseline: raise HTTPException(404, "Baseline not found")
        members = db.execute("SELECT m.*,rr.revision,rr.title,rr.statement FROM requirement_baseline_members m JOIN requirement_revisions rr ON rr.id=m.requirement_revision_id WHERE m.baseline_id=? ORDER BY m.requirement_code", (baseline_id,)).fetchall()
    return {**dict(baseline), "members": [dict(x) for x in members]}


@app.get("/api/projects/{project_id}/truth")
def project_truth(project_id: str, actor: Actor = Depends(current_actor)):
    project = require_project(actor, project_id)
    with connect() as db:
        context_count = db.execute("SELECT COUNT(*) FROM project_context_items WHERE project_id=? AND status='ACTIVE'", (project_id,)).fetchone()[0]
        latest_run = db.execute("SELECT * FROM ai_runs WHERE project_id=? ORDER BY started_at DESC LIMIT 1", (project_id,)).fetchone()
        counts = {row["status"]: row["n"] for row in db.execute("SELECT status,COUNT(*) n FROM requirement_candidates WHERE project_id=? GROUP BY status", (project_id,)).fetchall()}
        committed = db.execute("SELECT COUNT(*) FROM requirements WHERE project_id=? AND status='COMMITTED'", (project_id,)).fetchone()[0]
        latest_baseline = db.execute("SELECT b.*,COUNT(m.requirement_id) requirement_count FROM requirement_baselines b LEFT JOIN requirement_baseline_members m ON m.baseline_id=b.id WHERE b.project_id=? GROUP BY b.id ORDER BY b.version DESC LIMIT 1", (project_id,)).fetchone()
        readiness = baseline_readiness(db, project_id)
    stale = readiness["stale_candidate_count"]
    attention = []
    if latest_run and latest_run["status"] == "FAILED": attention.append({"type":"AI_FAILURE", "message": latest_run["failure_code"], "severity":"HIGH"})
    if stale: attention.append({"type":"STALE_AI", "message": f"{stale} AI candidate(s) are stale; regenerate before acceptance.", "severity":"HIGH"})
    if counts.get("NEEDS_REVIEW", 0): attention.append({"type":"CANDIDATE_REVIEW", "message": f"{counts['NEEDS_REVIEW']} candidate(s) need review.", "severity":"MEDIUM"})
    if readiness["ready"] and not latest_baseline: attention.append({"type":"GATE_1", "message":"Requirement baseline is ready for human freeze.", "severity":"HIGH"})
    elif readiness["blocking_items"]: attention.append({"type":"BASELINE_BLOCKED", "message":", ".join(readiness["blocking_items"]), "severity":"HIGH"})
    truth = {
        "project": {"id": project_id, "name": project["name"], "objective": project["objective"], "state": project["state"]},
        "context": {"status": "READY" if context_count else "NO_CONTEXT", "source_count": context_count, "revision": project["context_revision"]},
        "ai": {"latest_run_status": latest_run["status"] if latest_run else "NOT_RUN", "failure_code": latest_run["failure_code"] if latest_run else None,
               "candidate_count": sum(counts.values()), "needs_review": counts.get("NEEDS_REVIEW",0), "stale_candidate_count": stale},
        "requirements": {"committed_count": committed},
        "baseline": ({"status": latest_baseline["status"], "version": latest_baseline["version"], "id": latest_baseline["id"],
                      "requirement_count": latest_baseline["requirement_count"], "frozen_by": latest_baseline["frozen_by"], "frozen_at": latest_baseline["frozen_at"]}
                     if latest_baseline else {"status":"NONE", "version": None}),
        "requirement_readiness": "GATE_1_COMPLETE" if latest_baseline else ("READY_TO_FREEZE" if readiness["ready"] else "BLOCKED"),
        "blocking_items": readiness["blocking_items"], "attention": attention,
        "next_recommended_phase": "PHASE_2_DELIVERY_DESIGN_VERTICAL_SLICE" if latest_baseline else None,
    }
    from .phase2 import phase2_truth_projection
    phase2 = phase2_truth_projection(project_id)
    truth.update({key:value for key,value in phase2.items() if key not in {"phase2_attention", "next_recommended_phase"}})
    truth["attention"].extend(phase2["phase2_attention"])
    if phase2["next_recommended_phase"]:
        truth["next_recommended_phase"] = phase2["next_recommended_phase"]
    return truth


@app.get("/api/projects/{project_id}/audit")
def list_audit(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db:
        rows = db.execute("SELECT * FROM audit_events WHERE project_id=? ORDER BY created_at DESC LIMIT 200", (project_id,)).fetchall()
    return [unpack(x) for x in rows]


from .phase2 import router as phase2_router
app.include_router(phase2_router)
