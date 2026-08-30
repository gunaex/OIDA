from __future__ import annotations

import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, ValidationError

from .ai import (
    AIError,
    AIGroundingInsufficient,
    AIInvalidOutput,
    DeliveryItemOutput,
    DeliveryPlanOutput,
    DependencyOutput,
    RequirementBaselineInput,
    SolutionOptionOutput,
    adapter_for,
)
from .auth import Actor, current_actor, require_project
from .db import connect, now, transaction
from .telemetry import record_ai_telemetry

router = APIRouter(prefix="/api/projects/{project_id}", tags=["phase2"])


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def audit(db, project_id, actor_id, actor_type, action, target_type, target_id, result="SUCCESS", detail=None):
    db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?)", (
        uid("aud"), project_id, actor_id, actor_type, action, target_type, target_id,
        result, dumps(detail or {}), now()))


def require_key(value: Optional[str]) -> str:
    if not value or len(value) > 200:
        raise HTTPException(400, "A valid Idempotency-Key header is required")
    return value


def idem_get(db, project_id, actor_id, action, key):
    row = db.execute("SELECT response_json FROM idempotency_records WHERE project_scope=? AND actor_id=? AND action=? AND idempotency_key=?",
                     (project_id, actor_id, action, key)).fetchone()
    return json.loads(row[0]) if row else None


def idem_put(db, project_id, actor_id, action, key, response):
    db.execute("INSERT INTO idempotency_records VALUES (?,?,?,?,?,?)",
               (project_id, actor_id, action, key, dumps(response), now()))


class GenerateDesignIn(BaseModel):
    instruction: str = Field(default="", max_length=2000)


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class MergeIn(BaseModel):
    candidate_ids: list[str] = Field(min_length=2, max_length=3)
    title: str = Field(default="Merged solution", min_length=3, max_length=160)


class SolutionPatch(BaseModel):
    content: SolutionOptionOutput


class PlanPatch(BaseModel):
    content: DeliveryPlanOutput


class ManualItemIn(BaseModel):
    item: DeliveryItemOutput


class DependenciesIn(BaseModel):
    dependencies: list[DependencyOutput] = Field(max_length=80)


def latest_baseline(db, project_id):
    return db.execute("SELECT * FROM requirement_baselines WHERE project_id=? AND status='FROZEN' ORDER BY version DESC LIMIT 1",
                      (project_id,)).fetchone()


def baseline_input(db, project_id, baseline_id=None) -> RequirementBaselineInput:
    baseline = (db.execute("SELECT * FROM requirement_baselines WHERE id=? AND project_id=? AND status='FROZEN'",
                           (baseline_id, project_id)).fetchone() if baseline_id else latest_baseline(db, project_id))
    if not baseline:
        raise HTTPException(409, "Gate 1 must be frozen before solution generation")
    project = db.execute("SELECT name,objective FROM projects WHERE id=?", (project_id,)).fetchone()
    rows = db.execute(
        "SELECT m.requirement_code,m.requirement_revision_id,rr.title,rr.statement,rr.priority,rr.acceptance_criteria_json "
        "FROM requirement_baseline_members m JOIN requirement_revisions rr ON rr.id=m.requirement_revision_id "
        "WHERE m.baseline_id=? ORDER BY m.requirement_code", (baseline["id"],)).fetchall()
    requirements = [{**dict(row), "acceptance_criteria": json.loads(row["acceptance_criteria_json"])} for row in rows]
    for item in requirements:
        item.pop("acceptance_criteria_json")
    return RequirementBaselineInput(project["name"], project["objective"], baseline["id"], baseline["version"], requirements)


def validate_solution(content: SolutionOptionOutput, baseline: RequirementBaselineInput):
    expected = {x["requirement_revision_id"] for x in baseline.requirements}
    actual = [x.requirement_revision_id for x in content.requirement_coverage]
    if set(actual) != expected or len(actual) != len(set(actual)):
        raise HTTPException(422, "Solution coverage must reference every exact baseline requirement revision once")
    component_refs = {x.ref for x in content.components}
    if any(x.component_ref not in component_refs for x in content.requirement_coverage):
        raise HTTPException(422, "Solution coverage references an unknown component")


def validate_plan(content: DeliveryPlanOutput, baseline: RequirementBaselineInput, solution: dict):
    workstreams = {x.ref for x in content.workstreams}
    item_refs = [x.ref for x in content.items]
    if len(item_refs) != len(set(item_refs)):
        raise HTTPException(422, "Delivery item refs must be unique")
    if any(x.workstream_ref not in workstreams for x in content.items):
        raise HTTPException(422, "Delivery item references an unknown workstream")
    allowed_requirements = {x["requirement_revision_id"] for x in baseline.requirements}
    allowed_components = {x["ref"] for x in solution.get("components", [])}
    for item in content.items:
        if not set(item.requirement_revision_ids).issubset(allowed_requirements):
            raise HTTPException(422, "Delivery item references a requirement outside the baseline")
        if not set(item.solution_component_refs).issubset(allowed_components):
            raise HTTPException(422, "Delivery item references an unknown solution component")
    refs = set(item_refs)
    edges = []
    for dep in content.dependencies:
        if dep.predecessor_ref not in refs or dep.successor_ref not in refs:
            raise HTTPException(422, "Dependency references an unknown or cross-project item")
        if dep.predecessor_ref == dep.successor_ref:
            raise HTTPException(422, "Self-dependencies are not allowed")
        edges.append((dep.predecessor_ref, dep.successor_ref))
    if any(not set(x.item_refs).issubset(refs) for x in content.milestones):
        raise HTTPException(422, "Milestone references an unknown delivery item")
    graph = {ref: [] for ref in refs}
    for source, target in edges:
        graph[source].append(target)
    visiting, visited = set(), set()
    def visit(node):
        if node in visiting: return False
        if node in visited: return True
        visiting.add(node)
        if any(not visit(child) for child in graph[node]): return False
        visiting.remove(node); visited.add(node); return True
    if any(not visit(node) for node in refs):
        raise HTTPException(422, "Dependency graph contains a cycle")


def candidate_view(row):
    value = dict(row)
    value["content"] = json.loads(value.pop("content_json"))
    value["original_ai"] = json.loads(value.pop("original_ai_json"))
    value["human_modified"] = bool(value["human_modified"])
    value["recommended"] = bool(value["recommended"])
    return value


