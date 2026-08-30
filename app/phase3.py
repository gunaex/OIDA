from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .ai import AIError, AIInvalidOutput, ExecutionBaselineInput, adapter_for
from .auth import Actor, current_actor, require_project
from .db import connect, now, transaction
from .config import settings
from .execution_targets import (
    CAPABILITIES, ExecutionTargetError, TargetCreateRequest, TargetUnavailable,
    adapter_for_target,
)
from .phase2 import audit, dumps, idem_get, idem_put, require_key, uid


router = APIRouter(prefix="/api/projects/{project_id}/execution", tags=["phase3"])

TARGETS = {"INTERNAL", "PM_AGAIN", "MANUAL_EXTERNAL"}
PRIORITIES = {"HIGH", "MEDIUM", "LOW"}
EXECUTION_TYPES = {"BUILD", "CONFIGURE", "INTEGRATE", "VALIDATE", "DOCUMENT", "MIGRATE", "OPERATE", "DECIDE"}


class GenerateMaterializationIn(BaseModel):
    instruction: str = Field(default="", max_length=2000)


class MaterializationItemPatch(BaseModel):
    target_type: Optional[Literal["INTERNAL", "PM_AGAIN", "MANUAL_EXTERNAL"]] = None
    binding_id: Optional[str] = None
    execution_title: Optional[str] = Field(default=None, min_length=3, max_length=160)
    execution_description: Optional[str] = Field(default=None, min_length=10, max_length=2500)
    owner_role: Optional[str] = Field(default=None, min_length=2, max_length=120)
    priority: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = None
    milestone_ref: Optional[str] = None
    execution_type: Optional[Literal["BUILD", "CONFIGURE", "INTEGRATE", "VALIDATE", "DOCUMENT", "MIGRATE", "OPERATE", "DECIDE"]] = None
    acceptance_hint: Optional[str] = Field(default=None, min_length=5, max_length=1500)
    dependencies: Optional[list[str]] = Field(default=None, max_length=20)
    external_reference: Optional[str] = Field(default=None, max_length=500)
    enabled: Optional[bool] = None


class ManualMaterializationItemIn(BaseModel):
    source_delivery_item_id: Optional[str] = None
    target_type: Literal["INTERNAL", "PM_AGAIN", "MANUAL_EXTERNAL"] = "INTERNAL"
    binding_id: Optional[str] = None
    execution_title: str = Field(min_length=3, max_length=160)
    execution_description: str = Field(min_length=10, max_length=2500)
    owner_role: str = Field(min_length=2, max_length=120)
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    milestone_ref: Optional[str] = None
    execution_type: Literal["BUILD", "CONFIGURE", "INTEGRATE", "VALIDATE", "DOCUMENT", "MIGRATE", "OPERATE", "DECIDE"] = "BUILD"
    acceptance_hint: str = Field(min_length=5, max_length=1500)
    dependencies: list[str] = Field(default_factory=list, max_length=20)
    external_reference: Optional[str] = Field(default=None, max_length=500)


class SplitItemIn(BaseModel):
    titles: list[str] = Field(min_length=2, max_length=4)


class MergeItemsIn(BaseModel):
    item_ids: list[str] = Field(min_length=2, max_length=4)
    title: str = Field(min_length=3, max_length=160)


class ManualExecutionItemIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=2500)
    owner_role: str = Field(min_length=2, max_length=120)
    priority: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    status: Literal["NOT_STARTED", "IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED"] = "NOT_STARTED"


class ExecutionItemPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=160)
    description: Optional[str] = Field(default=None, min_length=10, max_length=2500)
    owner_role: Optional[str] = Field(default=None, min_length=2, max_length=120)
    priority: Optional[Literal["HIGH", "MEDIUM", "LOW"]] = None
    status: Optional[Literal["NOT_STARTED", "IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED"]] = None
    milestone_ref: Optional[str] = None
    dependencies: Optional[list[str]] = Field(default=None, max_length=40)


class LinkExecutionIn(BaseModel):
    source_delivery_item_id: str


class BindingIn(BaseModel):
    external_project_id: str = Field(min_length=1, max_length=300)


class ManualPlanIn(BaseModel):
    summary: str = Field(default="Human-prepared execution routing plan.", min_length=10, max_length=3000)


class RejectPlanIn(BaseModel):
    reason: str = Field(default="AI materialization suggestion rejected by human reviewer.", min_length=3, max_length=1000)


def latest_delivery_baseline(db, project_id: str):
    return db.execute("SELECT * FROM delivery_baselines WHERE project_id=? ORDER BY version DESC LIMIT 1", (project_id,)).fetchone()


def source_packet(db, project_id: str) -> tuple[ExecutionBaselineInput, dict]:
    baseline = latest_delivery_baseline(db, project_id)
    if not baseline:
        raise HTTPException(409, "EXECUTION_READINESS_BLOCKED_NO_DELIVERY_BASELINE")
    project = db.execute("SELECT name,objective FROM projects WHERE id=?", (project_id,)).fetchone()
    items = []
    for row in db.execute("SELECT * FROM delivery_plan_revision_items WHERE plan_revision_id=? ORDER BY local_ref",
                          (baseline["delivery_plan_revision_id"],)).fetchall():
        item = dict(row)
        item["acceptance_criteria"] = json.loads(item.pop("acceptance_criteria_json"))
        item["requirement_revision_ids"] = json.loads(item.pop("requirement_revision_ids_json"))
        item["solution_component_refs"] = json.loads(item.pop("solution_component_refs_json"))
        items.append(item)
    dependencies = [dict(x) for x in db.execute(
        "SELECT predecessor_ref,successor_ref,dependency_type FROM delivery_plan_revision_dependencies WHERE plan_revision_id=?",
        (baseline["delivery_plan_revision_id"],)).fetchall()]
    milestones = []
    for row in db.execute("SELECT local_ref,title,item_refs_json FROM delivery_plan_revision_milestones WHERE plan_revision_id=?",
                          (baseline["delivery_plan_revision_id"],)).fetchall():
        milestones.append({"ref":row["local_ref"],"title":row["title"],"item_refs":json.loads(row["item_refs_json"])})
    bindings = {x["target_type"]:dict(x) for x in db.execute("SELECT * FROM execution_bindings WHERE project_id=?", (project_id,)).fetchall()}
    capabilities = []
    for target, capability in CAPABILITIES.items():
        value = capability.as_dict()
        value["binding_state"] = "READY" if target == "INTERNAL" else (
            "MANUAL" if target == "MANUAL_EXTERNAL" else bindings.get(target, {}).get("status", "UNBOUND"))
        capabilities.append(value)
    packet = ExecutionBaselineInput(project["name"], project["objective"], baseline["id"], baseline["version"],
        baseline["requirement_baseline_id"], baseline["solution_revision_id"], baseline["delivery_plan_revision_id"],
        items, dependencies, milestones, capabilities)
    return packet, dict(baseline)


def plan_item_view(row) -> dict:
    value = dict(row)
    value["enabled"] = bool(value["enabled"])
    value["dependencies"] = json.loads(value.pop("dependencies_json"))
    value["warnings"] = json.loads(value.pop("warnings_json"))
    return value


def execution_view(row) -> dict:
    value = dict(row)
    value["dependencies"] = json.loads(value.pop("dependencies_json"))
    value["expected"] = json.loads(value.pop("expected_json"))
    return value


def current_plan_content(db, plan_id: str) -> dict:
    row = db.execute("SELECT content_json FROM materialization_plan_revisions WHERE plan_id=? ORDER BY revision DESC LIMIT 1", (plan_id,)).fetchone()
    return json.loads(row[0]) if row else {"plan_summary":"Human-prepared execution routing plan."}