def materialize_solution_run(db, project_id, actor, body, supersedes=None):
    baseline = baseline_input(db, project_id)
    project = db.execute("SELECT context_revision FROM projects WHERE id=?", (project_id,)).fetchone()
    adapter, run_id, stamp = adapter_for(), uid("srun"), now()
    db.execute("INSERT INTO solution_ai_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        run_id, project_id, actor.id, adapter.provider, adapter.model, "solution-alternatives/v1", body.instruction,
        baseline.baseline_id, project["context_revision"], "RUNNING", None, "[]", stamp, None))
    audit(db, project_id, f"ai:{run_id}", "AI", "AI_SOLUTION_RUN_STARTED", "SOLUTION_AI_RUN", run_id,
          detail={"requirement_baseline_id": baseline.baseline_id})
    started = time.monotonic()
    try:
        output = adapter.generate_solutions(baseline, body.instruction)
        ids = []
        for option in output.alternatives:
            try:
                validate_solution(option, baseline)
            except HTTPException as exc:
                raise AIGroundingInsufficient("Solution output failed exact baseline coverage validation") from exc
            candidate_id, content = uid("scand"), option.model_dump()
            db.execute("INSERT INTO solution_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                candidate_id, project_id, run_id, baseline.baseline_id, "NEEDS_REVIEW", option.title, option.summary,
                dumps(content), dumps(content), 1, 0, int(option.recommended), "AI", supersedes, None,
                f"ai:{run_id}", stamp, stamp))
            db.execute("INSERT INTO solution_candidate_revisions VALUES (?,?,?,?,?,?,?,?)", (
                uid("screv"), candidate_id, project_id, 1, dumps(content), f"ai:{run_id}", "AI", stamp))
            ids.append(candidate_id)
        db.execute("UPDATE solution_ai_runs SET status='SUCCEEDED',findings_json=?,completed_at=? WHERE id=?",
                   (dumps(output.findings), now(), run_id))
        telemetry = record_ai_telemetry(db, project_id, "SOLUTION", run_id, adapter)
        audit(db, project_id, f"ai:{run_id}", "AI", "AI_SOLUTION_RUN_COMPLETED", "SOLUTION_AI_RUN", run_id,
              detail={"alternative_count": len(ids), "duration_ms": round((time.monotonic()-started)*1000, 2)})
        return {"ai_run_id": run_id, "status":"SUCCEEDED", "candidate_ids":ids, "findings":output.findings,
                "provider":adapter.provider, "model":adapter.model, "requirement_baseline_id":baseline.baseline_id,
                "telemetry":telemetry}
    except AIError as exc:
        db.execute("UPDATE solution_ai_runs SET status='FAILED',failure_code=?,completed_at=? WHERE id=?", (exc.code, now(), run_id))
        telemetry = record_ai_telemetry(db, project_id, "SOLUTION", run_id, adapter, exc.code)
        audit(db, project_id, f"ai:{run_id}", "AI", "AI_SOLUTION_RUN_FAILED", "SOLUTION_AI_RUN", run_id,
              "FAILED", {"failure_code":exc.code})
        return {"ai_run_id":run_id, "status":"FAILED", "failure_code":exc.code, "message":str(exc),
                "provider":adapter.provider, "requirement_baseline_id":baseline.baseline_id, "telemetry":telemetry}


@router.get("/solution-readiness")
def solution_readiness(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db:
        baseline = latest_baseline(db, project_id)
    return {"ready": bool(baseline), "gate_1_status":"FROZEN" if baseline else "MISSING",
            "requirement_baseline_id":baseline["id"] if baseline else None,
            "blocking_items":[] if baseline else ["GATE_1_NOT_FROZEN"]}


def generate_solutions_sync(project_id: str, body: GenerateDesignIn, idempotency_key: Optional[str], actor: Actor):
    require_project(actor, project_id)
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, project_id, actor.id, "GENERATE_SOLUTIONS", key)
        if previous: return previous
        result = materialize_solution_run(db, project_id, actor, body)
        idem_put(db, project_id, actor.id, "GENERATE_SOLUTIONS", key, result)
    return result


@router.post("/ai/solutions:generate", status_code=202)
def generate_solutions(project_id: str, body: GenerateDesignIn, idempotency_key: Optional[str] = Header(None), actor: Actor = Depends(current_actor)):
    from .jobs import enqueue
    require_project(actor, project_id); key=require_key(idempotency_key)
    with connect() as db: baseline_input(db, project_id)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"QUEUE_SOLUTIONS",key)
        if previous:return previous
        result=enqueue(db,project_id,actor,"SOLUTIONS",body.model_dump());idem_put(db,project_id,actor.id,"QUEUE_SOLUTIONS",key,result)
    return result


@router.get("/solution-candidates")
def list_solution_candidates(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db:
        latest = latest_baseline(db, project_id)
        rows = db.execute("SELECT * FROM solution_candidates WHERE project_id=? ORDER BY created_at", (project_id,)).fetchall()
    result = []
    for row in rows:
        item = candidate_view(row)
        item["stale"] = not latest or item["requirement_baseline_id"] != latest["id"]
        result.append(item)
    return result


@router.patch("/solution-candidates/{candidate_id}")
def edit_solution_candidate(project_id: str, candidate_id: str, body: SolutionPatch,
                            actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with transaction() as db:
        row = db.execute("SELECT * FROM solution_candidates WHERE id=? AND project_id=?", (candidate_id, project_id)).fetchone()
        if not row: raise HTTPException(404, "Solution candidate not found")
        if row["status"] not in {"NEEDS_REVIEW","SELECTED"}: raise HTTPException(409, "Candidate cannot be edited in its current state")
        baseline = baseline_input(db, project_id, row["requirement_baseline_id"])
        validate_solution(body.content, baseline)
        revision, stamp = row["current_revision"] + 1, now()
        content = body.content.model_dump()
        db.execute("UPDATE solution_candidates SET title=?,summary=?,content_json=?,current_revision=?,human_modified=1,updated_at=? WHERE id=? AND project_id=?",
                   (body.content.title, body.content.summary, dumps(content), revision, stamp, candidate_id, project_id))
        db.execute("INSERT INTO solution_candidate_revisions VALUES (?,?,?,?,?,?,?,?)", (
            uid("screv"), candidate_id, project_id, revision, dumps(content), actor.id, "HUMAN", stamp))
        audit(db, project_id, actor.id, "HUMAN", "SOLUTION_CANDIDATE_EDITED", "SOLUTION_CANDIDATE", candidate_id,
              detail={"revision":revision})
    return {"id":candidate_id, "current_revision":revision, "human_modified":True}


@router.post("/solution-candidates/{candidate_id}:select")
def select_solution_candidate(project_id: str, candidate_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with transaction() as db:
        row = db.execute("SELECT * FROM solution_candidates WHERE id=? AND project_id=?", (candidate_id, project_id)).fetchone()
        latest = latest_baseline(db, project_id)
        if not row: raise HTTPException(404, "Solution candidate not found")
        if row["status"] not in {"NEEDS_REVIEW","SELECTED"}: raise HTTPException(409, "Candidate is not selectable")
        if not latest or row["requirement_baseline_id"] != latest["id"]: raise HTTPException(409, "Candidate is stale")
        db.execute("UPDATE solution_candidates SET status='NEEDS_REVIEW',updated_at=? WHERE project_id=? AND status='SELECTED'", (now(), project_id))
        db.execute("UPDATE solution_candidates SET status='SELECTED',updated_at=? WHERE id=? AND project_id=?", (now(), candidate_id, project_id))
        audit(db, project_id, actor.id, "HUMAN", "SOLUTION_CANDIDATE_SELECTED", "SOLUTION_CANDIDATE", candidate_id)
    return {"id":candidate_id, "status":"SELECTED"}


@router.post("/solution-candidates/{candidate_id}:reject")
def reject_solution_candidate(project_id: str, candidate_id: str, body: RejectIn, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with transaction() as db:
        row = db.execute("SELECT status FROM solution_candidates WHERE id=? AND project_id=?", (candidate_id, project_id)).fetchone()
        if not row: raise HTTPException(404, "Solution candidate not found")
        if row["status"] == "COMMITTED": raise HTTPException(409, "Committed solution cannot be rejected")
        db.execute("UPDATE solution_candidates SET status='REJECTED',rejection_reason=?,updated_at=? WHERE id=? AND project_id=?",
                   (body.reason, now(), candidate_id, project_id))
        audit(db, project_id, actor.id, "HUMAN", "SOLUTION_CANDIDATE_REJECTED", "SOLUTION_CANDIDATE", candidate_id,
              detail={"reason":body.reason})
    return {"id":candidate_id, "status":"REJECTED"}


def regenerate_solution_candidate_sync(project_id: str, candidate_id: str, body: GenerateDesignIn,
                                       idempotency_key: Optional[str], actor: Actor):
    require_project(actor, project_id)
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, project_id, actor.id, "REGENERATE_SOLUTION", key)
        if previous: return previous
        row = db.execute("SELECT status FROM solution_candidates WHERE id=? AND project_id=?", (candidate_id, project_id)).fetchone()
        if not row: raise HTTPException(404, "Solution candidate not found")
        result = materialize_solution_run(db, project_id, actor, body, candidate_id)
        if result["status"] == "SUCCEEDED" and row["status"] != "COMMITTED":
            db.execute("UPDATE solution_candidates SET status='SUPERSEDED',updated_at=? WHERE id=? AND project_id=?", (now(), candidate_id, project_id))
        idem_put(db, project_id, actor.id, "REGENERATE_SOLUTION", key, result)
    return result


@router.post("/solution-candidates/{candidate_id}:regenerate",status_code=202)
def regenerate_solution_candidate(project_id:str,candidate_id:str,body:GenerateDesignIn,idempotency_key:Optional[str]=Header(None),actor:Actor=Depends(current_actor)):
    from .jobs import enqueue
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        row=db.execute("SELECT id FROM solution_candidates WHERE id=? AND project_id=?",(candidate_id,project_id)).fetchone()
        if not row:raise HTTPException(404,"Solution candidate not found")
        previous=idem_get(db,project_id,actor.id,"QUEUE_REGENERATE_SOLUTION",key)
        if previous:return previous
        result=enqueue(db,project_id,actor,"SOLUTIONS_REGENERATE",{**body.model_dump(),"candidate_id":candidate_id});idem_put(db,project_id,actor.id,"QUEUE_REGENERATE_SOLUTION",key,result)
    return result


@router.post("/solution-candidates:merge", status_code=201)
def merge_solution_candidates(project_id: str, body: MergeIn, idempotency_key: Optional[str] = Header(None),
                              actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, project_id, actor.id, "MERGE_SOLUTIONS", key)
        if previous: return previous
        marks = ",".join("?" for _ in body.candidate_ids)
        rows = db.execute(f"SELECT * FROM solution_candidates WHERE project_id=? AND id IN ({marks})",
                          (project_id, *body.candidate_ids)).fetchall()
        if len(rows) != len(set(body.candidate_ids)): raise HTTPException(404, "One or more solution candidates were not found")
        baseline_ids = {x["requirement_baseline_id"] for x in rows}
        if len(baseline_ids) != 1: raise HTTPException(409, "Only candidates from the same baseline can be merged")
        contents = [json.loads(x["content_json"]) for x in rows]
        merged = dict(contents[0]); merged["title"] = body.title; merged["recommended"] = False
        merged["summary"] = "Human-composed merge of selected alternatives. " + merged["summary"]
        for field in ["design_principles","integrations","data_flows","security_considerations","deployment_considerations","assumptions","constraints","risks","open_decisions","pros","cons"]:
            unique = []
            for content in contents:
                for value in content[field]:
                    marker = dumps(value)
                    if marker not in {dumps(x) for x in unique}: unique.append(value)
            merged[field] = unique[:20]
        used = set(); components = []
        for content in contents:
            for component in content["components"]:
                if component["ref"] not in used: used.add(component["ref"]); components.append(component)
        merged["components"] = components
        try: model = SolutionOptionOutput.model_validate(merged)
        except ValidationError as exc: raise HTTPException(422, "Merged candidate is not structurally valid") from exc
        baseline = baseline_input(db, project_id, next(iter(baseline_ids))); validate_solution(model, baseline)
        candidate_id, stamp = uid("scand"), now()
        db.execute("INSERT INTO solution_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            candidate_id, project_id, None, baseline.baseline_id, "NEEDS_REVIEW", model.title, model.summary,
            dumps(model.model_dump()), dumps(model.model_dump()), 1, 1, 0, "HUMAN_MERGE", None, None,
            actor.id, stamp, stamp))
        db.execute("INSERT INTO solution_candidate_revisions VALUES (?,?,?,?,?,?,?,?)", (
            uid("screv"), candidate_id, project_id, 1, dumps(model.model_dump()), actor.id, "HUMAN", stamp))
        result = {"id":candidate_id, "status":"NEEDS_REVIEW", "origin":"HUMAN_MERGE", "source_candidate_ids":body.candidate_ids}
        audit(db, project_id, actor.id, "HUMAN", "SOLUTION_CANDIDATES_MERGED", "SOLUTION_CANDIDATE", candidate_id,
              detail={"source_candidate_ids":body.candidate_ids})
        idem_put(db, project_id, actor.id, "MERGE_SOLUTIONS", key, result)
    return result


def next_code(db, project_id, column, prefix):
    value = db.execute(f"SELECT {column} FROM projects WHERE id=?", (project_id,)).fetchone()[0]
    db.execute(f"UPDATE projects SET {column}={column}+1,updated_at=? WHERE id=?", (now(), project_id))
    return f"{prefix}-{value:03d}"


@router.post("/solution-candidates/{candidate_id}:commit")
def commit_solution(project_id: str, candidate_id: str, idempotency_key: Optional[str] = Header(None),
                    actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    key = require_key(idempotency_key)
    with transaction() as db:
        previous = idem_get(db, project_id, actor.id, "COMMIT_SOLUTION", key)
        if previous: return previous
        row = db.execute("SELECT * FROM solution_candidates WHERE id=? AND project_id=?", (candidate_id, project_id)).fetchone()
        if not row: raise HTTPException(404, "Solution candidate not found")
        existing = db.execute("SELECT s.*,sr.id revision_id FROM solutions s JOIN solution_revisions sr ON sr.solution_id=s.id AND sr.revision=s.current_revision WHERE s.source_candidate_id=? AND s.project_id=?", (candidate_id, project_id)).fetchone()
        if existing:
            result = {"solution_id":existing["id"], "solution_code":existing["solution_code"], "revision_id":existing["revision_id"], "reconciliation":"CONFIRMED"}
            idem_put(db, project_id, actor.id, "COMMIT_SOLUTION", key, result); return result
        latest = latest_baseline(db, project_id)
        if row["status"] != "SELECTED": raise HTTPException(409, "Select the solution candidate before commit")
        if not latest or row["requirement_baseline_id"] != latest["id"]: raise HTTPException(409, "Selected solution candidate is stale")
        content = SolutionOptionOutput.model_validate_json(row["content_json"])
        baseline = baseline_input(db, project_id, latest["id"]); validate_solution(content, baseline)
        solution_id, revision_id, stamp = uid("sol"), uid("solrev"), now()
        code = next_code(db, project_id, "next_solution_number", "SOL")
        db.execute("INSERT INTO solutions VALUES (?,?,?,?,?,?,?,?,?)", (
            solution_id, project_id, code, candidate_id, "COMMITTED", 1, actor.id, stamp, stamp))
        db.execute("INSERT INTO solution_revisions VALUES (?,?,?,?,?,?,?,?,?,?)", (
            revision_id, solution_id, project_id, 1, latest["id"], content.title, content.summary,
            dumps(content.model_dump()), actor.id, stamp))
        for coverage in content.requirement_coverage:
            db.execute("INSERT INTO solution_revision_coverage VALUES (?,?,?,?,?)", (
                revision_id, coverage.requirement_revision_id, coverage.status, coverage.component_ref, coverage.explanation))
        db.execute("UPDATE solution_candidates SET status='COMMITTED',updated_at=? WHERE id=?", (stamp, candidate_id))
        result = {"solution_id":solution_id, "solution_code":code, "revision_id":revision_id, "revision":1,
                  "requirement_baseline_id":latest["id"], "reconciliation":"CONFIRMED"}
        audit(db, project_id, actor.id, "HUMAN", "SOLUTION_COMMITTED", "SOLUTION", solution_id, detail=result)
        idem_put(db, project_id, actor.id, "COMMIT_SOLUTION", key, result)
    with connect() as db:
        confirmed = db.execute("SELECT id FROM solution_revisions WHERE id=? AND project_id=?", (revision_id, project_id)).fetchone()
    if not confirmed: raise HTTPException(503, "ACTION_SUCCEEDED_RESOLUTION_UNCONFIRMED")
    return result


@router.get("/solutions")
def list_solutions(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with connect() as db:
        latest = latest_baseline(db, project_id)
        rows = db.execute("SELECT s.*,sr.id revision_id,sr.requirement_baseline_id,sr.title,sr.summary,sr.content_json FROM solutions s JOIN solution_revisions sr ON sr.solution_id=s.id AND sr.revision=s.current_revision WHERE s.project_id=? ORDER BY s.created_at", (project_id,)).fetchall()
    result=[]
    for row in rows:
        item=dict(row); item["content"]=json.loads(item.pop("content_json")); item["stale"]=not latest or item["requirement_baseline_id"] != latest["id"]; result.append(item)
    return result


@router.patch("/solutions/{solution_id}")
def revise_solution(project_id: str, solution_id: str, body: SolutionPatch, actor: Actor = Depends(current_actor)):
    require_project(actor, project_id)
    with transaction() as db:
        solution=db.execute("SELECT * FROM solutions WHERE id=? AND project_id=?", (solution_id,project_id)).fetchone()
        if not solution: raise HTTPException(404,"Solution not found")
        old=db.execute("SELECT * FROM solution_revisions WHERE solution_id=? AND revision=?",(solution_id,solution["current_revision"])).fetchone()
        baseline=baseline_input(db,project_id,old["requirement_baseline_id"]); validate_solution(body.content,baseline)
        revision,revision_id,stamp=solution["current_revision"]+1,uid("solrev"),now()
        db.execute("INSERT INTO solution_revisions VALUES (?,?,?,?,?,?,?,?,?,?)",(revision_id,solution_id,project_id,revision,old["requirement_baseline_id"],body.content.title,body.content.summary,dumps(body.content.model_dump()),actor.id,stamp))
        for coverage in body.content.requirement_coverage:
            db.execute("INSERT INTO solution_revision_coverage VALUES (?,?,?,?,?)",(revision_id,coverage.requirement_revision_id,coverage.status,coverage.component_ref,coverage.explanation))
        db.execute("UPDATE solutions SET current_revision=?,updated_at=? WHERE id=? AND project_id=?",(revision,stamp,solution_id,project_id))
        audit(db,project_id,actor.id,"HUMAN","SOLUTION_REVISED","SOLUTION",solution_id,detail={"revision":revision})
    return {"solution_id":solution_id,"revision_id":revision_id,"revision":revision}


def current_solution(db, project_id):
    return db.execute("SELECT s.*,sr.id revision_id,sr.requirement_baseline_id,sr.content_json FROM solutions s JOIN solution_revisions sr ON sr.solution_id=s.id AND sr.revision=s.current_revision WHERE s.project_id=? ORDER BY s.updated_at DESC LIMIT 1", (project_id,)).fetchone()


def materialize_plan_run(db, project_id, actor, body, supersedes=None):
    solution=current_solution(db,project_id)
    if not solution: raise HTTPException(409,"A committed solution is required before delivery-plan generation")
    latest=latest_baseline(db,project_id)
    if not latest or solution["requirement_baseline_id"] != latest["id"]: raise HTTPException(409,"Committed solution is stale against the latest requirement baseline")
    baseline=baseline_input(db,project_id,latest["id"]); solution_content=json.loads(solution["content_json"])
    adapter,run_id,stamp=adapter_for(),uid("prun"),now()
    db.execute("INSERT INTO delivery_plan_ai_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(run_id,project_id,actor.id,adapter.provider,adapter.model,"delivery-plan/v1",body.instruction,latest["id"],solution["revision_id"],"RUNNING",None,"[]",stamp,None))
    audit(db,project_id,f"ai:{run_id}","AI","AI_DELIVERY_PLAN_RUN_STARTED","DELIVERY_PLAN_AI_RUN",run_id,detail={"solution_revision_id":solution["revision_id"]})
    try:
        output=adapter.generate_delivery_plan(baseline,solution_content,body.instruction)
        try:
            validate_plan(output,baseline,solution_content)
        except HTTPException as exc:
            raise AIInvalidOutput("Delivery plan output failed reference or dependency validation") from exc
        candidate_id=uid("pcand"); content=output.model_dump()
        db.execute("INSERT INTO delivery_plan_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(candidate_id,project_id,run_id,latest["id"],solution["revision_id"],"NEEDS_REVIEW",output.title,dumps(content),dumps(content),1,0,"AI",supersedes,None,f"ai:{run_id}",stamp,stamp))
        db.execute("INSERT INTO delivery_plan_candidate_revisions VALUES (?,?,?,?,?,?,?,?)",(uid("pcrev"),candidate_id,project_id,1,dumps(content),f"ai:{run_id}","AI",stamp))
        db.execute("UPDATE delivery_plan_ai_runs SET status='SUCCEEDED',findings_json=?,completed_at=? WHERE id=?",(dumps(output.findings),now(),run_id))
        telemetry=record_ai_telemetry(db,project_id,"DELIVERY_PLAN",run_id,adapter)
        audit(db,project_id,f"ai:{run_id}","AI","AI_DELIVERY_PLAN_RUN_COMPLETED","DELIVERY_PLAN_AI_RUN",run_id,detail={"item_count":len(output.items)})
        return {"ai_run_id":run_id,"status":"SUCCEEDED","candidate_id":candidate_id,"provider":adapter.provider,"model":adapter.model,"requirement_baseline_id":latest["id"],"solution_revision_id":solution["revision_id"],"telemetry":telemetry}
    except AIError as exc:
        db.execute("UPDATE delivery_plan_ai_runs SET status='FAILED',failure_code=?,completed_at=? WHERE id=?",(exc.code,now(),run_id))
        telemetry=record_ai_telemetry(db,project_id,"DELIVERY_PLAN",run_id,adapter,exc.code)
        audit(db,project_id,f"ai:{run_id}","AI","AI_DELIVERY_PLAN_RUN_FAILED","DELIVERY_PLAN_AI_RUN",run_id,"FAILED",{"failure_code":exc.code})
        return {"ai_run_id":run_id,"status":"FAILED","failure_code":exc.code,"message":str(exc),"provider":adapter.provider,"telemetry":telemetry}


def generate_plan_sync(project_id: str, body: GenerateDesignIn, idempotency_key: Optional[str], actor: Actor):
    require_project(actor,project_id); key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"GENERATE_DELIVERY_PLAN",key)
        if previous:return previous
        result=materialize_plan_run(db,project_id,actor,body); idem_put(db,project_id,actor.id,"GENERATE_DELIVERY_PLAN",key,result)
    return result


@router.post("/ai/delivery-plans:generate", status_code=202)
def generate_plan(project_id: str, body: GenerateDesignIn, idempotency_key: Optional[str]=Header(None), actor: Actor=Depends(current_actor)):
    from .jobs import enqueue
    require_project(actor,project_id);key=require_key(idempotency_key)
    with connect() as db:
        solution=current_solution(db,project_id);latest=latest_baseline(db,project_id)
        if not solution:raise HTTPException(409,"A committed solution is required before delivery-plan generation")
        if not latest or solution["requirement_baseline_id"]!=latest["id"]:raise HTTPException(409,"Committed solution is stale against the latest requirement baseline")
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"QUEUE_DELIVERY_PLAN",key)
        if previous:return previous
        result=enqueue(db,project_id,actor,"DELIVERY_PLAN",body.model_dump());idem_put(db,project_id,actor.id,"QUEUE_DELIVERY_PLAN",key,result)
    return result


def plan_candidate_view(row, latest_baseline_id, current_solution_revision_id):
    value=dict(row); value["content"]=json.loads(value.pop("content_json")); value["original_ai"]=json.loads(value.pop("original_ai_json")); value["human_modified"]=bool(value["human_modified"])
    value["stale"] = value["requirement_baseline_id"] != latest_baseline_id or value["solution_revision_id"] != current_solution_revision_id
    return value


@router.get("/delivery-plan-candidates")
def list_plan_candidates(project_id: str, actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:
        latest=latest_baseline(db,project_id); solution=current_solution(db,project_id)
        rows=db.execute("SELECT * FROM delivery_plan_candidates WHERE project_id=? ORDER BY created_at",(project_id,)).fetchall()
    return [plan_candidate_view(x,latest["id"] if latest else None,solution["revision_id"] if solution else None) for x in rows]


def update_plan_candidate(db, project_id, candidate_id, content: DeliveryPlanOutput, actor, action="DELIVERY_PLAN_CANDIDATE_EDITED"):
    row=db.execute("SELECT * FROM delivery_plan_candidates WHERE id=? AND project_id=?",(candidate_id,project_id)).fetchone()
    if not row: raise HTTPException(404,"Delivery plan candidate not found")
    if row["status"]!="NEEDS_REVIEW": raise HTTPException(409,"Plan candidate cannot be edited in its current state")
    baseline=baseline_input(db,project_id,row["requirement_baseline_id"])
    solution=db.execute("SELECT content_json FROM solution_revisions WHERE id=? AND project_id=?",(row["solution_revision_id"],project_id)).fetchone()
    if not solution: raise HTTPException(409,"Source solution revision is unavailable")
    validate_plan(content,baseline,json.loads(solution["content_json"]))
    revision,stamp=row["current_revision"]+1,now()
    db.execute("UPDATE delivery_plan_candidates SET title=?,content_json=?,current_revision=?,human_modified=1,updated_at=? WHERE id=? AND project_id=?",(content.title,dumps(content.model_dump()),revision,stamp,candidate_id,project_id))
    db.execute("INSERT INTO delivery_plan_candidate_revisions VALUES (?,?,?,?,?,?,?,?)",(uid("pcrev"),candidate_id,project_id,revision,dumps(content.model_dump()),actor.id,"HUMAN",stamp))
    audit(db,project_id,actor.id,"HUMAN",action,"DELIVERY_PLAN_CANDIDATE",candidate_id,detail={"revision":revision})
    return revision


@router.patch("/delivery-plan-candidates/{candidate_id}")
def edit_plan_candidate(project_id: str,candidate_id: str,body: PlanPatch,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db: revision=update_plan_candidate(db,project_id,candidate_id,body.content,actor)
    return {"id":candidate_id,"current_revision":revision,"human_modified":True}


@router.post("/delivery-plan-candidates/{candidate_id}/items")
def add_plan_item(project_id: str,candidate_id: str,body: ManualItemIn,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        row=db.execute("SELECT content_json FROM delivery_plan_candidates WHERE id=? AND project_id=?",(candidate_id,project_id)).fetchone()
        if not row: raise HTTPException(404,"Delivery plan candidate not found")
        raw=json.loads(row["content_json"])
        if body.item.ref in {x["ref"] for x in raw["items"]}: raise HTTPException(409,"Delivery item ref already exists")
        raw["items"].append(body.item.model_dump()); content=DeliveryPlanOutput.model_validate(raw)
        revision=update_plan_candidate(db,project_id,candidate_id,content,actor,"DELIVERY_ITEM_ADDED")
    return {"id":candidate_id,"item_ref":body.item.ref,"current_revision":revision}


@router.delete("/delivery-plan-candidates/{candidate_id}/items/{item_ref}")
def remove_plan_item(project_id: str,candidate_id: str,item_ref: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        row=db.execute("SELECT content_json FROM delivery_plan_candidates WHERE id=? AND project_id=?",(candidate_id,project_id)).fetchone()
        if not row: raise HTTPException(404,"Delivery plan candidate not found")
        raw=json.loads(row["content_json"]); before=len(raw["items"]); raw["items"]=[x for x in raw["items"] if x["ref"]!=item_ref]
        if len(raw["items"])==before: raise HTTPException(404,"Delivery item not found")
        raw["dependencies"]=[x for x in raw["dependencies"] if item_ref not in {x["predecessor_ref"],x["successor_ref"]}]
        for milestone in raw["milestones"]: milestone["item_refs"]=[x for x in milestone["item_refs"] if x!=item_ref]
        try: content=DeliveryPlanOutput.model_validate(raw)
        except ValidationError as exc: raise HTTPException(409,"Removal would make the plan invalid; edit milestone membership first") from exc
        revision=update_plan_candidate(db,project_id,candidate_id,content,actor,"DELIVERY_ITEM_REMOVED")
    return {"id":candidate_id,"removed_item_ref":item_ref,"current_revision":revision}


@router.put("/delivery-plan-candidates/{candidate_id}/dependencies")
def replace_dependencies(project_id: str,candidate_id: str,body: DependenciesIn,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        row=db.execute("SELECT content_json FROM delivery_plan_candidates WHERE id=? AND project_id=?",(candidate_id,project_id)).fetchone()
        if not row: raise HTTPException(404,"Delivery plan candidate not found")
        raw=json.loads(row["content_json"]); raw["dependencies"]=[x.model_dump() for x in body.dependencies]
        content=DeliveryPlanOutput.model_validate(raw); revision=update_plan_candidate(db,project_id,candidate_id,content,actor,"DELIVERY_DEPENDENCIES_CHANGED")
    return {"id":candidate_id,"current_revision":revision,"dependency_count":len(body.dependencies)}


def regenerate_plan_sync(project_id: str,candidate_id: str,body: GenerateDesignIn,idempotency_key: Optional[str],actor: Actor):
    require_project(actor,project_id); key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"REGENERATE_DELIVERY_PLAN",key)
        if previous:return previous
        row=db.execute("SELECT status FROM delivery_plan_candidates WHERE id=? AND project_id=?",(candidate_id,project_id)).fetchone()
        if not row: raise HTTPException(404,"Delivery plan candidate not found")
        result=materialize_plan_run(db,project_id,actor,body,candidate_id)
        if result["status"]=="SUCCEEDED" and row["status"]!="COMMITTED": db.execute("UPDATE delivery_plan_candidates SET status='SUPERSEDED',updated_at=? WHERE id=?",(now(),candidate_id))
        idem_put(db,project_id,actor.id,"REGENERATE_DELIVERY_PLAN",key,result)
    return result


@router.post("/delivery-plan-candidates/{candidate_id}:regenerate",status_code=202)
def regenerate_plan(project_id:str,candidate_id:str,body:GenerateDesignIn,idempotency_key:Optional[str]=Header(None),actor:Actor=Depends(current_actor)):
    from .jobs import enqueue
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        row=db.execute("SELECT id FROM delivery_plan_candidates WHERE id=? AND project_id=?",(candidate_id,project_id)).fetchone()
        if not row:raise HTTPException(404,"Delivery plan candidate not found")
        previous=idem_get(db,project_id,actor.id,"QUEUE_REGENERATE_DELIVERY_PLAN",key)
        if previous:return previous
        result=enqueue(db,project_id,actor,"DELIVERY_PLAN_REGENERATE",{**body.model_dump(),"candidate_id":candidate_id});idem_put(db,project_id,actor.id,"QUEUE_REGENERATE_DELIVERY_PLAN",key,result)
    return result


@router.post("/delivery-plan-candidates/{candidate_id}:reject")
def reject_plan(project_id: str,candidate_id: str,body: RejectIn,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        row=db.execute("SELECT status FROM delivery_plan_candidates WHERE id=? AND project_id=?",(candidate_id,project_id)).fetchone()
        if not row: raise HTTPException(404,"Delivery plan candidate not found")
        if row["status"]=="COMMITTED": raise HTTPException(409,"Committed plan cannot be rejected")
        db.execute("UPDATE delivery_plan_candidates SET status='REJECTED',rejection_reason=?,updated_at=? WHERE id=?",(body.reason,now(),candidate_id))
        audit(db,project_id,actor.id,"HUMAN","DELIVERY_PLAN_CANDIDATE_REJECTED","DELIVERY_PLAN_CANDIDATE",candidate_id,detail={"reason":body.reason})
    return {"id":candidate_id,"status":"REJECTED"}


def materialize_plan_revision(db, revision_id, plan_id, project_id, revision, candidate, content, actor_id, stamp):
    db.execute("INSERT INTO delivery_plan_revisions VALUES (?,?,?,?,?,?,?,?,?,?)",(revision_id,plan_id,project_id,revision,candidate["requirement_baseline_id"],candidate["solution_revision_id"],content.title,dumps(content.model_dump()),actor_id,stamp))
    for item in content.items:
        db.execute("INSERT INTO delivery_plan_revision_items VALUES (?,?,?,?,?,?,?,?,?,?,?)",(uid("ditem"),revision_id,item.ref,item.workstream_ref,item.title,item.description,item.owner_role,dumps(item.acceptance_criteria),item.effort,dumps(item.requirement_revision_ids),dumps(item.solution_component_refs)))
    for dep in content.dependencies:
        db.execute("INSERT INTO delivery_plan_revision_dependencies VALUES (?,?,?,?,?)",(uid("ddep"),revision_id,dep.predecessor_ref,dep.successor_ref,dep.dependency_type))
    for milestone in content.milestones:
        db.execute("INSERT INTO delivery_plan_revision_milestones VALUES (?,?,?,?,?,?)",(uid("dms"),revision_id,milestone.ref,milestone.title,dumps(milestone.exit_criteria),dumps(milestone.item_refs)))


@router.post("/delivery-plan-candidates/{candidate_id}:commit")
def commit_plan(project_id: str,candidate_id: str,idempotency_key: Optional[str]=Header(None),actor: Actor=Depends(current_actor)):
    require_project(actor,project_id); key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"COMMIT_DELIVERY_PLAN",key)
        if previous:return previous
        candidate=db.execute("SELECT * FROM delivery_plan_candidates WHERE id=? AND project_id=?",(candidate_id,project_id)).fetchone()
        if not candidate: raise HTTPException(404,"Delivery plan candidate not found")
        existing=db.execute("SELECT p.*,pr.id revision_id FROM delivery_plans p JOIN delivery_plan_revisions pr ON pr.plan_id=p.id AND pr.revision=p.current_revision WHERE p.source_candidate_id=? AND p.project_id=?",(candidate_id,project_id)).fetchone()
        if existing:
            result={"plan_id":existing["id"],"plan_code":existing["plan_code"],"revision_id":existing["revision_id"],"reconciliation":"CONFIRMED"}; idem_put(db,project_id,actor.id,"COMMIT_DELIVERY_PLAN",key,result); return result
        if candidate["status"]!="NEEDS_REVIEW": raise HTTPException(409,"Plan candidate is not available for commit")
        latest=latest_baseline(db,project_id); solution=current_solution(db,project_id)
        if not latest or not solution or candidate["requirement_baseline_id"]!=latest["id"] or candidate["solution_revision_id"]!=solution["revision_id"]: raise HTTPException(409,"Plan candidate is stale")
        content=DeliveryPlanOutput.model_validate_json(candidate["content_json"]); baseline=baseline_input(db,project_id,latest["id"]); validate_plan(content,baseline,json.loads(solution["content_json"]))
        plan_id,revision_id,stamp=uid("plan"),uid("planrev"),now(); code=next_code(db,project_id,"next_plan_number","PLAN")
        db.execute("INSERT INTO delivery_plans VALUES (?,?,?,?,?,?,?,?,?)",(plan_id,project_id,code,candidate_id,"COMMITTED",1,actor.id,stamp,stamp))
        materialize_plan_revision(db,revision_id,plan_id,project_id,1,candidate,content,actor.id,stamp)
        db.execute("UPDATE delivery_plan_candidates SET status='COMMITTED',updated_at=? WHERE id=?",(stamp,candidate_id))
        result={"plan_id":plan_id,"plan_code":code,"revision_id":revision_id,"revision":1,"requirement_baseline_id":latest["id"],"solution_revision_id":solution["revision_id"],"item_count":len(content.items),"reconciliation":"CONFIRMED"}
        audit(db,project_id,actor.id,"HUMAN","DELIVERY_PLAN_COMMITTED","DELIVERY_PLAN",plan_id,detail=result); idem_put(db,project_id,actor.id,"COMMIT_DELIVERY_PLAN",key,result)
    with connect() as db: confirmed=db.execute("SELECT COUNT(*) FROM delivery_plan_revision_items WHERE plan_revision_id=?",(revision_id,)).fetchone()[0]
    if confirmed!=len(content.items): raise HTTPException(503,"ACTION_SUCCEEDED_RESOLUTION_UNCONFIRMED")
    return result


@router.get("/delivery-plans")
def list_plans(project_id: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:
        latest=latest_baseline(db,project_id); solution=current_solution(db,project_id)
        rows=db.execute("SELECT p.*,pr.id revision_id,pr.requirement_baseline_id,pr.solution_revision_id,pr.title,pr.content_json FROM delivery_plans p JOIN delivery_plan_revisions pr ON pr.plan_id=p.id AND pr.revision=p.current_revision WHERE p.project_id=? ORDER BY p.created_at",(project_id,)).fetchall()
    result=[]
    for row in rows:
        item=dict(row);item["content"]=json.loads(item.pop("content_json"));item["stale"]=not latest or not solution or item["requirement_baseline_id"]!=latest["id"] or item["solution_revision_id"]!=solution["revision_id"];result.append(item)
    return result


@router.get("/design-ai-runs")
def list_design_ai_runs(project_id: str, actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:
        solutions=db.execute("SELECT id,'SOLUTION' run_type,provider,model,prompt_version,requirement_baseline_id,NULL solution_revision_id,status,failure_code,findings_json,started_at,completed_at FROM solution_ai_runs WHERE project_id=?",(project_id,)).fetchall()
        plans=db.execute("SELECT id,'DELIVERY_PLAN' run_type,provider,model,prompt_version,requirement_baseline_id,solution_revision_id,status,failure_code,findings_json,started_at,completed_at FROM delivery_plan_ai_runs WHERE project_id=?",(project_id,)).fetchall()
        telemetry={row["run_id"]:dict(row) for row in db.execute(
            "SELECT run_id,reasoning_effort,input_tokens,cache_hit_tokens,output_tokens,total_tokens,latency_ms,provider_request_id,error_class "
            "FROM ai_run_telemetry WHERE project_id=? AND run_kind IN ('SOLUTION','DELIVERY_PLAN')",(project_id,)).fetchall()}
    rows=[]
    for row in [*solutions,*plans]:
        item=dict(row);item["findings"]=json.loads(item.pop("findings_json"));item["telemetry"]=telemetry.get(item["id"]);rows.append(item)
    return sorted(rows,key=lambda x:x["started_at"],reverse=True)


def gate2_readiness(db, project_id):
    blockers=[]; latest=latest_baseline(db,project_id); solution=current_solution(db,project_id)
    plan=db.execute("SELECT p.*,pr.id revision_id,pr.requirement_baseline_id,pr.solution_revision_id,pr.content_json FROM delivery_plans p JOIN delivery_plan_revisions pr ON pr.plan_id=p.id AND pr.revision=p.current_revision WHERE p.project_id=? ORDER BY p.updated_at DESC LIMIT 1",(project_id,)).fetchone()
    if not latest: blockers.append("GATE_1_NOT_FROZEN")
    if not solution: blockers.append("NO_COMMITTED_SOLUTION")
    elif latest and solution["requirement_baseline_id"]!=latest["id"]: blockers.append("STALE_COMMITTED_SOLUTION")
    if not plan: blockers.append("NO_COMMITTED_DELIVERY_PLAN")
    elif solution and (plan["solution_revision_id"]!=solution["revision_id"] or plan["requirement_baseline_id"]!=solution["requirement_baseline_id"]): blockers.append("STALE_COMMITTED_DELIVERY_PLAN")
    required_decisions=[]; uncovered=[]
    if solution:
        content=json.loads(solution["content_json"])
        required_decisions=[x["ref"] for x in content["open_decisions"] if x["classification"]=="REQUIRED_BEFORE_BASELINE"]
        if required_decisions: blockers.append("UNRESOLVED_REQUIRED_SOLUTION_DECISIONS")
        if latest:
            priorities={x["requirement_revision_id"]:x["priority"] for x in baseline_input(db,project_id,latest["id"]).requirements}
            coverage={x["requirement_revision_id"]:x["status"] for x in content["requirement_coverage"]}
            uncovered=[key for key,value in priorities.items() if value=="MUST" and coverage.get(key)!="COVERED"]
            if uncovered: blockers.append("UNCOVERED_MUST_REQUIREMENTS")
    if plan and solution and latest and not any(x.startswith("STALE_") for x in blockers):
        try: validate_plan(DeliveryPlanOutput.model_validate_json(plan["content_json"]),baseline_input(db,project_id,latest["id"]),json.loads(solution["content_json"]))
        except (HTTPException,ValidationError): blockers.append("INVALID_DELIVERY_PLAN")
    return {"ready":not blockers,"blocking_items":blockers,"requirement_baseline_id":latest["id"] if latest else None,
            "solution_revision_id":solution["revision_id"] if solution else None,"delivery_plan_revision_id":plan["revision_id"] if plan else None,
            "unresolved_decision_refs":required_decisions,"uncovered_must_requirement_revision_ids":uncovered}


@router.get("/delivery-baselines/readiness")
def get_gate2_readiness(project_id: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:return gate2_readiness(db,project_id)


@router.post("/delivery-baselines:freeze")
def freeze_delivery_baseline(project_id: str,idempotency_key: Optional[str]=Header(None),actor: Actor=Depends(current_actor)):
    require_project(actor,project_id,owner=True)
    if actor.actor_type!="HUMAN": raise HTTPException(403,"Only a human project owner can freeze Gate 2")
    key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"FREEZE_DELIVERY_BASELINE",key)
        if previous:return previous
        readiness=gate2_readiness(db,project_id)
        audit(db,project_id,actor.id,"HUMAN","DELIVERY_BASELINE_FREEZE_REQUESTED","DELIVERY_BASELINE",None,detail=readiness)
        if not readiness["ready"]: raise HTTPException(409,{"message":"Delivery baseline is blocked",**readiness})
        version=db.execute("SELECT COALESCE(MAX(version),0)+1 FROM delivery_baselines WHERE project_id=?",(project_id,)).fetchone()[0]
        baseline_id,stamp=uid("dbl"),now()
        db.execute("INSERT INTO delivery_baselines VALUES (?,?,?,?,?,?,?,?,?)",(baseline_id,project_id,version,"FROZEN",readiness["requirement_baseline_id"],readiness["solution_revision_id"],readiness["delivery_plan_revision_id"],actor.id,stamp))
        result={"baseline_id":baseline_id,"version":version,"status":"FROZEN","requirement_baseline_id":readiness["requirement_baseline_id"],"solution_revision_id":readiness["solution_revision_id"],"delivery_plan_revision_id":readiness["delivery_plan_revision_id"],"frozen_by":actor.id,"frozen_at":stamp,"membership_reconciliation":"CONFIRMED"}
        audit(db,project_id,actor.id,"HUMAN","DELIVERY_BASELINE_FROZEN","DELIVERY_BASELINE",baseline_id,detail=result);idem_put(db,project_id,actor.id,"FREEZE_DELIVERY_BASELINE",key,result)
    with connect() as db: confirmed=db.execute("SELECT * FROM delivery_baselines WHERE id=? AND project_id=?",(baseline_id,project_id)).fetchone()
    if not confirmed or confirmed["delivery_plan_revision_id"]!=readiness["delivery_plan_revision_id"]: raise HTTPException(503,"ACTION_SUCCEEDED_RESOLUTION_UNCONFIRMED")
    return result


@router.get("/delivery-baselines")
def list_delivery_baselines(project_id: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db: rows=db.execute("SELECT * FROM delivery_baselines WHERE project_id=? ORDER BY version DESC",(project_id,)).fetchall()
    return [dict(x) for x in rows]


@router.get("/delivery-baselines/{baseline_id}")
def get_delivery_baseline(project_id: str,baseline_id: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:
        row=db.execute("SELECT * FROM delivery_baselines WHERE id=? AND project_id=?",(baseline_id,project_id)).fetchone()
        if not row: raise HTTPException(404,"Delivery baseline not found")
        solution=db.execute("SELECT title,summary,content_json FROM solution_revisions WHERE id=? AND project_id=?",(row["solution_revision_id"],project_id)).fetchone()
        plan=db.execute("SELECT title,content_json FROM delivery_plan_revisions WHERE id=? AND project_id=?",(row["delivery_plan_revision_id"],project_id)).fetchone()
    return {**dict(row),"solution":{**dict(solution),"content":json.loads(solution["content_json"])} if solution else None,
            "delivery_plan":{**dict(plan),"content":json.loads(plan["content_json"])} if plan else None}


def phase2_truth_projection(project_id: str):
    with connect() as db:
        readiness=gate2_readiness(db,project_id); solution=current_solution(db,project_id)
        plan=db.execute("SELECT p.plan_code,pr.id revision_id FROM delivery_plans p JOIN delivery_plan_revisions pr ON pr.plan_id=p.id AND pr.revision=p.current_revision WHERE p.project_id=? ORDER BY p.updated_at DESC LIMIT 1",(project_id,)).fetchone()
        baseline=db.execute("SELECT * FROM delivery_baselines WHERE project_id=? ORDER BY version DESC LIMIT 1",(project_id,)).fetchone()
        solution_pending=db.execute("SELECT COUNT(*) FROM solution_candidates WHERE project_id=? AND status IN ('NEEDS_REVIEW','SELECTED')",(project_id,)).fetchone()[0]
        plan_pending=db.execute("SELECT COUNT(*) FROM delivery_plan_candidates WHERE project_id=? AND status='NEEDS_REVIEW'",(project_id,)).fetchone()[0]
        solution_run=db.execute("SELECT status,failure_code FROM solution_ai_runs WHERE project_id=? ORDER BY started_at DESC LIMIT 1",(project_id,)).fetchone()
        plan_run=db.execute("SELECT status,failure_code FROM delivery_plan_ai_runs WHERE project_id=? ORDER BY started_at DESC LIMIT 1",(project_id,)).fetchone()
    attention=[]
    if not baseline:
        if readiness["ready"]: attention.append({"type":"GATE_2","message":"Delivery baseline is ready for human freeze.","severity":"HIGH"})
        elif readiness["blocking_items"] and readiness["blocking_items"]!=["GATE_1_NOT_FROZEN"]: attention.append({"type":"DELIVERY_BASELINE_BLOCKED","message":", ".join(readiness["blocking_items"]),"severity":"HIGH"})
    if solution_pending: attention.append({"type":"SOLUTION_REVIEW","message":f"{solution_pending} solution candidate(s) need a decision.","severity":"MEDIUM"})
    if plan_pending: attention.append({"type":"DELIVERY_PLAN_REVIEW","message":f"{plan_pending} delivery plan candidate(s) need review.","severity":"MEDIUM"})
    if solution_run and solution_run["status"]=="FAILED": attention.append({"type":"SOLUTION_AI_FAILURE","message":solution_run["failure_code"],"severity":"HIGH"})
    if plan_run and plan_run["status"]=="FAILED": attention.append({"type":"DELIVERY_PLAN_AI_FAILURE","message":plan_run["failure_code"],"severity":"HIGH"})
    return {"solution":{"status":"COMMITTED" if solution else "NONE","solution_code":solution["solution_code"] if solution else None,"revision_id":solution["revision_id"] if solution else None},
            "delivery_plan":{"status":"COMMITTED" if plan else "NONE","plan_code":plan["plan_code"] if plan else None,"revision_id":plan["revision_id"] if plan else None},
            "design_ai":{"latest_solution_run_status":solution_run["status"] if solution_run else "NOT_RUN","latest_solution_failure_code":solution_run["failure_code"] if solution_run else None,"latest_plan_run_status":plan_run["status"] if plan_run else "NOT_RUN","latest_plan_failure_code":plan_run["failure_code"] if plan_run else None},
            "delivery_baseline":({"status":"FROZEN","id":baseline["id"],"version":baseline["version"],"frozen_by":baseline["frozen_by"],"frozen_at":baseline["frozen_at"]} if baseline else {"status":"NONE","version":None}),
            "delivery_readiness":"GATE_2_COMPLETE" if baseline else ("READY_TO_FREEZE" if readiness["ready"] else "BLOCKED"),
            "delivery_blocking_items":readiness["blocking_items"],"phase2_attention":attention,
            "next_recommended_phase":"PHASE_3_EXECUTION_AND_VALIDATION" if baseline else None}