def snapshot_plan(db, plan_row, editor: str, actor_type: str, summary: Optional[str] = None) -> int:
    previous = current_plan_content(db, plan_row["id"])
    revision = plan_row["current_revision"] if not previous.get("items") else plan_row["current_revision"] + 1
    content = {"plan_summary":summary or previous.get("plan_summary") or "Execution materialization plan.",
        "routing_warnings":json.loads(plan_row["routing_warnings_json"]),
        "unresolved_items":json.loads(plan_row["unresolved_items_json"]),
        "items":[plan_item_view(x) for x in db.execute("SELECT * FROM materialization_items WHERE plan_id=? ORDER BY created_at,id", (plan_row["id"],)).fetchall()]}
    stamp = now()
    db.execute("INSERT INTO materialization_plan_revisions VALUES (?,?,?,?,?,?,?,?)",
               (uid("mprev"),plan_row["id"],plan_row["project_id"],revision,dumps(content),editor,actor_type,stamp))
    db.execute("UPDATE materialization_plans SET current_revision=?,updated_at=? WHERE id=?", (revision,stamp,plan_row["id"]))
    return revision


def binding_for(db, project_id: str, binding_id: Optional[str], target_type: str):
    if not binding_id: return None
    row = db.execute("SELECT * FROM execution_bindings WHERE id=? AND project_id=? AND target_type=?",
                     (binding_id,project_id,target_type)).fetchone()
    if not row: raise HTTPException(422, "Execution binding is unavailable for this project and target")
    return row


def source_refs(db, plan_row) -> tuple[set[str], set[str], dict[str, str]]:
    baseline = db.execute("SELECT delivery_plan_revision_id FROM delivery_baselines WHERE id=? AND project_id=?",
                          (plan_row["delivery_baseline_id"],plan_row["project_id"])).fetchone()
    if not baseline: raise HTTPException(409,"Source Delivery Baseline is unavailable")
    refs = {x["local_ref"]:x["id"] for x in db.execute(
        "SELECT id,local_ref FROM delivery_plan_revision_items WHERE plan_revision_id=?",(baseline["delivery_plan_revision_id"],)).fetchall()}
    milestones = {x["local_ref"] for x in db.execute(
        "SELECT local_ref FROM delivery_plan_revision_milestones WHERE plan_revision_id=?",(baseline["delivery_plan_revision_id"],)).fetchall()}
    return set(refs), milestones, refs


def item_ready_status(target_type: str, binding, external_reference: Optional[str], enabled: bool) -> tuple[str,list[str]]:
    if not enabled: return "DISABLED", []
    if target_type == "PM_AGAIN" and (not binding or binding["status"] != "READY"):
        return "BLOCKED", ["PM_AGAIN_BINDING_NOT_READY"]
    if target_type == "MANUAL_EXTERNAL" and not external_reference:
        return "BLOCKED", ["MANUAL_EXTERNAL_REFERENCE_REQUIRED"]
    return "PLANNED", []


def validate_ai_materialization(output, packet: ExecutionBaselineInput) -> None:
    refs={x["local_ref"] for x in packet.delivery_items};actual={x.source_delivery_item_ref for x in output.items}
    milestones={x["ref"] for x in packet.milestones}
    if actual != refs: raise AIInvalidOutput("Materialization output does not exactly cover the frozen delivery items")
    if any(x.target_type not in TARGETS for x in output.items): raise AIInvalidOutput("Materialization output contains an unsupported target")
    if any(not set(x.dependencies).issubset(refs) for x in output.items): raise AIInvalidOutput("Materialization output contains an unknown dependency")
    if any(x.milestone_ref and x.milestone_ref not in milestones for x in output.items): raise AIInvalidOutput("Materialization output contains an unknown milestone")


@router.get("/readiness")
def execution_readiness(project_id: str, actor: Actor = Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:
        baseline=latest_delivery_baseline(db,project_id)
    return {"ready":bool(baseline),"status":"READY" if baseline else "BLOCKED_NO_DELIVERY_BASELINE",
            "delivery_baseline_id":baseline["id"] if baseline else None,"delivery_baseline_version":baseline["version"] if baseline else None,
            "blocking_items":[] if baseline else ["BLOCKED_NO_DELIVERY_BASELINE"]}


def generate_materialization_plan_sync(project_id: str, body: GenerateMaterializationIn,
                                       idempotency_key: Optional[str], actor: Actor):
    require_project(actor,project_id); key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"GENERATE_MATERIALIZATION_PLAN",key)
        if previous:return previous
        packet,baseline=source_packet(db,project_id); adapter=adapter_for();run_id=uid("mrun");stamp=now()
        db.execute("INSERT INTO materialization_ai_runs (id,project_id,requested_by,provider,model,reasoning_effort,prompt_version,instruction,delivery_baseline_id,status,started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id,project_id,actor.id,adapter.provider,adapter.model,getattr(adapter,"reasoning_effort",None),"execution-materialization/v1",body.instruction,baseline["id"],"RUNNING",stamp))
        audit(db,project_id,f"ai:{run_id}","AI","MATERIALIZATION_PLAN_GENERATION_STARTED","MATERIALIZATION_AI_RUN",run_id)
        try:
            output=adapter.generate_materialization_plan(packet,body.instruction);validate_ai_materialization(output,packet)
            plan_id=uid("mplan")
            db.execute("INSERT INTO materialization_plans (id,project_id,delivery_baseline_id,ai_run_id,status,current_revision,routing_warnings_json,unresolved_items_json,authorized_by,authorized_at,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (plan_id,project_id,baseline["id"],run_id,"NEEDS_REVIEW",1,dumps(output.routing_warnings),dumps(output.unresolved_items),None,None,f"ai:{run_id}",stamp,stamp))
            # The explicit column form protects this insert from future additive columns.
        except Exception as exc:
            if not isinstance(exc, AIError): raise
            metrics=getattr(adapter,"last_metrics",None); values=metrics.as_dict() if metrics else {}
            db.execute("UPDATE materialization_ai_runs SET status='FAILED',failure_code=?,input_tokens=?,cache_hit_tokens=?,output_tokens=?,total_tokens=?,latency_ms=?,provider_request_id=?,completed_at=? WHERE id=?",
                (exc.code,values.get("input_tokens"),values.get("cache_hit_tokens"),values.get("output_tokens"),values.get("total_tokens"),values.get("latency_ms"),values.get("provider_request_id"),now(),run_id))
            result={"ai_run_id":run_id,"status":"FAILED","failure_code":exc.code,"message":str(exc),"provider":adapter.provider,"delivery_baseline_id":baseline["id"],"telemetry":values}
            audit(db,project_id,f"ai:{run_id}","AI","MATERIALIZATION_PLAN_GENERATION_FAILED","MATERIALIZATION_AI_RUN",run_id,"FAILED",{"failure_code":exc.code})
            idem_put(db,project_id,actor.id,"GENERATE_MATERIALIZATION_PLAN",key,result);return result
        refs={x["local_ref"]:x for x in packet.delivery_items}; bindings={x["target_type"]:x for x in db.execute("SELECT * FROM execution_bindings WHERE project_id=?",(project_id,)).fetchall()}
        for proposed in output.items:
            source=refs[proposed.source_delivery_item_ref];binding=bindings.get(proposed.target_type)
            status,warnings=item_ready_status(proposed.target_type,binding,None,True)
            warnings=[*proposed.warnings,*warnings]
            db.execute("INSERT INTO materialization_items (id,project_id,plan_id,source_delivery_item_id,source_delivery_item_ref,source_plan_revision_id,target_type,binding_id,execution_title,execution_description,owner_id,owner_role,priority,milestone_ref,execution_type,acceptance_hint,dependencies_json,warnings_json,external_reference,origin,enabled,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
                uid("mitem"),project_id,plan_id,source["id"],source["local_ref"],baseline["delivery_plan_revision_id"],
                proposed.target_type,binding["id"] if binding else None,proposed.execution_title,proposed.execution_description,
                None,proposed.suggested_owner_role,proposed.priority,proposed.milestone_ref,proposed.execution_type,
                proposed.acceptance_hint,dumps(proposed.dependencies),dumps(warnings),None,"AI",1,status,stamp,stamp))
        plan_row=db.execute("SELECT * FROM materialization_plans WHERE id=?",(plan_id,)).fetchone();snapshot_plan(db,plan_row,f"ai:{run_id}","AI",output.plan_summary)
        metrics=getattr(adapter,"last_metrics",None);values=metrics.as_dict() if metrics else {}
        db.execute("UPDATE materialization_ai_runs SET status='SUCCEEDED',findings_json=?,input_tokens=?,cache_hit_tokens=?,output_tokens=?,total_tokens=?,latency_ms=?,provider_request_id=?,completed_at=? WHERE id=?",
            (dumps(output.findings),values.get("input_tokens"),values.get("cache_hit_tokens"),values.get("output_tokens"),values.get("total_tokens"),values.get("latency_ms"),values.get("provider_request_id"),now(),run_id))
        result={"ai_run_id":run_id,"plan_id":plan_id,"status":"SUCCEEDED","item_count":len(output.items),"provider":adapter.provider,"model":adapter.model,"delivery_baseline_id":baseline["id"],"telemetry":values}
        audit(db,project_id,f"ai:{run_id}","AI","MATERIALIZATION_PLAN_GENERATED","MATERIALIZATION_PLAN",plan_id,detail={"item_count":len(output.items)})
        idem_put(db,project_id,actor.id,"GENERATE_MATERIALIZATION_PLAN",key,result)
        return result


@router.post("/materialization-plans:generate", status_code=202)
def generate_materialization_plan(project_id: str, body: GenerateMaterializationIn,
                                  idempotency_key: Optional[str]=Header(None), actor: Actor=Depends(current_actor)):
    from .jobs import enqueue
    require_project(actor,project_id);key=require_key(idempotency_key)
    with connect() as db: source_packet(db,project_id)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"QUEUE_MATERIALIZATION",key)
        if previous:return previous
        result=enqueue(db,project_id,actor,"MATERIALIZATION",body.model_dump());idem_put(db,project_id,actor.id,"QUEUE_MATERIALIZATION",key,result)
    return result


def plan_view(db, row) -> dict:
    value=dict(row);value["routing_warnings"]=json.loads(value.pop("routing_warnings_json"));value["unresolved_items"]=json.loads(value.pop("unresolved_items_json"))
    latest=current_plan_content(db,row["id"]);value["plan_summary"]=latest.get("plan_summary");value["items"]=[plan_item_view(x) for x in db.execute("SELECT * FROM materialization_items WHERE plan_id=? ORDER BY created_at,id",(row["id"],)).fetchall()]
    value["preview"]={"total":len(value["items"]),"enabled":sum(x["enabled"] for x in value["items"]),
        "blocked":sum(x["status"]=="BLOCKED" for x in value["items"]),"targets":{target:sum(x["target_type"]==target and x["enabled"] for x in value["items"]) for target in TARGETS}}
    return value


@router.get("/materialization-plans")
def list_materialization_plans(project_id: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db: rows=db.execute("SELECT * FROM materialization_plans WHERE project_id=? ORDER BY created_at DESC",(project_id,)).fetchall();return [plan_view(db,x) for x in rows]


@router.post("/materialization-plans", status_code=201)
def create_manual_materialization_plan(project_id: str, body: ManualPlanIn,
                                       idempotency_key: Optional[str]=Header(None), actor: Actor=Depends(current_actor)):
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"CREATE_MANUAL_MATERIALIZATION_PLAN",key)
        if previous:return previous
        _,baseline=source_packet(db,project_id);plan_id=uid("mplan");stamp=now()
        db.execute("INSERT INTO materialization_plans (id,project_id,delivery_baseline_id,ai_run_id,status,current_revision,routing_warnings_json,unresolved_items_json,authorized_by,authorized_at,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (plan_id,project_id,baseline["id"],None,"NEEDS_REVIEW",1,"[]","[]",None,None,actor.id,stamp,stamp))
        plan=db.execute("SELECT * FROM materialization_plans WHERE id=?",(plan_id,)).fetchone();snapshot_plan(db,plan,actor.id,"HUMAN",body.summary)
        result={"plan_id":plan_id,"status":"NEEDS_REVIEW","origin":"HUMAN","delivery_baseline_id":baseline["id"]}
        audit(db,project_id,actor.id,"HUMAN","MANUAL_MATERIALIZATION_PLAN_CREATED","MATERIALIZATION_PLAN",plan_id);idem_put(db,project_id,actor.id,"CREATE_MANUAL_MATERIALIZATION_PLAN",key,result)
    return result


@router.post("/materialization-plans/{plan_id}:reject")
def reject_materialization_plan(project_id: str, plan_id: str, body: RejectPlanIn, actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        plan=editable_plan(db,project_id,plan_id);stamp=now()
        db.execute("UPDATE materialization_plans SET status='REJECTED',updated_at=? WHERE id=?",(stamp,plan_id))
        audit(db,project_id,actor.id,"HUMAN","MATERIALIZATION_PLAN_REJECTED","MATERIALIZATION_PLAN",plan_id,detail={"reason":body.reason,"revision":plan["current_revision"]})
    return {"plan_id":plan_id,"status":"REJECTED","reason":body.reason}


def editable_plan(db, project_id: str, plan_id: str):
    row=db.execute("SELECT * FROM materialization_plans WHERE id=? AND project_id=?",(plan_id,project_id)).fetchone()
    if not row: raise HTTPException(404,"Materialization plan not found")
    if row["status"]!="NEEDS_REVIEW": raise HTTPException(409,"Materialization plan is no longer editable")
    latest=latest_delivery_baseline(db,project_id)
    if not latest or latest["id"]!=row["delivery_baseline_id"]: raise HTTPException(409,"Materialization plan is stale")
    return row


@router.patch("/materialization-plans/{plan_id}/items/{item_id}")
def patch_materialization_item(project_id: str,plan_id: str,item_id: str,body: MaterializationItemPatch,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        plan=editable_plan(db,project_id,plan_id);item=db.execute("SELECT * FROM materialization_items WHERE id=? AND plan_id=? AND project_id=?",(item_id,plan_id,project_id)).fetchone()
        if not item:raise HTTPException(404,"Materialization item not found")
        changes=body.model_dump(exclude_unset=True);target=changes.get("target_type",item["target_type"]);binding_id=changes.get("binding_id",item["binding_id"])
        binding=binding_for(db,project_id,binding_id,target) if binding_id else None;enabled=changes.get("enabled",bool(item["enabled"]));external=changes.get("external_reference",item["external_reference"])
        refs,milestones,_=source_refs(db,plan)
        if "dependencies" in changes and not set(changes["dependencies"]).issubset(refs):raise HTTPException(422,"Dependency references an unknown frozen delivery item")
        milestone=changes.get("milestone_ref",item["milestone_ref"])
        if milestone and milestone not in milestones:raise HTTPException(422,"Milestone is outside the frozen Delivery Baseline")
        status,warnings=item_ready_status(target,binding,external,enabled)
        fields={"target_type":target,"binding_id":binding_id,"execution_title":changes.get("execution_title",item["execution_title"]),
            "execution_description":changes.get("execution_description",item["execution_description"]),"owner_role":changes.get("owner_role",item["owner_role"]),
            "priority":changes.get("priority",item["priority"]),"milestone_ref":milestone,"execution_type":changes.get("execution_type",item["execution_type"]),
            "acceptance_hint":changes.get("acceptance_hint",item["acceptance_hint"]),"dependencies_json":dumps(changes.get("dependencies",json.loads(item["dependencies_json"]))),
            "external_reference":external,"enabled":int(enabled),"status":status,"warnings_json":dumps(warnings),"updated_at":now()}
        db.execute("UPDATE materialization_items SET target_type=:target_type,binding_id=:binding_id,execution_title=:execution_title,execution_description=:execution_description,owner_role=:owner_role,priority=:priority,milestone_ref=:milestone_ref,execution_type=:execution_type,acceptance_hint=:acceptance_hint,dependencies_json=:dependencies_json,external_reference=:external_reference,enabled=:enabled,status=:status,warnings_json=:warnings_json,updated_at=:updated_at WHERE id=:id",{**fields,"id":item_id})
        revision=snapshot_plan(db,plan,actor.id,"HUMAN");audit(db,project_id,actor.id,"HUMAN","MATERIALIZATION_PLAN_EDITED","MATERIALIZATION_PLAN",plan_id,detail={"item_id":item_id,"revision":revision})
    return {"id":item_id,"plan_id":plan_id,"current_revision":revision,"status":status,"human_override":True}


@router.post("/materialization-plans/{plan_id}/items",status_code=201)
def add_materialization_item(project_id: str,plan_id: str,body: ManualMaterializationItemIn,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        plan=editable_plan(db,project_id,plan_id);refs,milestones,ref_ids=source_refs(db,plan);source=None;source_ref=None
        if body.source_delivery_item_id:
            source=db.execute("SELECT id,local_ref FROM delivery_plan_revision_items WHERE id=? AND plan_revision_id=?",(body.source_delivery_item_id,db.execute("SELECT delivery_plan_revision_id FROM delivery_baselines WHERE id=?",(plan["delivery_baseline_id"],)).fetchone()[0])).fetchone()
            if not source:raise HTTPException(422,"Source delivery item is outside the frozen Delivery Baseline")
            source_ref=source["local_ref"]
        if body.milestone_ref and body.milestone_ref not in milestones:raise HTTPException(422,"Milestone is outside the frozen Delivery Baseline")
        if not set(body.dependencies).issubset(refs):raise HTTPException(422,"Dependency references an unknown frozen delivery item")
        binding=binding_for(db,project_id,body.binding_id,body.target_type) if body.binding_id else None;status,warnings=item_ready_status(body.target_type,binding,body.external_reference,True);item_id=uid("mitem");stamp=now()
        db.execute("INSERT INTO materialization_items (id,project_id,plan_id,source_delivery_item_id,source_delivery_item_ref,source_plan_revision_id,target_type,binding_id,execution_title,execution_description,owner_id,owner_role,priority,milestone_ref,execution_type,acceptance_hint,dependencies_json,warnings_json,external_reference,origin,enabled,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(item_id,project_id,plan_id,source["id"] if source else None,source_ref,db.execute("SELECT delivery_plan_revision_id FROM delivery_baselines WHERE id=?",(plan["delivery_baseline_id"],)).fetchone()[0],body.target_type,body.binding_id,body.execution_title,body.execution_description,None,body.owner_role,body.priority,body.milestone_ref,body.execution_type,body.acceptance_hint,dumps(body.dependencies),dumps(warnings),body.external_reference,"HUMAN",1,status,stamp,stamp))
        revision=snapshot_plan(db,plan,actor.id,"HUMAN");audit(db,project_id,actor.id,"HUMAN","MATERIALIZATION_MANUAL_ITEM_ADDED","MATERIALIZATION_ITEM",item_id,detail={"revision":revision})
    return {"id":item_id,"plan_id":plan_id,"status":status,"origin":"HUMAN","current_revision":revision}


@router.post("/materialization-plans/{plan_id}/items/{item_id}:split")
def split_materialization_item(project_id: str,plan_id: str,item_id: str,body: SplitItemIn,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        plan=editable_plan(db,project_id,plan_id);source=db.execute("SELECT * FROM materialization_items WHERE id=? AND plan_id=? AND project_id=?",(item_id,plan_id,project_id)).fetchone()
        if not source:raise HTTPException(404,"Materialization item not found")
        if not source["enabled"]:raise HTTPException(409,"Disabled item cannot be split")
        stamp=now();ids=[]
        for title in body.titles:
            new_id=uid("mitem");values=list(source);values[0]=new_id;values[8]=title;values[19]="HUMAN";values[22]=stamp;values[23]=stamp
            db.execute("INSERT INTO materialization_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",values);ids.append(new_id)
        db.execute("UPDATE materialization_items SET enabled=0,status='DISABLED',updated_at=? WHERE id=?",(stamp,item_id));revision=snapshot_plan(db,plan,actor.id,"HUMAN");audit(db,project_id,actor.id,"HUMAN","MATERIALIZATION_ITEM_SPLIT","MATERIALIZATION_ITEM",item_id,detail={"new_item_ids":ids})
    return {"source_item_id":item_id,"new_item_ids":ids,"current_revision":revision}


@router.post("/materialization-plans/{plan_id}/items:merge",status_code=201)
def merge_materialization_items(project_id: str,plan_id: str,body: MergeItemsIn,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        plan=editable_plan(db,project_id,plan_id);marks=','.join('?' for _ in body.item_ids);rows=db.execute(f"SELECT * FROM materialization_items WHERE project_id=? AND plan_id=? AND id IN ({marks})",(project_id,plan_id,*body.item_ids)).fetchall()
        if len(rows)!=len(set(body.item_ids)):raise HTTPException(404,"One or more materialization items were not found")
        if len({x["target_type"] for x in rows})!=1:raise HTTPException(422,"Only items routed to the same target can be merged")
        first=rows[0];new_id=uid("mitem");stamp=now();dependencies=[];warnings=[]
        for row in rows:
            dependencies.extend(x for x in json.loads(row["dependencies_json"]) if x not in dependencies);warnings.extend(x for x in json.loads(row["warnings_json"]) if x not in warnings)
        values=list(first);values[0]=new_id;values[3]=None;values[4]=None;values[8]=body.title;values[9]=' '.join(x["execution_description"] for x in rows);values[16]=dumps(dependencies);values[17]=dumps(warnings);values[19]="HUMAN";values[22]=stamp;values[23]=stamp
        db.execute("INSERT INTO materialization_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",values)
        db.execute(f"UPDATE materialization_items SET enabled=0,status='DISABLED',updated_at=? WHERE project_id=? AND plan_id=? AND id IN ({marks})",(stamp,project_id,plan_id,*body.item_ids));revision=snapshot_plan(db,plan,actor.id,"HUMAN");audit(db,project_id,actor.id,"HUMAN","MATERIALIZATION_ITEMS_MERGED","MATERIALIZATION_ITEM",new_id,detail={"source_item_ids":body.item_ids})
    return {"id":new_id,"source_item_ids":body.item_ids,"origin":"HUMAN","current_revision":revision}


@router.post("/materialization-plans/{plan_id}:authorize")
def authorize_materialization(project_id: str,plan_id: str,idempotency_key: Optional[str]=Header(None),actor: Actor=Depends(current_actor)):
    if actor.actor_type != "HUMAN": raise HTTPException(403,"Only a human project owner may authorize execution materialization")
    require_project(actor,project_id,owner=True);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"AUTHORIZE_MATERIALIZATION",key)
        if previous:return previous
        plan=editable_plan(db,project_id,plan_id);items=db.execute("SELECT * FROM materialization_items WHERE plan_id=? AND project_id=?",(plan_id,project_id)).fetchall();ready=sum(x["enabled"] and x["status"]=="PLANNED" for x in items);blocked=sum(x["enabled"] and x["status"]=="BLOCKED" for x in items)
        if not ready:raise HTTPException(409,"No ready materialization items are available for authorization")
        stamp=now();db.execute("UPDATE materialization_plans SET status='AUTHORIZED',authorized_by=?,authorized_at=?,updated_at=? WHERE id=?",(actor.id,stamp,stamp,plan_id))
        result={"plan_id":plan_id,"status":"AUTHORIZED","ready_item_count":ready,"blocked_item_count":blocked,"authorized_by":actor.id,"authorized_at":stamp}
        audit(db,project_id,actor.id,"HUMAN","MATERIALIZATION_AUTHORIZED","MATERIALIZATION_PLAN",plan_id,detail=result);idem_put(db,project_id,actor.id,"AUTHORIZE_MATERIALIZATION",key,result)
    return result


def next_execution_code(db,project_id: str) -> str:
    value=db.execute("SELECT next_execution_number FROM projects WHERE id=?",(project_id,)).fetchone()[0]
    db.execute("UPDATE projects SET next_execution_number=next_execution_number+1,updated_at=? WHERE id=?",(now(),project_id));return f"EXEC-{value:03d}"


def expected_from_item(item, dependencies: list[str]) -> dict:
    return {"title":item["execution_title"],"description":item["execution_description"],"owner_role":item["owner_role"],
            "priority":item["priority"],"milestone_ref":item["milestone_ref"],"dependencies":dependencies}


def materialize_one(db,project_id: str,plan,item,actor: Actor):
    existing=db.execute("SELECT * FROM execution_items WHERE materialization_item_id=? AND project_id=?",(item["id"],project_id)).fetchone()
    if existing:
        return existing
    execution_id=uid("exec");stamp=now();code=next_execution_code(db,project_id);expected=expected_from_item(item,[]);link_state="LINKED" if item["source_delivery_item_id"] else "UNLINKED"
    db.execute("INSERT INTO execution_items (id,project_id,execution_code,materialization_plan_id,materialization_item_id,source_delivery_item_id,source_plan_revision_id,target_type,binding_id,external_id,external_url,title,description,owner_id,owner_role,priority,status,milestone_ref,dependencies_json,expected_json,link_state,reconciliation_status,last_verified_at,current_revision,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
        execution_id,project_id,code,plan["id"],item["id"],item["source_delivery_item_id"],item["source_plan_revision_id"],item["target_type"],item["binding_id"],None,None,
        item["execution_title"],item["execution_description"],item["owner_id"],item["owner_role"],item["priority"],"NOT_STARTED",item["milestone_ref"],"[]",dumps(expected),link_state,"NOT_CHECKED",None,1,actor.id,stamp,stamp))
    db.execute("INSERT INTO execution_item_revisions VALUES (?,?,?,?,?,?,?,?)",(uid("exrev"),execution_id,project_id,1,dumps(expected),actor.id,"HUMAN",stamp))
    return db.execute("SELECT * FROM execution_items WHERE id=?",(execution_id,)).fetchone()


@router.post("/materialization-plans/{plan_id}:materialize")
def materialize_plan(project_id: str,plan_id: str,idempotency_key: Optional[str]=Header(None),actor: Actor=Depends(current_actor)):
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"MATERIALIZE_EXECUTION",key)
        if previous:return previous
        plan=db.execute("SELECT * FROM materialization_plans WHERE id=? AND project_id=?",(plan_id,project_id)).fetchone()
        if not plan:raise HTTPException(404,"Materialization plan not found")
        if plan["status"] not in {"AUTHORIZED","PARTIAL"}:raise HTTPException(409,"Human authorization is required before materialization")
        latest=latest_delivery_baseline(db,project_id)
        if not latest or latest["id"]!=plan["delivery_baseline_id"]:raise HTTPException(409,"Authorized materialization plan is stale")
        items=db.execute("SELECT * FROM materialization_items WHERE plan_id=? AND project_id=? ORDER BY created_at,id",(plan_id,project_id)).fetchall();results=[]
        audit(db,project_id,actor.id,"HUMAN","MATERIALIZATION_STARTED","MATERIALIZATION_PLAN",plan_id,detail={"enabled_item_count":sum(bool(x["enabled"]) for x in items)})
        for item in items:
            if not item["enabled"]:continue
            if item["status"]=="BLOCKED":results.append({"item_id":item["id"],"status":"BLOCKED"});continue
            db.execute("UPDATE materialization_items SET status='MATERIALIZING',updated_at=? WHERE id=?",(now(),item["id"]));audit(db,project_id,actor.id,"HUMAN","EXECUTION_ITEM_CREATE_REQUESTED","MATERIALIZATION_ITEM",item["id"])
            execution=materialize_one(db,project_id,plan,item,actor)
            request=TargetCreateRequest(execution["id"],project_id,item["binding_id"],item["execution_title"],item["execution_description"],item["owner_role"],item["priority"],item["milestone_ref"],[],f"{plan_id}:{item['id']}",item["external_reference"])
            try:
                target=adapter_for_target(item["target_type"]);created=target.create_work_item(db,request)
                db.execute("UPDATE execution_items SET external_id=?,external_url=?,updated_at=? WHERE id=?",(created.external_id,created.external_url,now(),execution["id"]));readback=target.get_work_item(db,project_id,item["binding_id"],created.external_id)
                if not readback:
                    db.execute("UPDATE execution_items SET reconciliation_status='UNCONFIRMED',updated_at=? WHERE id=?",(now(),execution["id"]));db.execute("UPDATE materialization_items SET status='UNCONFIRMED',updated_at=? WHERE id=?",(now(),item["id"]));status="UNCONFIRMED";audit(db,project_id,"system:materialization","SYSTEM","EXECUTION_ITEM_CREATE_UNCONFIRMED","EXECUTION_ITEM",execution["id"],"UNCONFIRMED")
                else:
                    db.execute("UPDATE execution_items SET reconciliation_status='CONFIRMED',last_verified_at=?,updated_at=? WHERE id=?",(now(),now(),execution["id"]));db.execute("UPDATE materialization_items SET status='MATERIALIZED',updated_at=? WHERE id=?",(now(),item["id"]));status="CONFIRMED";audit(db,project_id,"system:materialization","SYSTEM","EXECUTION_ITEM_CREATE_CONFIRMED","EXECUTION_ITEM",execution["id"])
            except ExecutionTargetError as exc:
                db.execute("UPDATE execution_items SET reconciliation_status='ERROR',updated_at=? WHERE id=?",(now(),execution["id"]));db.execute("UPDATE materialization_items SET status='FAILED',warnings_json=?,updated_at=? WHERE id=?",(dumps([exc.code]),now(),item["id"]));status="FAILED";audit(db,project_id,"system:materialization","SYSTEM","EXECUTION_ITEM_CREATE_FAILED","EXECUTION_ITEM",execution["id"],"FAILED",{"failure_code":exc.code})
            results.append({"item_id":item["id"],"execution_item_id":execution["id"],"status":status})
        # Materialize dependency links only after semantic create IDs are known.
        source_map={}
        for row in db.execute("SELECT e.id,m.source_delivery_item_ref FROM execution_items e JOIN materialization_items m ON m.id=e.materialization_item_id WHERE e.project_id=? AND e.materialization_plan_id=?",(project_id,plan_id)).fetchall():source_map.setdefault(row["source_delivery_item_ref"],[]).append(row["id"])
        for item in items:
            execution=db.execute("SELECT * FROM execution_items WHERE materialization_item_id=?",(item["id"],)).fetchone()
            if not execution:continue
            deps=[]
            for source_ref in json.loads(item["dependencies_json"]):deps.extend(x for x in source_map.get(source_ref,[]) if x not in deps)
            expected=expected_from_item(item,deps);db.execute("UPDATE execution_items SET dependencies_json=?,expected_json=?,updated_at=? WHERE id=?",(dumps(deps),dumps(expected),now(),execution["id"]))
        counts={state:sum(x["status"]==state for x in results) for state in ["CONFIRMED","FAILED","UNCONFIRMED","BLOCKED"]};overall="MATERIALIZED" if counts["CONFIRMED"]==len(results) else "PARTIAL"
        db.execute("UPDATE materialization_plans SET status=?,updated_at=? WHERE id=?",(overall,now(),plan_id));result={"plan_id":plan_id,"status":overall,"requested_count":len(results),"confirmed_count":counts["CONFIRMED"],"failed_count":counts["FAILED"],"unconfirmed_count":counts["UNCONFIRMED"],"blocked_count":counts["BLOCKED"],"results":results};audit(db,project_id,"system:materialization","SYSTEM","MATERIALIZATION_COMPLETED" if overall=="MATERIALIZED" else "MATERIALIZATION_PARTIAL","MATERIALIZATION_PLAN",plan_id,result="SUCCESS" if overall=="MATERIALIZED" else "PARTIAL",detail={key:value for key,value in result.items() if key!="results"})
        idem_put(db,project_id,actor.id,"MATERIALIZE_EXECUTION",key,result)
    return result


@router.get("/items")
def list_execution_items(project_id: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:rows=db.execute("SELECT * FROM execution_items WHERE project_id=? ORDER BY created_at,id",(project_id,)).fetchall();return [execution_view(x) for x in rows]


@router.post("/items",status_code=201)
def add_manual_execution_item(project_id: str,body: ManualExecutionItemIn,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        baseline=latest_delivery_baseline(db,project_id)
        if not baseline:raise HTTPException(409,"EXECUTION_READINESS_BLOCKED_NO_DELIVERY_BASELINE")
        execution_id=uid("exec");stamp=now();code=next_execution_code(db,project_id);expected={"title":body.title,"description":body.description,"owner_role":body.owner_role,"priority":body.priority,"milestone_ref":None,"dependencies":[]}
        db.execute("INSERT INTO execution_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(execution_id,project_id,code,None,None,None,baseline["delivery_plan_revision_id"],"INTERNAL",None,execution_id,None,body.title,body.description,None,body.owner_role,body.priority,body.status,None,"[]",dumps(expected),"UNLINKED","CONFIRMED",stamp,1,actor.id,stamp,stamp))
        db.execute("INSERT INTO execution_item_revisions VALUES (?,?,?,?,?,?,?,?)",(uid("exrev"),execution_id,project_id,1,dumps(expected),actor.id,"HUMAN",stamp));audit(db,project_id,actor.id,"HUMAN","MANUAL_EXECUTION_ITEM_ADDED","EXECUTION_ITEM",execution_id)
    return {"id":execution_id,"execution_code":code,"target_type":"INTERNAL","link_state":"UNLINKED","reconciliation_status":"CONFIRMED"}


@router.patch("/items/{execution_item_id}")
def update_execution_item(project_id: str,execution_item_id: str,body: ExecutionItemPatch,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        row=db.execute("SELECT * FROM execution_items WHERE id=? AND project_id=?",(execution_item_id,project_id)).fetchone()
        if not row:raise HTTPException(404,"Execution item not found")
        if row["target_type"]!="INTERNAL":raise HTTPException(409,"External execution status is authoritative in its target")
        changes=body.model_dump(exclude_unset=True)
        if "dependencies" in changes:
            marks=','.join('?' for _ in changes["dependencies"])
            found=0 if not changes["dependencies"] else db.execute(f"SELECT COUNT(*) FROM execution_items WHERE project_id=? AND id IN ({marks})",(project_id,*changes["dependencies"])).fetchone()[0]
            if found!=len(set(changes["dependencies"])) or execution_item_id in changes["dependencies"]:raise HTTPException(422,"Execution dependency is unknown, cross-project, or self-referential")
        revision=row["current_revision"]+1;stamp=now();values={"title":changes.get("title",row["title"]),"description":changes.get("description",row["description"]),"owner_role":changes.get("owner_role",row["owner_role"]),"priority":changes.get("priority",row["priority"]),"status":changes.get("status",row["status"]),"milestone_ref":changes.get("milestone_ref",row["milestone_ref"]),"dependencies_json":dumps(changes.get("dependencies",json.loads(row["dependencies_json"])))}
        db.execute("UPDATE execution_items SET title=:title,description=:description,owner_role=:owner_role,priority=:priority,status=:status,milestone_ref=:milestone_ref,dependencies_json=:dependencies_json,current_revision=:revision,updated_at=:stamp WHERE id=:id",{**values,"revision":revision,"stamp":stamp,"id":execution_item_id})
        db.execute("INSERT INTO execution_item_revisions VALUES (?,?,?,?,?,?,?,?)",(uid("exrev"),execution_item_id,project_id,revision,dumps(values),actor.id,"HUMAN",stamp));audit(db,project_id,actor.id,"HUMAN","EXECUTION_ITEM_UPDATED","EXECUTION_ITEM",execution_item_id,detail={"revision":revision})
    return {"id":execution_item_id,"current_revision":revision,"status":values["status"]}


@router.post("/items/{execution_item_id}:link")
def link_execution_item(project_id: str,execution_item_id: str,body: LinkExecutionIn,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        row=db.execute("SELECT * FROM execution_items WHERE id=? AND project_id=?",(execution_item_id,project_id)).fetchone()
        if not row:raise HTTPException(404,"Execution item not found")
        baseline=latest_delivery_baseline(db,project_id);source=db.execute("SELECT id FROM delivery_plan_revision_items WHERE id=? AND plan_revision_id=?",(body.source_delivery_item_id,baseline["delivery_plan_revision_id"] if baseline else None)).fetchone()
        if not source:raise HTTPException(422,"Delivery item is outside the frozen Delivery Baseline")
        db.execute("UPDATE execution_items SET source_delivery_item_id=?,source_plan_revision_id=?,link_state='LINKED',updated_at=? WHERE id=?",(source["id"],baseline["delivery_plan_revision_id"],now(),execution_item_id));audit(db,project_id,actor.id,"HUMAN","EXECUTION_ITEM_LINKED","EXECUTION_ITEM",execution_item_id,detail={"source_delivery_item_id":source["id"]})
    return {"id":execution_item_id,"link_state":"LINKED","source_delivery_item_id":source["id"]}


def upsert_drift(db,project_id: str,baseline_id: str,key: str,drift_type: str,severity: str,detail: dict,source_id=None,execution_id=None):
    existing=db.execute("SELECT id,status FROM execution_drift_records WHERE project_id=? AND detected_key=?",(project_id,key)).fetchone();stamp=now()
    if existing:
        db.execute("UPDATE execution_drift_records SET drift_type=?,severity=?,detail_json=?,status=CASE WHEN status='ACKNOWLEDGED' THEN status ELSE 'OPEN' END,detected_at=?,resolved_at=NULL WHERE id=?",(drift_type,severity,dumps(detail),stamp,existing["id"]));return existing["id"]
    drift_id=uid("drift");db.execute("INSERT INTO execution_drift_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(drift_id,project_id,key,baseline_id,source_id,execution_id,drift_type,severity,"OPEN",dumps(detail),stamp,None,None,None));audit(db,project_id,"system:reconciliation","SYSTEM","DRIFT_DETECTED","EXECUTION_DRIFT",drift_id,detail={"drift_type":drift_type});return drift_id


@router.post(":reconcile")
def reconcile_execution(project_id: str,idempotency_key: Optional[str]=Header(None),actor: Actor=Depends(current_actor)):
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"RECONCILE_EXECUTION",key)
        if previous:return previous
        packet,baseline=source_packet(db,project_id);run_id=uid("recon");stamp=now();db.execute("INSERT INTO execution_reconciliation_runs (id,project_id,delivery_baseline_id,requested_by,status,confirmed_count,missing_count,mismatch_count,stale_count,unconfirmed_count,started_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(run_id,project_id,baseline["id"],actor.id,"RUNNING",0,0,0,0,0,stamp,None));audit(db,project_id,actor.id,"HUMAN","RECONCILIATION_STARTED","EXECUTION_RECONCILIATION",run_id)
        detected=[];confirmed=missing=mismatch=stale=unconfirmed=0;items=db.execute("SELECT * FROM execution_items WHERE project_id=?",(project_id,)).fetchall()
        for row in items:
            if row["link_state"]=="UNLINKED":
                drift_key=f"unlinked:{row['id']}";upsert_drift(db,project_id,baseline["id"],drift_key,"UNLINKED_EXECUTION","WARNING",{"execution_code":row["execution_code"]},execution_id=row["id"]);detected.append(drift_key)
            try:
                actual=adapter_for_target(row["target_type"]).get_work_item(db,project_id,row["binding_id"],row["external_id"] or row["id"])
            except ExecutionTargetError:
                actual=None
            if not actual:
                drift_key=f"missing:{row['id']}";upsert_drift(db,project_id,baseline["id"],drift_key,"EXTERNAL_ITEM_MISSING","CRITICAL",{"execution_code":row["execution_code"]},row["source_delivery_item_id"],row["id"]);detected.append(drift_key);missing+=1;db.execute("UPDATE execution_items SET reconciliation_status='ERROR',updated_at=? WHERE id=?",(now(),row["id"]));continue
            expected=json.loads(row["expected_json"]);actual_values={"title":actual.title,"description":actual.description,"owner_role":actual.owner_role,"priority":actual.priority,"milestone_ref":actual.milestone_ref,"dependencies":actual.dependencies}
            differences=[name for name in expected if expected[name]!=actual_values.get(name)]
            if differences:
                drift_type="OWNER_DRIFT" if differences==["owner_role"] else ("DEPENDENCY_DRIFT" if differences==["dependencies"] else ("MILESTONE_DRIFT" if differences==["milestone_ref"] else "SCOPE_DRIFT"));drift_key=f"mismatch:{row['id']}:{drift_type}";upsert_drift(db,project_id,baseline["id"],drift_key,drift_type,"WARNING",{"fields":differences,"execution_code":row["execution_code"]},row["source_delivery_item_id"],row["id"]);detected.append(drift_key);mismatch+=1;state="MISMATCH"
            else:confirmed+=1;state="CONFIRMED"
            db.execute("UPDATE execution_items SET reconciliation_status=?,last_verified_at=?,updated_at=? WHERE id=?",(state,now(),now(),row["id"]))
        materialized_sources={x[0] for x in db.execute("SELECT DISTINCT source_delivery_item_id FROM execution_items WHERE project_id=? AND source_delivery_item_id IS NOT NULL",(project_id,)).fetchall()}
        for source in packet.delivery_items:
            if source["id"] not in materialized_sources:
                drift_key=f"baseline-missing:{source['id']}";upsert_drift(db,project_id,baseline["id"],drift_key,"MISSING_EXECUTION","CRITICAL",{"delivery_item_ref":source["local_ref"]},source["id"]);detected.append(drift_key);missing+=1
        open_rows=db.execute("SELECT id,detected_key FROM execution_drift_records WHERE project_id=? AND status IN ('OPEN','ACKNOWLEDGED')",(project_id,)).fetchall()
        for drift in open_rows:
            if drift["detected_key"] not in detected:db.execute("UPDATE execution_drift_records SET status='RESOLVED',resolved_at=? WHERE id=?",(now(),drift["id"]));audit(db,project_id,"system:reconciliation","SYSTEM","DRIFT_RESOLVED","EXECUTION_DRIFT",drift["id"])
        overall="SUCCEEDED" if not detected and not (missing or mismatch or stale or unconfirmed) else "PARTIAL";db.execute("UPDATE execution_reconciliation_runs SET status=?,confirmed_count=?,missing_count=?,mismatch_count=?,stale_count=?,unconfirmed_count=?,completed_at=? WHERE id=?",(overall,confirmed,missing,mismatch,stale,unconfirmed,now(),run_id));result={"run_id":run_id,"status":overall,"confirmed_count":confirmed,"missing_count":missing,"mismatch_count":mismatch,"stale_count":stale,"unconfirmed_count":unconfirmed,"drift_count":len(detected)};audit(db,project_id,"system:reconciliation","SYSTEM","RECONCILIATION_CONFIRMED" if overall=="SUCCEEDED" else "RECONCILIATION_MISMATCH","EXECUTION_RECONCILIATION",run_id,detail=result);idem_put(db,project_id,actor.id,"RECONCILE_EXECUTION",key,result)
    return result


@router.get("/drift")
def list_drift(project_id: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:rows=db.execute("SELECT * FROM execution_drift_records WHERE project_id=? ORDER BY detected_at DESC",(project_id,)).fetchall()
    result=[]
    for row in rows:value=dict(row);value["detail"]=json.loads(value.pop("detail_json"));result.append(value)
    return result


@router.post("/drift/{drift_id}:acknowledge")
def acknowledge_drift(project_id: str,drift_id: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        row=db.execute("SELECT * FROM execution_drift_records WHERE id=? AND project_id=?",(drift_id,project_id)).fetchone()
        if not row:raise HTTPException(404,"Drift record not found")
        if row["status"]=="RESOLVED":raise HTTPException(409,"Resolved drift no longer needs acknowledgement")
        db.execute("UPDATE execution_drift_records SET status='ACKNOWLEDGED',acknowledged_by=?,acknowledged_at=? WHERE id=?",(actor.id,now(),drift_id));audit(db,project_id,actor.id,"HUMAN","DRIFT_ACKNOWLEDGED","EXECUTION_DRIFT",drift_id)
    return {"id":drift_id,"status":"ACKNOWLEDGED"}


def execution_truth_projection(project_id: str) -> dict:
    with connect() as db:
        baseline=latest_delivery_baseline(db,project_id)
        if not baseline:return {"execution_materialization_status":"BLOCKED_NO_DELIVERY_BASELINE","execution_materialization_progress":{"materialized":0,"total":0},"execution_binding_status":"UNBOUND","execution_health":"BLOCKED","execution_blockers":["BLOCKED_NO_DELIVERY_BASELINE"],"execution_drift":{"open":0,"acknowledged":0},"execution_attention":[],"execution_next_action":"Freeze Delivery Baseline"}
        total=db.execute("SELECT COUNT(*) FROM delivery_plan_revision_items WHERE plan_revision_id=?",(baseline["delivery_plan_revision_id"],)).fetchone()[0]
        materialized=db.execute("SELECT COUNT(DISTINCT source_delivery_item_id) FROM execution_items WHERE project_id=? AND source_delivery_item_id IS NOT NULL",(project_id,)).fetchone()[0]
        plan=db.execute("SELECT status FROM materialization_plans WHERE project_id=? AND delivery_baseline_id=? ORDER BY created_at DESC LIMIT 1",(project_id,baseline["id"])).fetchone()
        statuses={x["status"]:x["n"] for x in db.execute("SELECT status,COUNT(*) n FROM execution_items WHERE project_id=? GROUP BY status",(project_id,)).fetchall()}
        recon={x["reconciliation_status"]:x["n"] for x in db.execute("SELECT reconciliation_status,COUNT(*) n FROM execution_items WHERE project_id=? GROUP BY reconciliation_status",(project_id,)).fetchall()}
        drift={x["status"]:x["n"] for x in db.execute("SELECT status,COUNT(*) n FROM execution_drift_records WHERE project_id=? GROUP BY status",(project_id,)).fetchall()}
        binding=db.execute("SELECT status FROM execution_bindings WHERE project_id=? AND target_type='PM_AGAIN'",(project_id,)).fetchone()
        latest_ai=db.execute("SELECT status,failure_code,provider,model,completed_at FROM materialization_ai_runs WHERE project_id=? ORDER BY started_at DESC LIMIT 1",(project_id,)).fetchone()
        external_rows=db.execute("SELECT last_verified_at FROM execution_items WHERE project_id=? AND target_type!='INTERNAL'",(project_id,)).fetchall()
    current=datetime.now(timezone.utc);freshness_stale=sum(1 for row in external_rows if not row["last_verified_at"] or (current-datetime.fromisoformat(row["last_verified_at"])).total_seconds()>settings.execution_freshness_seconds)
    blockers=[]
    if not plan:blockers.append("NO_MATERIALIZATION_PLAN")
    elif plan["status"]=="NEEDS_REVIEW":blockers.append("MATERIALIZATION_REVIEW_REQUIRED")
    elif plan["status"]=="AUTHORIZED":blockers.append("MATERIALIZATION_NOT_RUN")
    if recon.get("UNCONFIRMED",0):blockers.append("UNCONFIRMED_EXECUTION")
    if freshness_stale:blockers.append("TARGET_DATA_STALE")
    if recon.get("MISMATCH",0) or recon.get("ERROR",0):blockers.append("EXECUTION_RECONCILIATION_ATTENTION")
    if drift.get("OPEN",0):blockers.append("EXECUTION_DRIFT_OPEN")
    if latest_ai and latest_ai["status"]=="FAILED":blockers.append("MATERIALIZATION_AI_FAILURE")
    attention=[]
    for item in blockers:attention.append({"type":item,"message":item.replace('_',' ').title(),"severity":"HIGH" if item in {"UNCONFIRMED_EXECUTION","EXECUTION_DRIFT_OPEN"} else "MEDIUM"})
    next_action=("Generate execution materialization plan" if not plan else ("Review execution routing" if plan["status"]=="NEEDS_REVIEW" else ("Materialize authorized execution" if plan["status"]=="AUTHORIZED" else ("Reconcile unconfirmed work" if recon.get("UNCONFIRMED",0) or freshness_stale else ("Resolve execution drift" if drift.get("OPEN",0) or recon.get("MISMATCH",0) or recon.get("ERROR",0) else "Prepare QA scope")))))
    reconciliation={key.lower():recon.get(key,0) for key in ["CONFIRMED","MISMATCH","STALE","UNCONFIRMED","ERROR"]};reconciliation["stale"]=max(reconciliation["stale"],freshness_stale)
    return {"execution_materialization_status":plan["status"] if plan else "NOT_PLANNED","execution_materialization_progress":{"materialized":materialized,"total":total,"unmaterialized":max(total-materialized,0)},"execution_binding_status":binding["status"] if binding else "UNBOUND","execution_health":"HEALTHY" if not blockers and materialized==total else ("ATTENTION" if plan else "BLOCKED"),"execution_blockers":blockers,"execution_status":{key.lower():statuses.get(key,0) for key in ["NOT_STARTED","IN_PROGRESS","BLOCKED","COMPLETED","CANCELLED"]},"execution_reconciliation":reconciliation,"execution_drift":{"open":drift.get("OPEN",0),"acknowledged":drift.get("ACKNOWLEDGED",0)},"execution_ai":dict(latest_ai) if latest_ai else {"status":"NOT_RUN","failure_code":None},"execution_freshness":{"threshold_seconds":settings.execution_freshness_seconds,"stale_item_count":freshness_stale},"execution_attention":attention,"execution_next_action":next_action,"delivery_baseline_id":baseline["id"],"delivery_baseline_version":baseline["version"]}


@router.get("/truth")
def execution_truth(project_id: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id);return execution_truth_projection(project_id)


@router.post("/bindings/pm-again",status_code=201)
def create_pm_binding(project_id: str,body: BindingIn,actor: Actor=Depends(current_actor)):
    if actor.actor_type != "HUMAN": raise HTTPException(403,"Only a human project owner may create an execution binding")
    require_project(actor,project_id,owner=True)
    with transaction() as db:
        existing=db.execute("SELECT id FROM execution_bindings WHERE project_id=? AND target_type='PM_AGAIN'",(project_id,)).fetchone()
        if existing:raise HTTPException(409,"PM Again binding already exists")
        binding_id=uid("bind");stamp=now();db.execute("INSERT INTO execution_bindings (id,project_id,target_type,external_project_id,status,capabilities_json,last_verified_at,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(binding_id,project_id,"PM_AGAIN",body.external_project_id,"UNBOUND",dumps(CAPABILITIES["PM_AGAIN"].as_dict()),None,actor.id,stamp,stamp));audit(db,project_id,actor.id,"HUMAN","EXECUTION_BINDING_CREATED","EXECUTION_BINDING",binding_id)
    return {"id":binding_id,"target_type":"PM_AGAIN","status":"UNBOUND","external_project_id":body.external_project_id}


@router.post("/bindings/{binding_id}:verify")
def verify_binding(project_id: str,binding_id: str,actor: Actor=Depends(current_actor)):
    require_project(actor,project_id,owner=True)
    with transaction() as db:
        row=db.execute("SELECT * FROM execution_bindings WHERE id=? AND project_id=?",(binding_id,project_id)).fetchone()
        if not row:raise HTTPException(404,"Execution binding not found")
        try:
            adapter=adapter_for_target(row["target_type"])
            verifier=getattr(adapter,"verify_project",None)
            if not verifier: raise TargetUnavailable("Target cannot verify projects")
            verifier(row["external_project_id"]);status="READY"
        except ExecutionTargetError:status="ERROR"
        db.execute("UPDATE execution_bindings SET status=?,last_verified_at=?,updated_at=? WHERE id=?",(status,now(),now(),binding_id));audit(db,project_id,actor.id,"HUMAN","EXECUTION_BINDING_VERIFIED","EXECUTION_BINDING",binding_id,result="SUCCESS" if status=="READY" else "FAILED",detail={"status":status})
    return {"id":binding_id,"status":status}
