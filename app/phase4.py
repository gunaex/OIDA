from __future__ import annotations

import hashlib
import json
from typing import Literal, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from .ai import AIError, AIInvalidOutput, AcceptanceFoundationInput, QAFoundationInput, adapter_for
from .auth import Actor, current_actor, require_project
from .db import connect, now, transaction
from .phase2 import audit, dumps, idem_get, idem_put, require_key, uid
from .phase3 import execution_truth_projection, latest_delivery_baseline
from .validation_targets import CAPABILITIES, ValidationCreateRequest, ValidationTargetError, ValidationTargetUnavailable, adapter_for_validation_target


router=APIRouter(prefix="/api/projects/{project_id}",tags=["phase4"])


class GenerateIn(BaseModel):instruction:str=Field(default="",max_length=2000)
class ManualScopeIn(BaseModel):summary:str=Field(default="Human-prepared QA scope.",min_length=10,max_length=3000)
class ValidationPatch(BaseModel):
    area:Optional[str]=Field(default=None,min_length=3,max_length=80);title:Optional[str]=Field(default=None,min_length=8,max_length=180)
    objective:Optional[str]=Field(default=None,min_length=20,max_length=2000);preconditions:Optional[list[str]]=Field(default=None,max_length=15)
    validation_method:Optional[str]=Field(default=None,min_length=20,max_length=2500);expected_result:Optional[str]=Field(default=None,min_length=15,max_length=2000)
    validation_type:Optional[Literal["FUNCTIONAL","INTEGRATION","SECURITY","DATA","PERFORMANCE","OPERATIONAL","ACCEPTANCE","OTHER"]]=None
    execution_mode:Optional[Literal["MANUAL","AUTOMATED","HYBRID","EXTERNAL"]]=None;target_type:Optional[Literal["INTERNAL","QA_AGAIN","MANUAL_EXTERNAL"]]=None
    binding_id:Optional[str]=None;external_reference:Optional[str]=Field(default=None,max_length=500)
    requirement_revision_ids:Optional[list[str]]=Field(default=None,min_length=1,max_length=20);acceptance_criteria_refs:Optional[list[dict]]=Field(default=None,min_length=1,max_length=30)
    delivery_item_ids:Optional[list[str]]=Field(default=None,max_length=30);execution_item_ids:Optional[list[str]]=Field(default=None,max_length=30)
    required_evidence_types:Optional[list[Literal["SCREENSHOT","LOG","REPORT","DOCUMENT","API_RESPONSE","RECORD","APPROVAL","LINK","OTHER"]]]=Field(default=None,min_length=1,max_length=8)
    priority:Optional[Literal["HIGH","MEDIUM","LOW"]]=None;severity_if_failed:Optional[Literal["LOW","MEDIUM","HIGH","CRITICAL"]]=None
    owner_role:Optional[str]=Field(default=None,min_length=2,max_length=120);required_for_acceptance:Optional[bool]=None
class ManualValidationIn(ValidationPatch):
    area:str=Field(min_length=3,max_length=80);title:str=Field(min_length=8,max_length=180);objective:str=Field(min_length=20,max_length=2000)
    validation_method:str=Field(min_length=20,max_length=2500);expected_result:str=Field(min_length=15,max_length=2000)
    validation_type:Literal["FUNCTIONAL","INTEGRATION","SECURITY","DATA","PERFORMANCE","OPERATIONAL","ACCEPTANCE","OTHER"]="FUNCTIONAL"
    execution_mode:Literal["MANUAL","AUTOMATED","HYBRID","EXTERNAL"]="MANUAL";target_type:Literal["INTERNAL","QA_AGAIN","MANUAL_EXTERNAL"]="INTERNAL"
    requirement_revision_ids:list[str]=Field(min_length=1,max_length=20);acceptance_criteria_refs:list[dict]=Field(min_length=1,max_length=30)
    required_evidence_types:list[Literal["SCREENSHOT","LOG","REPORT","DOCUMENT","API_RESPONSE","RECORD","APPROVAL","LINK","OTHER"]]=Field(default_factory=lambda:["REPORT"],min_length=1,max_length=8)
    priority:Literal["HIGH","MEDIUM","LOW"]="MEDIUM";severity_if_failed:Literal["LOW","MEDIUM","HIGH","CRITICAL"]="HIGH"
    owner_role:str=Field(default="QA Lead",min_length=2,max_length=120);required_for_acceptance:bool=True
class ResultIn(BaseModel):
    result:Literal["PASS","FAIL","BLOCKED","SKIPPED"];observed_result:str=Field(min_length=5,max_length=4000);notes:str=Field(default="",max_length=3000)
    source_type:Literal["MANUAL","AUTOMATED_INTERNAL","EXTERNAL"]="MANUAL";source_reference:Optional[str]=Field(default=None,max_length=500)
class EvidenceIn(BaseModel):
    classification:Literal["TEST","INTERNAL","CUSTOMER"];evidence_type:Literal["SCREENSHOT","LOG","REPORT","DOCUMENT","API_RESPONSE","RECORD","APPROVAL","LINK","OTHER"]
    validation_item_id:Optional[str]=None;validation_result_id:Optional[str]=None;execution_item_id:Optional[str]=None
    requirement_revision_ids:list[str]=Field(default_factory=list,max_length=30);title:str=Field(min_length=3,max_length=180);description:str=Field(min_length=5,max_length=2000)
    content_text:Optional[str]=Field(default=None,min_length=1,max_length=100000);external_reference:Optional[str]=Field(default=None,max_length=1000)
class EvidenceStatusIn(BaseModel):status:Literal["INVALID","STALE","SUPERSEDED"];reason:str=Field(min_length=3,max_length=1000)
class FinalAcceptanceIn(BaseModel):acceptance_package_id:str;acceptance_comment:str=Field(min_length=10,max_length=3000)
class ManualAcceptancePackageIn(BaseModel):
    executive_summary:str=Field(min_length=20,max_length=4000)
    recommendation_basis:str=Field(min_length=20,max_length=4000)
    residual_risks:list[str]=Field(default_factory=list,max_length=30)
class ExceptionIn(BaseModel):validation_item_id:str;validation_result_id:str;reason:str=Field(min_length=10,max_length=2000);risk:str=Field(min_length=10,max_length=2000)
class ExceptionDecisionIn(BaseModel):decision:Literal["APPROVED","REJECTED"]
class BindingIn(BaseModel):external_project_id:str=Field(min_length=1,max_length=300)


def sha(value)->str:return hashlib.sha256(dumps(value).encode()).hexdigest()
def next_code(db,project_id,column,prefix)->str:
    value=db.execute(f"SELECT {column} FROM projects WHERE id=?",(project_id,)).fetchone()[0];db.execute(f"UPDATE projects SET {column}={column}+1,updated_at=? WHERE id=?",(now(),project_id));return f"{prefix}-{value:03d}"
def human_owner(actor,project_id):
    if actor.actor_type!="HUMAN":raise HTTPException(403,"Only a human project owner may perform this authority action")
    return require_project(actor,project_id,owner=True)


def requirement_source(db,baseline):
    rows=db.execute("SELECT r.id requirement_id,r.requirement_code,rr.id requirement_revision_id,rr.title,rr.statement,rr.priority,rr.acceptance_criteria_json FROM requirement_baseline_members m JOIN requirement_revisions rr ON rr.id=m.requirement_revision_id JOIN requirements r ON r.id=rr.requirement_id WHERE m.baseline_id=? ORDER BY r.requirement_code",(baseline["requirement_baseline_id"],)).fetchall()
    return [{**dict(x),"acceptance_criteria":json.loads(x["acceptance_criteria_json"])} for x in rows]


def execution_snapshot(db,project_id):
    rows=db.execute("SELECT id,execution_code,source_delivery_item_id,target_type,status,reconciliation_status,current_revision,updated_at FROM execution_items WHERE project_id=? ORDER BY id",(project_id,)).fetchall()
    return sha([dict(x) for x in rows]),[dict(x) for x in rows]


def qa_foundation(db,project_id):
    baseline=latest_delivery_baseline(db,project_id)
    if not baseline:raise HTTPException(409,"QA_READINESS_BLOCKED_UPSTREAM_NOT_READY")
    requirements=requirement_source(db,baseline);snap,execution=execution_snapshot(db,project_id)
    if not execution:raise HTTPException(409,"QA_READINESS_BLOCKED_UPSTREAM_NOT_READY")
    project=db.execute("SELECT name,objective FROM projects WHERE id=?",(project_id,)).fetchone()
    delivery=[]
    for row in db.execute("SELECT * FROM delivery_plan_revision_items WHERE plan_revision_id=? ORDER BY local_ref",(baseline["delivery_plan_revision_id"],)).fetchall():
        value=dict(row);value["requirement_revision_ids"]=json.loads(value.pop("requirement_revision_ids_json"));value["acceptance_criteria"]=json.loads(value.pop("acceptance_criteria_json"));value["solution_component_refs"]=json.loads(value.pop("solution_component_refs_json"));delivery.append(value)
    drift=[dict(x) for x in db.execute("SELECT id,drift_type,severity,status,detail_json FROM execution_drift_records WHERE project_id=? AND status IN ('OPEN','ACKNOWLEDGED')",(project_id,)).fetchall()]
    latest_recon=db.execute("SELECT id FROM execution_reconciliation_runs WHERE project_id=? ORDER BY started_at DESC LIMIT 1",(project_id,)).fetchone()
    bindings={x["target_type"]:dict(x) for x in db.execute("SELECT * FROM qa_bindings WHERE project_id=?",(project_id,)).fetchall()};capabilities=[]
    for target,capability in CAPABILITIES.items():
        value=capability.as_dict();value["binding_state"]="READY" if target=="INTERNAL" else ("MANUAL" if target=="MANUAL_EXTERNAL" else bindings.get(target,{}).get("status","UNBOUND"));capabilities.append(value)
    truth=execution_truth_projection(project_id)
    requirement_baseline_version=db.execute(
        "SELECT version FROM requirement_baselines WHERE id=? AND project_id=?",
        (baseline["requirement_baseline_id"],project_id),
    ).fetchone()[0]
    foundation=QAFoundationInput(project["name"],project["objective"],baseline["requirement_baseline_id"],requirement_baseline_version,baseline["id"],baseline["version"],baseline["solution_revision_id"],baseline["delivery_plan_revision_id"],snap,requirements,delivery,execution,truth,drift,capabilities)
    return foundation,dict(baseline),latest_recon["id"] if latest_recon else None


def validate_refs(db,project_id,baseline,requirements,criteria,delivery_ids,execution_ids):
    req_allowed={x["requirement_revision_id"]:x for x in requirement_source(db,baseline)}
    if not set(requirements).issubset(req_allowed):raise HTTPException(422,"Requirement reference is outside the frozen Requirement Baseline")
    for ref in criteria:
        rid=ref.get("requirement_revision_id");index=ref.get("criterion_index")
        if rid not in req_allowed or not isinstance(index,int) or index<0 or index>=len(req_allowed[rid]["acceptance_criteria"]):raise HTTPException(422,"Acceptance criterion reference is outside the frozen Requirement Baseline")
        if rid not in requirements:raise HTTPException(422,"Acceptance criterion must belong to a linked requirement revision")
    if delivery_ids:
        marks=','.join('?' for _ in delivery_ids);found=db.execute(f"SELECT COUNT(*) FROM delivery_plan_revision_items WHERE plan_revision_id=? AND id IN ({marks})",(baseline["delivery_plan_revision_id"],*delivery_ids)).fetchone()[0]
        if found!=len(set(delivery_ids)):raise HTTPException(422,"Delivery reference is outside the frozen Delivery Baseline")
    if execution_ids:
        marks=','.join('?' for _ in execution_ids);found=db.execute(f"SELECT COUNT(*) FROM execution_items WHERE project_id=? AND id IN ({marks})",(project_id,*execution_ids)).fetchone()[0]
        if found!=len(set(execution_ids)):raise HTTPException(422,"Execution reference is outside project Execution Truth")


def item_content(db,item):
    value=dict(item);value["preconditions"]=json.loads(value.pop("preconditions_json"));value["required_evidence_types"]=json.loads(value.pop("required_evidence_types_json"));value["required_for_acceptance"]=bool(value["required_for_acceptance"])
    value["requirement_revision_ids"]=[x[0] for x in db.execute("SELECT requirement_revision_id FROM validation_item_requirements WHERE validation_item_id=? GROUP BY requirement_revision_id",(item["id"],)).fetchall()]
    value["acceptance_criteria_refs"]=[{"requirement_revision_id":x[0],"criterion_index":x[1]} for x in db.execute("SELECT requirement_revision_id,criterion_index FROM validation_item_requirements WHERE validation_item_id=? AND criterion_index>=0",(item["id"],)).fetchall()]
    value["delivery_item_ids"]=[x[0] for x in db.execute("SELECT delivery_item_id FROM validation_item_delivery_links WHERE validation_item_id=?",(item["id"],)).fetchall()]
    value["execution_item_ids"]=[x[0] for x in db.execute("SELECT execution_item_id FROM validation_item_execution_links WHERE validation_item_id=?",(item["id"],)).fetchall()]
    latest=db.execute("SELECT * FROM validation_results WHERE validation_item_id=? ORDER BY result_no DESC LIMIT 1",(item["id"],)).fetchone();value["latest_result"]=dict(latest) if latest else None
    value["result_count"]=db.execute("SELECT COUNT(*) FROM validation_results WHERE validation_item_id=?",(item["id"],)).fetchone()[0]
    value["valid_evidence_count"]=db.execute("SELECT COUNT(*) FROM evidence_records WHERE validation_item_id=? AND status='VALID'",(item["id"],)).fetchone()[0]
    return value


def replace_links(db,item_id,requirements,criteria,delivery_ids,execution_ids):
    for table in ["validation_item_requirements","validation_item_delivery_links","validation_item_execution_links"]:db.execute(f"DELETE FROM {table} WHERE validation_item_id=?",(item_id,))
    criterion_req={x["requirement_revision_id"] for x in criteria}
    for rid in requirements:
        if rid not in criterion_req:db.execute("INSERT INTO validation_item_requirements VALUES (?,?,?)",(item_id,rid,-1))
    for ref in criteria:db.execute("INSERT INTO validation_item_requirements VALUES (?,?,?)",(item_id,ref["requirement_revision_id"],ref["criterion_index"]))
    for did in delivery_ids:db.execute("INSERT INTO validation_item_delivery_links VALUES (?,?)",(item_id,did))
    for eid in execution_ids:db.execute("INSERT INTO validation_item_execution_links VALUES (?,?)",(item_id,eid))


def insert_item(db,project_id,scope_id,data,actor_id,origin):
    code=next_code(db,project_id,"next_validation_number","VAL");item_id=uid("val");stamp=now();binding=data.get("binding_id");external=data.get("external_reference")
    status="BLOCKED" if data["target_type"]=="QA_AGAIN" and not binding else ("BLOCKED" if data["target_type"]=="MANUAL_EXTERNAL" and not external else "DRAFT")
    db.execute("INSERT INTO validation_items (id,project_id,qa_scope_id,validation_code,area,title,objective,preconditions_json,validation_method,expected_result,validation_type,execution_mode,target_type,binding_id,external_id,external_url,required_evidence_types_json,priority,severity_if_failed,owner_role,owner_id,required_for_acceptance,candidate_status,materialization_status,execution_status,origin,current_revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (item_id,project_id,scope_id,code,data["area"],data["title"],data["objective"],dumps(data.get("preconditions") or []),data["validation_method"],data["expected_result"],data["validation_type"],data["execution_mode"],data["target_type"],binding,external,None,dumps(data["required_evidence_types"]),data["priority"],data["severity_if_failed"],data["owner_role"],None,int(data["required_for_acceptance"]),"ACTIVE",status,"NOT_STARTED",origin,1,stamp,stamp))
    replace_links(db,item_id,data["requirement_revision_ids"],data["acceptance_criteria_refs"],data.get("delivery_item_ids") or [],data.get("execution_item_ids") or [])
    content=item_content(db,db.execute("SELECT * FROM validation_items WHERE id=?",(item_id,)).fetchone());db.execute("INSERT INTO validation_item_revisions VALUES (?,?,?,?,?,?,?,?)",(uid("vrev"),item_id,project_id,1,dumps(content),actor_id,"AI" if origin=="AI" else "HUMAN",stamp))
    return item_id,code


def scope_view(db,row):
    value=dict(row);value["risks"]=json.loads(value.pop("risks_json"));value["gaps"]=json.loads(value.pop("gaps_json"));snap,_=execution_snapshot(db,row["project_id"])
    value["stale"]=row["execution_snapshot_hash"]!=snap or row["delivery_baseline_id"]!=(latest_delivery_baseline(db,row["project_id"])["id"] if latest_delivery_baseline(db,row["project_id"]) else None)
    value["items"]=[item_content(db,x) for x in db.execute("SELECT * FROM validation_items WHERE qa_scope_id=? ORDER BY validation_code",(row["id"],)).fetchall()]
    return value


def snapshot_scope(db,scope,editor,actor_type):
    revision=scope["current_revision"]+1;items=[item_content(db,x) for x in db.execute("SELECT * FROM validation_items WHERE qa_scope_id=? ORDER BY validation_code",(scope["id"],)).fetchall()];stamp=now()
    db.execute("INSERT INTO qa_scope_revisions VALUES (?,?,?,?,?,?,?,?)",(uid("qrev"),scope["id"],scope["project_id"],revision,dumps({"summary":scope["summary"],"risks":json.loads(scope["risks_json"]),"gaps":json.loads(scope["gaps_json"]),"items":items}),editor,actor_type,stamp));db.execute("UPDATE qa_scopes SET current_revision=?,status=CASE WHEN status='AI_CANDIDATE' THEN 'HUMAN_REVIEWED' ELSE status END,updated_at=? WHERE id=?",(revision,stamp,scope["id"]));return revision


def editable_scope(db,project_id,scope_id):
    row=db.execute("SELECT * FROM qa_scopes WHERE id=? AND project_id=?",(scope_id,project_id)).fetchone()
    if not row:raise HTTPException(404,"QA Scope not found")
    if row["status"] not in {"AI_CANDIDATE","HUMAN_REVIEWED"}:raise HTTPException(409,"QA Scope is no longer editable")
    return row


@router.get("/qa/readiness")
def qa_readiness(project_id:str,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:
        try:foundation,baseline,recon=qa_foundation(db,project_id)
        except HTTPException:return {"ready":False,"status":"BLOCKED_UPSTREAM_NOT_READY","blocking_items":["QA_READINESS_BLOCKED_UPSTREAM_NOT_READY"]}
    return {"ready":True,"status":"READY","requirement_baseline_id":foundation.requirement_baseline_id,"delivery_baseline_id":foundation.delivery_baseline_id,"execution_snapshot_hash":foundation.execution_snapshot_hash,"execution_reconciliation_run_id":recon,"blocking_items":[]}


def generate_scope_sync(project_id:str,body:GenerateIn,idempotency_key:Optional[str],actor:Actor):
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"GENERATE_QA_SCOPE",key)
        if previous:return previous
        foundation,baseline,recon=qa_foundation(db,project_id);adapter=adapter_for();run_id=uid("qarun");stamp=now()
        db.execute("INSERT INTO qa_ai_runs (id,project_id,run_type,requested_by,provider,model,reasoning_effort,prompt_version,instruction,requirement_baseline_id,delivery_baseline_id,status,started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(run_id,project_id,"QA_SCOPE",actor.id,adapter.provider,adapter.model,getattr(adapter,"reasoning_effort",None),"qa-scope/v1",body.instruction,foundation.requirement_baseline_id,foundation.delivery_baseline_id,"RUNNING",stamp));audit(db,project_id,f"ai:{run_id}","AI","QA_SCOPE_AI_RUN_STARTED","QA_AI_RUN",run_id)
        try:
            output=adapter.generate_qa_scope(foundation,body.instruction);valid_req={x["requirement_revision_id"]:x for x in foundation.requirements};valid_delivery={x["id"] for x in foundation.delivery_items};valid_execution={x["id"] for x in foundation.execution_items}
            covered=set()
            for item in output.items:
                covered.update(item.requirement_revision_ids)
                if not set(item.requirement_revision_ids).issubset(valid_req) or not set(item.delivery_item_ids).issubset(valid_delivery) or not set(item.execution_item_ids).issubset(valid_execution):raise AIInvalidOutput("QA Scope contains an unknown frozen reference")
                for ref in item.acceptance_criteria_refs:
                    if ref.requirement_revision_id not in valid_req or ref.criterion_index>=len(valid_req[ref.requirement_revision_id]["acceptance_criteria"]):raise AIInvalidOutput("QA Scope contains an unknown acceptance criterion")
            if covered!=set(valid_req):raise AIInvalidOutput("QA Scope must cover every frozen requirement revision")
        except AIError as exc:
            metrics=getattr(adapter,"last_metrics",None);values=metrics.as_dict() if metrics else {};db.execute("UPDATE qa_ai_runs SET status='FAILED',failure_code=?,input_tokens=?,cache_hit_tokens=?,output_tokens=?,total_tokens=?,latency_ms=?,provider_request_id=?,completed_at=? WHERE id=?",(exc.code,values.get("input_tokens"),values.get("cache_hit_tokens"),values.get("output_tokens"),values.get("total_tokens"),values.get("latency_ms"),values.get("provider_request_id"),now(),run_id));result={"ai_run_id":run_id,"status":"FAILED","failure_code":exc.code,"message":str(exc),"provider":adapter.provider,"telemetry":values};audit(db,project_id,f"ai:{run_id}","AI","QA_SCOPE_AI_RUN_FAILED","QA_AI_RUN",run_id,"FAILED",{"failure_code":exc.code});idem_put(db,project_id,actor.id,"GENERATE_QA_SCOPE",key,result);return result
        code=next_code(db,project_id,"next_qa_number","QA");scope_id=uid("qas");db.execute("INSERT INTO qa_scopes (id,project_id,qa_code,requirement_baseline_id,delivery_baseline_id,delivery_plan_revision_id,execution_snapshot_hash,execution_reconciliation_run_id,ai_run_id,status,current_revision,summary,risks_json,gaps_json,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(scope_id,project_id,code,foundation.requirement_baseline_id,foundation.delivery_baseline_id,foundation.delivery_plan_revision_id,foundation.execution_snapshot_hash,recon,run_id,"AI_CANDIDATE",1,output.summary,dumps(output.risks),dumps(output.gaps),f"ai:{run_id}",stamp,stamp))
        for item in output.items:insert_item(db,project_id,scope_id,item.model_dump(),f"ai:{run_id}","AI")
        content={"summary":output.summary,"risks":output.risks,"gaps":output.gaps,"items":[item_content(db,x) for x in db.execute("SELECT * FROM validation_items WHERE qa_scope_id=?",(scope_id,)).fetchall()]};db.execute("INSERT INTO qa_scope_revisions VALUES (?,?,?,?,?,?,?,?)",(uid("qrev"),scope_id,project_id,1,dumps(content),f"ai:{run_id}","AI",stamp))
        metrics=getattr(adapter,"last_metrics",None);values=metrics.as_dict() if metrics else {};db.execute("UPDATE qa_ai_runs SET qa_scope_id=?,status='SUCCEEDED',findings_json=?,input_tokens=?,cache_hit_tokens=?,output_tokens=?,total_tokens=?,latency_ms=?,provider_request_id=?,completed_at=? WHERE id=?",(scope_id,dumps(output.findings),values.get("input_tokens"),values.get("cache_hit_tokens"),values.get("output_tokens"),values.get("total_tokens"),values.get("latency_ms"),values.get("provider_request_id"),now(),run_id));result={"ai_run_id":run_id,"scope_id":scope_id,"qa_code":code,"status":"SUCCEEDED","item_count":len(output.items),"provider":adapter.provider,"model":adapter.model,"telemetry":values};audit(db,project_id,f"ai:{run_id}","AI","QA_SCOPE_AI_RUN_COMPLETED","QA_SCOPE",scope_id,detail={"item_count":len(output.items)});idem_put(db,project_id,actor.id,"GENERATE_QA_SCOPE",key,result);return result


@router.post("/qa-scopes:generate", status_code=202)
def generate_scope(project_id:str,body:GenerateIn,idempotency_key:Optional[str]=Header(None),actor:Actor=Depends(current_actor)):
    from .jobs import enqueue
    require_project(actor,project_id);key=require_key(idempotency_key)
    with connect() as db: qa_foundation(db,project_id)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"QUEUE_QA_SCOPE",key)
        if previous:return previous
        result=enqueue(db,project_id,actor,"QA_SCOPE",body.model_dump());idem_put(db,project_id,actor.id,"QUEUE_QA_SCOPE",key,result)
    return result


@router.post("/qa-scopes",status_code=201)
def manual_scope(project_id:str,body:ManualScopeIn,idempotency_key:Optional[str]=Header(None),actor:Actor=Depends(current_actor)):
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"CREATE_MANUAL_QA_SCOPE",key)
        if previous:return previous
        foundation,baseline,recon=qa_foundation(db,project_id);scope_id=uid("qas");code=next_code(db,project_id,"next_qa_number","QA");stamp=now();db.execute("INSERT INTO qa_scopes (id,project_id,qa_code,requirement_baseline_id,delivery_baseline_id,delivery_plan_revision_id,execution_snapshot_hash,execution_reconciliation_run_id,status,current_revision,summary,risks_json,gaps_json,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(scope_id,project_id,code,foundation.requirement_baseline_id,foundation.delivery_baseline_id,foundation.delivery_plan_revision_id,foundation.execution_snapshot_hash,recon,"HUMAN_REVIEWED",1,body.summary,"[]","[]",actor.id,stamp,stamp));db.execute("INSERT INTO qa_scope_revisions VALUES (?,?,?,?,?,?,?,?)",(uid("qrev"),scope_id,project_id,1,dumps({"summary":body.summary,"risks":[],"gaps":[],"items":[]}),actor.id,"HUMAN",stamp));result={"scope_id":scope_id,"qa_code":code,"status":"HUMAN_REVIEWED","origin":"HUMAN"};audit(db,project_id,actor.id,"HUMAN","QA_SCOPE_CREATED","QA_SCOPE",scope_id);idem_put(db,project_id,actor.id,"CREATE_MANUAL_QA_SCOPE",key,result);return result


@router.get("/qa-scopes")
def list_scopes(project_id:str,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:return [scope_view(db,x) for x in db.execute("SELECT * FROM qa_scopes WHERE project_id=? ORDER BY created_at DESC",(project_id,)).fetchall()]


@router.patch("/qa-scopes/{scope_id}/items/{item_id}")
def patch_item(project_id:str,scope_id:str,item_id:str,body:ValidationPatch,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        scope=editable_scope(db,project_id,scope_id);item=db.execute("SELECT * FROM validation_items WHERE id=? AND qa_scope_id=? AND project_id=?",(item_id,scope_id,project_id)).fetchone()
        if not item:raise HTTPException(404,"Validation item not found")
        current=item_content(db,item);changes=body.model_dump(exclude_unset=True);merged={**current,**changes};baseline=latest_delivery_baseline(db,project_id);validate_refs(db,project_id,baseline,merged["requirement_revision_ids"],merged["acceptance_criteria_refs"],merged.get("delivery_item_ids",[]),merged.get("execution_item_ids",[]))
        target=merged["target_type"];binding=merged.get("binding_id");external=merged.get("external_reference")
        if binding:
            found=db.execute("SELECT 1 FROM qa_bindings WHERE id=? AND project_id=? AND target_type=?",(binding,project_id,target)).fetchone()
            if not found:raise HTTPException(422,"QA binding is unavailable for this project")
        material="BLOCKED" if target=="QA_AGAIN" and not binding else ("BLOCKED" if target=="MANUAL_EXTERNAL" and not external else "DRAFT")
        revision=item["current_revision"]+1;stamp=now();db.execute("UPDATE validation_items SET area=?,title=?,objective=?,preconditions_json=?,validation_method=?,expected_result=?,validation_type=?,execution_mode=?,target_type=?,binding_id=?,external_id=?,required_evidence_types_json=?,priority=?,severity_if_failed=?,owner_role=?,required_for_acceptance=?,materialization_status=?,current_revision=?,updated_at=? WHERE id=?",(merged["area"],merged["title"],merged["objective"],dumps(merged["preconditions"]),merged["validation_method"],merged["expected_result"],merged["validation_type"],merged["execution_mode"],target,binding,external,dumps(merged["required_evidence_types"]),merged["priority"],merged["severity_if_failed"],merged["owner_role"],int(merged["required_for_acceptance"]),material,revision,stamp,item_id));replace_links(db,item_id,merged["requirement_revision_ids"],merged["acceptance_criteria_refs"],merged.get("delivery_item_ids",[]),merged.get("execution_item_ids",[]));updated=item_content(db,db.execute("SELECT * FROM validation_items WHERE id=?",(item_id,)).fetchone());db.execute("INSERT INTO validation_item_revisions VALUES (?,?,?,?,?,?,?,?)",(uid("vrev"),item_id,project_id,revision,dumps(updated),actor.id,"HUMAN",stamp));scope_revision=snapshot_scope(db,scope,actor.id,"HUMAN");audit(db,project_id,actor.id,"HUMAN","VALIDATION_ITEM_EDITED","VALIDATION_ITEM",item_id,detail={"revision":revision,"qa_scope_revision":scope_revision});return {"id":item_id,"current_revision":revision,"qa_scope_revision":scope_revision,"human_override":True,"materialization_status":material}


@router.post("/qa-scopes/{scope_id}/items",status_code=201)
def add_item(project_id:str,scope_id:str,body:ManualValidationIn,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        scope=editable_scope(db,project_id,scope_id);data=body.model_dump();baseline=latest_delivery_baseline(db,project_id);validate_refs(db,project_id,baseline,data["requirement_revision_ids"],data["acceptance_criteria_refs"],data.get("delivery_item_ids") or [],data.get("execution_item_ids") or []);item_id,code=insert_item(db,project_id,scope_id,data,actor.id,"HUMAN");revision=snapshot_scope(db,scope,actor.id,"HUMAN");audit(db,project_id,actor.id,"HUMAN","VALIDATION_ITEM_CREATED","VALIDATION_ITEM",item_id);return {"id":item_id,"validation_code":code,"qa_scope_revision":revision,"origin":"HUMAN"}


@router.post("/qa-scopes/{scope_id}/items/{item_id}:reject")
def reject_item(project_id:str,scope_id:str,item_id:str,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        scope=editable_scope(db,project_id,scope_id);item=db.execute("SELECT id FROM validation_items WHERE id=? AND qa_scope_id=? AND project_id=?",(item_id,scope_id,project_id)).fetchone()
        if not item:raise HTTPException(404,"Validation item not found")
        db.execute("UPDATE validation_items SET candidate_status='REJECTED',updated_at=? WHERE id=?",(now(),item_id));revision=snapshot_scope(db,scope,actor.id,"HUMAN");audit(db,project_id,actor.id,"HUMAN","VALIDATION_ITEM_REJECTED","VALIDATION_ITEM",item_id);return {"id":item_id,"candidate_status":"REJECTED","qa_scope_revision":revision}


@router.post("/qa-scopes/{scope_id}:commit")
def commit_scope(project_id:str,scope_id:str,idempotency_key:Optional[str]=Header(None),actor:Actor=Depends(current_actor)):
    human_owner(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"COMMIT_QA_SCOPE",key)
        if previous:return previous
        scope=editable_scope(db,project_id,scope_id);snap,_=execution_snapshot(db,project_id)
        if snap!=scope["execution_snapshot_hash"]:raise HTTPException(409,"QA Scope is stale against current Execution Truth")
        sources=requirement_source(db,latest_delivery_baseline(db,project_id));required={x["requirement_revision_id"] for x in sources};covered={x[0] for x in db.execute("SELECT DISTINCT l.requirement_revision_id FROM validation_item_requirements l JOIN validation_items v ON v.id=l.validation_item_id WHERE v.qa_scope_id=? AND v.candidate_status='ACTIVE'",(scope_id,)).fetchall()}
        if covered!=required:raise HTTPException(409,"QA Scope does not cover every frozen requirement")
        required_criteria={(x["requirement_revision_id"],index) for x in sources for index,_ in enumerate(x["acceptance_criteria"])}
        covered_criteria={(x[0],x[1]) for x in db.execute("SELECT DISTINCT l.requirement_revision_id,l.criterion_index FROM validation_item_requirements l JOIN validation_items v ON v.id=l.validation_item_id WHERE v.qa_scope_id=? AND v.candidate_status='ACTIVE' AND l.criterion_index>=0",(scope_id,)).fetchall()}
        if not required_criteria.issubset(covered_criteria):raise HTTPException(409,"QA Scope does not cover every frozen acceptance criterion")
        active=db.execute("SELECT COUNT(*) FROM validation_items WHERE qa_scope_id=? AND candidate_status='ACTIVE'",(scope_id,)).fetchone()[0]
        if not active:raise HTTPException(409,"QA Scope has no active validation items")
        stamp=now();db.execute("UPDATE qa_scopes SET status='COMMITTED',committed_by=?,committed_at=?,updated_at=? WHERE id=?",(actor.id,stamp,stamp,scope_id));confirmed=db.execute("SELECT status,current_revision,committed_by FROM qa_scopes WHERE id=? AND project_id=?",(scope_id,project_id)).fetchone()
        if not confirmed or confirmed["status"]!="COMMITTED" or confirmed["current_revision"]!=scope["current_revision"] or confirmed["committed_by"]!=actor.id:raise HTTPException(500,"QA Scope commit read-after-write reconciliation failed")
        result={"scope_id":scope_id,"status":"COMMITTED","revision":scope["current_revision"],"active_item_count":active,"committed_by":actor.id,"committed_at":stamp,"reconciliation":"CONFIRMED"};audit(db,project_id,actor.id,"HUMAN","QA_SCOPE_COMMITTED","QA_SCOPE",scope_id,detail=result);idem_put(db,project_id,actor.id,"COMMIT_QA_SCOPE",key,result);return result


@router.post("/qa-scopes/{scope_id}:materialize")
def materialize_scope(project_id:str,scope_id:str,idempotency_key:Optional[str]=Header(None),actor:Actor=Depends(current_actor)):
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"MATERIALIZE_QA_SCOPE",key)
        if previous:return previous
        scope=db.execute("SELECT * FROM qa_scopes WHERE id=? AND project_id=?",(scope_id,project_id)).fetchone()
        if not scope:raise HTTPException(404,"QA Scope not found")
        if scope["status"]!="COMMITTED":raise HTTPException(409,"Committed QA Scope required")
        results=[]
        for item in db.execute("SELECT * FROM validation_items WHERE qa_scope_id=? AND candidate_status='ACTIVE' ORDER BY validation_code",(scope_id,)).fetchall():
            if item["materialization_status"]=="BLOCKED":results.append({"item_id":item["id"],"status":"BLOCKED"});continue
            request=ValidationCreateRequest(item["id"],project_id,item["binding_id"],item["title"],item["objective"],item["expected_result"],item["owner_role"],f"{scope_id}:{item['id']}",item["external_id"])
            try:
                target=adapter_for_validation_target(item["target_type"]);created=target.create_validation_item(db,request);db.execute("UPDATE validation_items SET external_id=?,external_url=?,updated_at=? WHERE id=?",(created.external_id,created.external_url,now(),item["id"]));readback=target.get_validation_item(db,project_id,item["binding_id"],created.external_id)
                status="CONFIRMED" if readback else "UNCONFIRMED";db.execute("UPDATE validation_items SET materialization_status=?,updated_at=? WHERE id=?",(status,now(),item["id"]));audit(db,project_id,"system:qa-materialization","SYSTEM","VALIDATION_ITEM_MATERIALIZED" if readback else "VALIDATION_ITEM_UNCONFIRMED","VALIDATION_ITEM",item["id"],"SUCCESS" if readback else "UNCONFIRMED")
            except ValidationTargetError as exc:
                status="FAILED";db.execute("UPDATE validation_items SET materialization_status='FAILED',updated_at=? WHERE id=?",(now(),item["id"]));audit(db,project_id,"system:qa-materialization","SYSTEM","VALIDATION_ITEM_MATERIALIZATION_FAILED","VALIDATION_ITEM",item["id"],"FAILED",{"failure_code":exc.code})
            results.append({"item_id":item["id"],"status":status})
        counts={state:sum(x["status"]==state for x in results) for state in ["CONFIRMED","FAILED","UNCONFIRMED","BLOCKED"]};overall="CONFIRMED" if counts["CONFIRMED"]==len(results) else "PARTIAL";result={"scope_id":scope_id,"status":overall,"requested_count":len(results),**{f"{key.lower()}_count":value for key,value in counts.items()},"results":results};idem_put(db,project_id,actor.id,"MATERIALIZE_QA_SCOPE",key,result);return result


@router.get("/validation-items")
def list_validation(project_id:str,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:return [item_content(db,x) for x in db.execute("SELECT * FROM validation_items WHERE project_id=? ORDER BY validation_code",(project_id,)).fetchall()]


@router.post("/validation-items/{item_id}/results",status_code=201)
def record_result(project_id:str,item_id:str,body:ResultIn,idempotency_key:Optional[str]=Header(None),actor:Actor=Depends(current_actor)):
    if actor.actor_type!="HUMAN":raise HTTPException(403,"AI or system actors cannot record manual validation judgment")
    require_project(actor,project_id);key=require_key(idempotency_key)
    if body.source_type!="MANUAL":raise HTTPException(403,"Automated/external results require a trusted service ingestion boundary")
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"RECORD_VALIDATION_RESULT",key)
        if previous:return previous
        item=db.execute("SELECT * FROM validation_items WHERE id=? AND project_id=? AND candidate_status='ACTIVE'",(item_id,project_id)).fetchone()
        if not item:raise HTTPException(404,"Validation item not found")
        if item["materialization_status"]!="CONFIRMED":raise HTTPException(409,"Validation item is not materialized and confirmed")
        number=db.execute("SELECT COALESCE(MAX(result_no),0)+1 FROM validation_results WHERE validation_item_id=?",(item_id,)).fetchone()[0];result_id=uid("vres");stamp=now();db.execute("UPDATE validation_results SET status='SUPERSEDED' WHERE validation_item_id=? AND status='CURRENT'",(item_id,));db.execute("INSERT INTO validation_results (id,project_id,validation_item_id,result_no,result,observed_result,notes,source_type,source_reference,executed_by,actor_type,executed_at,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(result_id,project_id,item_id,number,body.result,body.observed_result,body.notes,body.source_type,body.source_reference,actor.id,"HUMAN",stamp,"CURRENT",stamp));db.execute("UPDATE validation_items SET execution_status=?,updated_at=? WHERE id=?",(body.result,stamp,item_id));result={"id":result_id,"validation_item_id":item_id,"result_no":number,"result":body.result,"status":"CURRENT"};audit(db,project_id,actor.id,"HUMAN","VALIDATION_RESULT_RECORDED","VALIDATION_RESULT",result_id,detail=result);idem_put(db,project_id,actor.id,"RECORD_VALIDATION_RESULT",key,result);return result


@router.get("/validation-items/{item_id}/results")
def result_history(project_id:str,item_id:str,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:
        if not db.execute("SELECT 1 FROM validation_items WHERE id=? AND project_id=?",(item_id,project_id)).fetchone():raise HTTPException(404,"Validation item not found")
        return [dict(x) for x in db.execute("SELECT * FROM validation_results WHERE validation_item_id=? ORDER BY result_no",(item_id,)).fetchall()]


def safe_external_reference(value):
    if not value:return
    parsed=urlparse(value)
    if parsed.scheme not in {"https","urn"} or (parsed.scheme=="https" and (not parsed.netloc or parsed.username or parsed.password)):raise HTTPException(422,"Evidence external reference must be a safe HTTPS URL or URN")


@router.post("/evidence",status_code=201)
def add_evidence(project_id:str,body:EvidenceIn,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id);safe_external_reference(body.external_reference)
    if not body.content_text and not body.external_reference:raise HTTPException(422,"Evidence requires actual content or an external reference")
    with transaction() as db:
        item=result=execution=None
        if body.validation_item_id:item=db.execute("SELECT * FROM validation_items WHERE id=? AND project_id=?",(body.validation_item_id,project_id)).fetchone()
        if body.validation_result_id:result=db.execute("SELECT * FROM validation_results WHERE id=? AND project_id=?",(body.validation_result_id,project_id)).fetchone()
        if body.execution_item_id:execution=db.execute("SELECT 1 FROM execution_items WHERE id=? AND project_id=?",(body.execution_item_id,project_id)).fetchone()
        if body.validation_item_id and not item or body.validation_result_id and not result or body.execution_item_id and not execution:raise HTTPException(422,"Evidence source is unknown or cross-project")
        if result and body.validation_item_id and result["validation_item_id"]!=body.validation_item_id:raise HTTPException(422,"Evidence result does not belong to the validation item")
        baseline=latest_delivery_baseline(db,project_id);allowed={x["requirement_revision_id"] for x in requirement_source(db,baseline)}
        reqs=set(body.requirement_revision_ids)
        if item: reqs.update(x[0] for x in db.execute("SELECT DISTINCT requirement_revision_id FROM validation_item_requirements WHERE validation_item_id=?",(item["id"],)).fetchall())
        if not reqs or not reqs.issubset(allowed):raise HTTPException(422,"Evidence must link to valid frozen requirement revisions")
        material=(body.content_text or body.external_reference).encode();digest=hashlib.sha256(material).hexdigest();evidence_id=uid("evid");code=next_code(db,project_id,"next_evidence_number","EVID");stamp=now();storage=f"oida://evidence/{evidence_id}" if body.content_text else body.external_reference
        db.execute("INSERT INTO evidence_records (id,project_id,evidence_code,classification,evidence_type,validation_item_id,validation_result_id,execution_item_id,title,description,storage_reference,external_reference,content_text,content_sha256,size_bytes,status,created_by,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(evidence_id,project_id,code,body.classification,body.evidence_type,body.validation_item_id,body.validation_result_id,body.execution_item_id,body.title,body.description,storage,body.external_reference,body.content_text,digest,len(material),"VALID",actor.id,stamp,stamp));
        for rid in reqs:db.execute("INSERT INTO evidence_requirement_links VALUES (?,?)",(evidence_id,rid))
        db.execute("INSERT INTO evidence_status_history VALUES (?,?,?,?,?,?,?)",(uid("ehist"),evidence_id,project_id,"VALID","Evidence captured",actor.id,stamp));audit(db,project_id,actor.id,"HUMAN","EVIDENCE_ADDED","EVIDENCE",evidence_id,detail={"classification":body.classification,"evidence_type":body.evidence_type,"sha256":digest,"size_bytes":len(material)});return {"id":evidence_id,"evidence_code":code,"status":"VALID","content_sha256":digest,"size_bytes":len(material),"storage_reference":storage}


@router.get("/evidence")
def list_evidence(project_id:str,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:
        values=[]
        for row in db.execute("SELECT * FROM evidence_records WHERE project_id=? ORDER BY created_at",(project_id,)).fetchall():
            value=dict(row);value.pop("content_text",None);value["requirement_revision_ids"]=[x[0] for x in db.execute("SELECT requirement_revision_id FROM evidence_requirement_links WHERE evidence_id=?",(row["id"],)).fetchall()];values.append(value)
        return values


@router.patch("/evidence/{evidence_id}/status")
def evidence_status(project_id:str,evidence_id:str,body:EvidenceStatusIn,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        row=db.execute("SELECT * FROM evidence_records WHERE id=? AND project_id=?",(evidence_id,project_id)).fetchone()
        if not row:raise HTTPException(404,"Evidence not found")
        db.execute("UPDATE evidence_records SET status=?,updated_at=? WHERE id=?",(body.status,now(),evidence_id));db.execute("INSERT INTO evidence_status_history VALUES (?,?,?,?,?,?,?)",(uid("ehist"),evidence_id,project_id,body.status,body.reason,actor.id,now()));audit(db,project_id,actor.id,"HUMAN","EVIDENCE_INVALIDATED" if body.status=="INVALID" else "EVIDENCE_SUPERSEDED","EVIDENCE",evidence_id,detail={"status":body.status});return {"id":evidence_id,"status":body.status}


def latest_committed_scope(db,project_id):return db.execute("SELECT * FROM qa_scopes WHERE project_id=? AND status IN ('COMMITTED','STALE') ORDER BY committed_at DESC LIMIT 1",(project_id,)).fetchone()
def current_results(db,scope_id):return db.execute("SELECT r.*,v.validation_code,v.required_for_acceptance,v.required_evidence_types_json,v.severity_if_failed FROM validation_items v LEFT JOIN validation_results r ON r.validation_item_id=v.id AND r.status='CURRENT' WHERE v.qa_scope_id=? AND v.candidate_status='ACTIVE' ORDER BY v.validation_code",(scope_id,)).fetchall()


def validation_state(db,project_id,scope):
    items=db.execute("SELECT * FROM validation_items WHERE qa_scope_id=? AND candidate_status='ACTIVE' ORDER BY validation_code",(scope["id"],)).fetchall();summary={key:0 for key in ["total","pass","fail","blocked","skipped","not_run"]};summary["total"]=len(items);failed=[];blocked=[];missing=[];result_ids=[];evidence_ids=[]
    for item in items:
        result=db.execute("SELECT * FROM validation_results WHERE validation_item_id=? AND status='CURRENT' ORDER BY result_no DESC LIMIT 1",(item["id"],)).fetchone()
        if not result:summary["not_run"]+=1
        else:
            summary[result["result"].lower()]+=1;result_ids.append(result["id"])
            if item["required_for_acceptance"] and result["result"]=="FAIL":failed.append({"validation_item_id":item["id"],"validation_code":item["validation_code"],"result_id":result["id"],"severity":item["severity_if_failed"]})
            if item["required_for_acceptance"] and result["result"]=="BLOCKED":blocked.append({"validation_item_id":item["id"],"validation_code":item["validation_code"],"result_id":result["id"]})
        if result:
            valid=db.execute("SELECT id,evidence_type FROM evidence_records WHERE validation_item_id=? AND status='VALID' AND validation_result_id=?",(item["id"],result["id"])).fetchall()
        else:
            valid=db.execute("SELECT id,evidence_type FROM evidence_records WHERE validation_item_id=? AND status='VALID'",(item["id"],)).fetchall()
        evidence_ids.extend(x["id"] for x in valid);have={x["evidence_type"] for x in valid};required=set(json.loads(item["required_evidence_types_json"]))
        if item["required_for_acceptance"] and (not result or result["result"]=="PASS") and not required.issubset(have):missing.append({"validation_item_id":item["id"],"validation_code":item["validation_code"],"missing_types":sorted(required-have)})
    req_total=db.execute("SELECT COUNT(*) FROM requirement_baseline_members WHERE baseline_id=?",(scope["requirement_baseline_id"],)).fetchone()[0];req_covered=db.execute("SELECT COUNT(DISTINCT l.requirement_revision_id) FROM validation_item_requirements l JOIN validation_items v ON v.id=l.validation_item_id WHERE v.qa_scope_id=? AND v.candidate_status='ACTIVE'",(scope["id"],)).fetchone()[0]
    evidence_summary={x["classification"]:x["n"] for x in db.execute("SELECT classification,COUNT(*) n FROM evidence_records WHERE project_id=? AND status='VALID' GROUP BY classification",(project_id,)).fetchall()};evidence_summary.update({"valid":len(set(evidence_ids)),"missing":len(missing),"invalid":db.execute("SELECT COUNT(*) FROM evidence_records e JOIN validation_items v ON v.id=e.validation_item_id WHERE e.project_id=? AND v.qa_scope_id=? AND v.candidate_status='ACTIVE' AND e.status='INVALID'",(project_id,scope["id"])).fetchone()[0]})
    return {"validation_summary":summary,"failed_items":failed,"blocked_items":blocked,"missing_evidence":missing,"result_ids":sorted(set(result_ids)),"evidence_ids":sorted(set(evidence_ids)),"requirement_summary":{"total":req_total,"covered":req_covered},"evidence_summary":evidence_summary}


def acceptance_readiness_value(db,project_id,mark_stale=True):
    baseline=latest_delivery_baseline(db,project_id);blockers=[];scope=latest_committed_scope(db,project_id)
    if not baseline:blockers.extend(["NO_FROZEN_REQUIREMENT_BASELINE","NO_FROZEN_DELIVERY_BASELINE"])
    if not scope:return {"ready":False,"status":"BLOCKED","blocking_items":[*blockers,"NO_COMMITTED_QA_SCOPE"],"qa_scope_id":None}
    snap,_=execution_snapshot(db,project_id)
    if scope["delivery_baseline_id"]!=baseline["id"] or scope["execution_snapshot_hash"]!=snap:
        blockers.append("STALE_QA_SCOPE")
        if mark_stale:db.execute("UPDATE qa_scopes SET status='STALE',updated_at=? WHERE id=?",(now(),scope["id"]))
    state=validation_state(db,project_id,scope);summary=state["validation_summary"]
    exceptions={x[0] for x in db.execute("SELECT validation_result_id FROM acceptance_exceptions WHERE project_id=? AND status='APPROVED'",(project_id,)).fetchall()}
    for row in db.execute("SELECT v.id,v.required_for_acceptance,r.id result_id,r.result FROM validation_items v LEFT JOIN validation_results r ON r.validation_item_id=v.id AND r.status='CURRENT' WHERE v.qa_scope_id=? AND v.candidate_status='ACTIVE'",(scope["id"],)).fetchall():
        if not row["required_for_acceptance"]:continue
        if not row["result_id"]:blockers.append("REQUIRED_VALIDATION_NOT_EXECUTED")
        elif row["result"]=="FAIL" and row["result_id"] not in exceptions:blockers.append("REQUIRED_VALIDATION_FAIL")
        elif row["result"]=="BLOCKED" and row["result_id"] not in exceptions:blockers.append("REQUIRED_VALIDATION_BLOCKED")
        elif row["result"]!="PASS" and row["result_id"] not in exceptions:blockers.append("REQUIRED_VALIDATION_NOT_EXECUTED")
    if state["missing_evidence"]:blockers.append("REQUIRED_EVIDENCE_MISSING")
    if state["evidence_summary"]["invalid"]:blockers.append("INVALID_EVIDENCE")
    if db.execute("SELECT COUNT(*) FROM execution_drift_records WHERE project_id=? AND status='OPEN' AND severity='CRITICAL'",(project_id,)).fetchone()[0]:blockers.append("UNRESOLVED_CRITICAL_DRIFT")
    truth=execution_truth_projection(project_id)
    if truth["execution_health"]!="HEALTHY":blockers.append("EXECUTION_TRUTH_NOT_HEALTHY")
    snapshot_hash=sha({"scope_id":scope["id"],"scope_revision":scope["current_revision"],"execution":snap,"results":state["result_ids"],"evidence":state["evidence_ids"],"blockers":sorted(set(blockers))})
    package=db.execute("SELECT * FROM acceptance_packages WHERE project_id=? ORDER BY version DESC LIMIT 1",(project_id,)).fetchone()
    if not package:blockers.append("NO_ACCEPTANCE_PACKAGE")
    elif package["validation_snapshot_hash"]!=snapshot_hash:
        blockers.append("STALE_ACCEPTANCE_PACKAGE")
        if mark_stale:db.execute("UPDATE acceptance_packages SET status='STALE' WHERE id=?",(package["id"],))
    blockers=sorted(set(blockers));ready=not blockers
    requirement_version=db.execute("SELECT version FROM requirement_baselines WHERE id=?",(scope["requirement_baseline_id"],)).fetchone()[0]
    return {"ready":ready,"status":"READY" if ready else "BLOCKED","blocking_items":blockers,"requirement_baseline_id":scope["requirement_baseline_id"],"requirement_baseline_version":requirement_version,"delivery_baseline_id":scope["delivery_baseline_id"],"delivery_baseline_version":baseline["version"],"qa_scope_id":scope["id"],"qa_scope_code":scope["qa_code"],"qa_scope_revision":scope["current_revision"],"acceptance_package_id":package["id"] if package and package["validation_snapshot_hash"]==snapshot_hash else None,"validation_snapshot_hash":snapshot_hash,**state,"execution_snapshot_hash":snap,"execution_truth":truth}


@router.get("/acceptance/readiness")
def acceptance_readiness(project_id:str,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        value=acceptance_readiness_value(db,project_id);audit(db,project_id,actor.id,"HUMAN","GATE3_READINESS_CHECKED","PROJECT",project_id,result=value["status"],detail={"blocking_items":value["blocking_items"]});return value


def acceptance_foundation(db,project_id,readiness):
    scope=db.execute("SELECT * FROM qa_scopes WHERE id=?",(readiness["qa_scope_id"],)).fetchone();project=db.execute("SELECT name,objective FROM projects WHERE id=?",(project_id,)).fetchone();drift=[dict(x) for x in db.execute("SELECT drift_type,severity,status FROM execution_drift_records WHERE project_id=? AND status IN ('OPEN','ACKNOWLEDGED')",(project_id,)).fetchall()]
    return AcceptanceFoundationInput(project["name"],project["objective"],scope["requirement_baseline_id"],scope["delivery_baseline_id"],scope["id"],scope["current_revision"],readiness["execution_truth"],readiness["requirement_summary"],readiness["validation_summary"],readiness["evidence_summary"],readiness["failed_items"],readiness["blocked_items"],readiness["missing_evidence"],json.loads(scope["risks_json"]),drift,{"ready":readiness["ready"],"blocking_items":readiness["blocking_items"]})


def generate_package_sync(project_id:str,body:GenerateIn,idempotency_key:Optional[str],actor:Actor):
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"GENERATE_ACCEPTANCE_PACKAGE",key)
        if previous:return previous
        # Generate from deterministic state before requiring a current package.
        readiness=acceptance_readiness_value(db,project_id,False);readiness["blocking_items"]=[x for x in readiness["blocking_items"] if x not in {"NO_ACCEPTANCE_PACKAGE","STALE_ACCEPTANCE_PACKAGE"}];readiness["ready"]=not readiness["blocking_items"]
        if not readiness.get("qa_scope_id"):raise HTTPException(409,"Committed QA Scope required")
        foundation=acceptance_foundation(db,project_id,readiness);adapter=adapter_for();run_id=uid("qarun");stamp=now();scope=db.execute("SELECT * FROM qa_scopes WHERE id=?",(readiness["qa_scope_id"],)).fetchone()
        db.execute("INSERT INTO qa_ai_runs (id,project_id,run_type,requested_by,provider,model,reasoning_effort,prompt_version,instruction,requirement_baseline_id,delivery_baseline_id,qa_scope_id,status,started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(run_id,project_id,"ACCEPTANCE_PACKAGE",actor.id,adapter.provider,adapter.model,getattr(adapter,"reasoning_effort",None),"acceptance-package/v1",body.instruction,scope["requirement_baseline_id"],scope["delivery_baseline_id"],scope["id"],"RUNNING",stamp));audit(db,project_id,f"ai:{run_id}","AI","ACCEPTANCE_PACKAGE_AI_RUN_STARTED","QA_AI_RUN",run_id)
        try:
            output=adapter.generate_acceptance_package(foundation,body.instruction);failed={x["validation_item_id"] for x in readiness["failed_items"]};missing={x["validation_item_id"] for x in readiness["missing_evidence"]};blockers=set(readiness["blocking_items"])
            if failed!=set(output.critical_failure_validation_item_ids) or missing!=set(output.missing_evidence_validation_item_ids) or blockers!=set(output.critical_blockers):raise AIInvalidOutput("Acceptance Package failure, evidence-gap, and blocker membership must exactly match authoritative state")
            if not readiness["ready"] and output.acceptance_recommendation=="RECOMMEND_ACCEPT":raise AIInvalidOutput("Acceptance recommendation conflicts with deterministic blockers")
        except AIError as exc:
            metrics=getattr(adapter,"last_metrics",None);values=metrics.as_dict() if metrics else {};db.execute("UPDATE qa_ai_runs SET status='FAILED',failure_code=?,input_tokens=?,cache_hit_tokens=?,output_tokens=?,total_tokens=?,latency_ms=?,provider_request_id=?,completed_at=? WHERE id=?",(exc.code,values.get("input_tokens"),values.get("cache_hit_tokens"),values.get("output_tokens"),values.get("total_tokens"),values.get("latency_ms"),values.get("provider_request_id"),now(),run_id));result={"ai_run_id":run_id,"status":"FAILED","failure_code":exc.code,"message":str(exc),"provider":adapter.provider,"telemetry":values};audit(db,project_id,f"ai:{run_id}","AI","ACCEPTANCE_PACKAGE_AI_RUN_FAILED","QA_AI_RUN",run_id,"FAILED",{"failure_code":exc.code});idem_put(db,project_id,actor.id,"GENERATE_ACCEPTANCE_PACKAGE",key,result);return result
        version=db.execute("SELECT COALESCE(MAX(version),0)+1 FROM acceptance_packages WHERE project_id=?",(project_id,)).fetchone()[0];package_id=uid("apkg");summary={"requirement_readiness":output.requirement_readiness};validation={**readiness["validation_summary"],"narrative":output.validation_readiness};evidence={**readiness["evidence_summary"],"narrative":output.evidence_readiness};execution={"health":readiness["execution_truth"]["execution_health"],"narrative":output.execution_readiness}
        db.execute("UPDATE acceptance_packages SET status='STALE' WHERE project_id=? AND status='CURRENT'",(project_id,))
        db.execute("INSERT INTO acceptance_packages (id,project_id,version,requirement_baseline_id,delivery_baseline_id,qa_scope_id,qa_scope_revision,execution_snapshot_hash,validation_snapshot_hash,ai_run_id,status,executive_summary,requirement_summary_json,validation_summary_json,evidence_summary_json,execution_summary_json,critical_failures_json,critical_blockers_json,missing_evidence_json,residual_risks_json,recommendation,recommendation_basis,generated_by,generated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(package_id,project_id,version,scope["requirement_baseline_id"],scope["delivery_baseline_id"],scope["id"],scope["current_revision"],readiness["execution_snapshot_hash"],readiness["validation_snapshot_hash"],run_id,"CURRENT",output.executive_summary,dumps(summary),dumps(validation),dumps(evidence),dumps(execution),dumps(output.critical_failure_validation_item_ids),dumps(output.critical_blockers),dumps(output.missing_evidence_validation_item_ids),dumps(output.residual_risks),output.acceptance_recommendation,output.recommendation_basis,f"ai:{run_id}",stamp));metrics=getattr(adapter,"last_metrics",None);values=metrics.as_dict() if metrics else {};db.execute("UPDATE qa_ai_runs SET status='SUCCEEDED',findings_json=?,input_tokens=?,cache_hit_tokens=?,output_tokens=?,total_tokens=?,latency_ms=?,provider_request_id=?,completed_at=? WHERE id=?",(dumps(output.findings),values.get("input_tokens"),values.get("cache_hit_tokens"),values.get("output_tokens"),values.get("total_tokens"),values.get("latency_ms"),values.get("provider_request_id"),now(),run_id));result={"ai_run_id":run_id,"package_id":package_id,"version":version,"status":"SUCCEEDED","recommendation":output.acceptance_recommendation,"deterministic_ready":readiness["ready"],"telemetry":values};audit(db,project_id,f"ai:{run_id}","AI","ACCEPTANCE_PACKAGE_GENERATED","ACCEPTANCE_PACKAGE",package_id,detail={"recommendation":output.acceptance_recommendation,"deterministic_ready":readiness["ready"]});idem_put(db,project_id,actor.id,"GENERATE_ACCEPTANCE_PACKAGE",key,result);return result


@router.post("/acceptance-packages:generate", status_code=202)
def generate_package(project_id:str,body:GenerateIn,idempotency_key:Optional[str]=Header(None),actor:Actor=Depends(current_actor)):
    from .jobs import enqueue
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        readiness=acceptance_readiness_value(db,project_id,False)
        if not readiness.get("qa_scope_id"):raise HTTPException(409,"Committed QA Scope required")
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"QUEUE_ACCEPTANCE_PACKAGE",key)
        if previous:return previous
        result=enqueue(db,project_id,actor,"ACCEPTANCE_PACKAGE",body.model_dump());idem_put(db,project_id,actor.id,"QUEUE_ACCEPTANCE_PACKAGE",key,result)
    return result


@router.post("/acceptance-packages",status_code=201)
def create_manual_package(project_id:str,body:ManualAcceptancePackageIn,idempotency_key:Optional[str]=Header(None),actor:Actor=Depends(current_actor)):
    require_project(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"CREATE_MANUAL_ACCEPTANCE_PACKAGE",key)
        if previous:return previous
        readiness=acceptance_readiness_value(db,project_id,False)
        readiness["blocking_items"]=[x for x in readiness["blocking_items"] if x not in {"NO_ACCEPTANCE_PACKAGE","STALE_ACCEPTANCE_PACKAGE"}]
        readiness["ready"]=not readiness["blocking_items"]
        if not readiness.get("qa_scope_id"):raise HTTPException(409,"Committed QA Scope required")
        scope=db.execute("SELECT * FROM qa_scopes WHERE id=? AND project_id=?",(readiness["qa_scope_id"],project_id)).fetchone();version=db.execute("SELECT COALESCE(MAX(version),0)+1 FROM acceptance_packages WHERE project_id=?",(project_id,)).fetchone()[0];package_id=uid("apkg");stamp=now()
        db.execute("UPDATE acceptance_packages SET status='STALE' WHERE project_id=? AND status='CURRENT'",(project_id,))
        db.execute("INSERT INTO acceptance_packages (id,project_id,version,requirement_baseline_id,delivery_baseline_id,qa_scope_id,qa_scope_revision,execution_snapshot_hash,validation_snapshot_hash,ai_run_id,status,executive_summary,requirement_summary_json,validation_summary_json,evidence_summary_json,execution_summary_json,critical_failures_json,critical_blockers_json,missing_evidence_json,residual_risks_json,recommendation,recommendation_basis,generated_by,generated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(package_id,project_id,version,scope["requirement_baseline_id"],scope["delivery_baseline_id"],scope["id"],scope["current_revision"],readiness["execution_snapshot_hash"],readiness["validation_snapshot_hash"],None,"CURRENT",body.executive_summary,dumps(readiness["requirement_summary"]),dumps(readiness["validation_summary"]),dumps(readiness["evidence_summary"]),dumps({"health":readiness["execution_truth"]["execution_health"]}),dumps([x["validation_item_id"] for x in readiness["failed_items"]]),dumps(readiness["blocking_items"]),dumps([x["validation_item_id"] for x in readiness["missing_evidence"]]),dumps(body.residual_risks),"NO_AI_RECOMMENDATION",body.recommendation_basis,actor.id,stamp))
        result={"package_id":package_id,"version":version,"status":"CURRENT","recommendation":"NO_AI_RECOMMENDATION","deterministic_ready":readiness["ready"],"origin":"HUMAN"};audit(db,project_id,actor.id,"HUMAN","ACCEPTANCE_PACKAGE_CREATED_MANUALLY","ACCEPTANCE_PACKAGE",package_id,detail={"deterministic_ready":readiness["ready"]});idem_put(db,project_id,actor.id,"CREATE_MANUAL_ACCEPTANCE_PACKAGE",key,result);return result


@router.get("/acceptance-packages")
def list_packages(project_id:str,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:
        result=[]
        for row in db.execute("SELECT * FROM acceptance_packages WHERE project_id=? ORDER BY version DESC",(project_id,)).fetchall():
            value=dict(row)
            for key in ["requirement_summary_json","validation_summary_json","evidence_summary_json","execution_summary_json","critical_failures_json","critical_blockers_json","missing_evidence_json","residual_risks_json"]:value[key.removesuffix("_json")]=json.loads(value.pop(key))
            result.append(value)
        return result


@router.post("/acceptance-exceptions",status_code=201)
def create_exception(project_id:str,body:ExceptionIn,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with transaction() as db:
        result=db.execute("SELECT * FROM validation_results WHERE id=? AND validation_item_id=? AND project_id=?",(body.validation_result_id,body.validation_item_id,project_id)).fetchone()
        if not result or result["result"] not in {"FAIL","BLOCKED"}:raise HTTPException(422,"Exception requires an actual failed or blocked validation result")
        exception_id=uid("aexc");stamp=now();db.execute("INSERT INTO acceptance_exceptions VALUES (?,?,?,?,?,?,?,?,?,?,?)",(exception_id,project_id,body.validation_item_id,body.validation_result_id,body.reason,body.risk,"PENDING",actor.id,None,stamp,None));audit(db,project_id,actor.id,"HUMAN","ACCEPTANCE_EXCEPTION_CREATED","ACCEPTANCE_EXCEPTION",exception_id);return {"id":exception_id,"status":"PENDING"}


@router.post("/acceptance-exceptions/{exception_id}:decide")
def decide_exception(project_id:str,exception_id:str,body:ExceptionDecisionIn,actor:Actor=Depends(current_actor)):
    human_owner(actor,project_id)
    with transaction() as db:
        row=db.execute("SELECT * FROM acceptance_exceptions WHERE id=? AND project_id=?",(exception_id,project_id)).fetchone()
        if not row:raise HTTPException(404,"Acceptance exception not found")
        db.execute("UPDATE acceptance_exceptions SET status=?,approved_by=?,decided_at=? WHERE id=?",(body.decision,actor.id,now(),exception_id));audit(db,project_id,actor.id,"HUMAN","ACCEPTANCE_EXCEPTION_APPROVED" if body.decision=="APPROVED" else "ACCEPTANCE_EXCEPTION_REJECTED","ACCEPTANCE_EXCEPTION",exception_id);return {"id":exception_id,"status":body.decision}


def final_view(db,row):
    value=dict(row);value["validation_result_ids"]=[x[0] for x in db.execute("SELECT validation_result_id FROM final_acceptance_validation_results WHERE final_acceptance_id=?",(row["id"],)).fetchall()];value["evidence_ids"]=[x[0] for x in db.execute("SELECT evidence_id FROM final_acceptance_evidence WHERE final_acceptance_id=?",(row["id"],)).fetchall()];value["exception_ids"]=[x[0] for x in db.execute("SELECT acceptance_exception_id FROM final_acceptance_exceptions WHERE final_acceptance_id=?",(row["id"],)).fetchall()];return value


@router.post("/final-acceptance")
def final_accept(project_id:str,body:FinalAcceptanceIn,idempotency_key:Optional[str]=Header(None),actor:Actor=Depends(current_actor)):
    human_owner(actor,project_id);key=require_key(idempotency_key)
    with transaction() as db:
        previous=idem_get(db,project_id,actor.id,"FINAL_ACCEPTANCE",key)
        if previous:return previous
        readiness=acceptance_readiness_value(db,project_id)
        if not readiness["ready"]:raise HTTPException(409,{"code":"GATE3_NOT_READY","blocking_items":readiness["blocking_items"]})
        package=db.execute("SELECT * FROM acceptance_packages WHERE id=? AND project_id=? AND status='CURRENT'",(body.acceptance_package_id,project_id)).fetchone()
        if not package or package["id"]!=readiness["acceptance_package_id"]:raise HTTPException(409,"Exact current Acceptance Package required")
        scope=db.execute("SELECT * FROM qa_scopes WHERE id=?",(readiness["qa_scope_id"],)).fetchone();baseline=latest_delivery_baseline(db,project_id);exceptions=sorted(x[0] for x in db.execute("SELECT id FROM acceptance_exceptions WHERE project_id=? AND status='APPROVED'",(project_id,)).fetchall());membership={"requirement_baseline_id":scope["requirement_baseline_id"],"delivery_baseline_id":scope["delivery_baseline_id"],"execution_snapshot_hash":readiness["execution_snapshot_hash"],"qa_scope_id":scope["id"],"qa_scope_revision":scope["current_revision"],"package_id":package["id"],"package_version":package["version"],"result_ids":readiness["result_ids"],"evidence_ids":readiness["evidence_ids"],"exception_ids":exceptions};membership_hash=sha(membership)
        existing=db.execute("SELECT * FROM final_acceptances WHERE project_id=?",(project_id,)).fetchone()
        if existing:
            if existing["membership_hash"]==membership_hash:
                result=final_view(db,existing);idem_put(db,project_id,actor.id,"FINAL_ACCEPTANCE",key,result);return result
            raise HTTPException(409,"Project already has an immutable Final Acceptance with different exact membership")
        version=1;acceptance_id=uid("final");code=next_code(db,project_id,"next_acceptance_number","FINAL-ACCEPTANCE");stamp=now();req_version=db.execute("SELECT version FROM requirement_baselines WHERE id=?",(scope["requirement_baseline_id"],)).fetchone()[0];audit(db,project_id,actor.id,"HUMAN","FINAL_ACCEPTANCE_REQUESTED","PROJECT",project_id,detail={"membership_hash":membership_hash})
        db.execute("INSERT INTO final_acceptances (id,project_id,version,acceptance_code,status,requirement_baseline_id,requirement_baseline_version,delivery_baseline_id,delivery_baseline_version,execution_snapshot_hash,qa_scope_id,qa_scope_revision,acceptance_package_id,acceptance_package_version,membership_hash,acceptance_comment,accepted_by,accepted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(acceptance_id,project_id,version,code,"ACCEPTED",scope["requirement_baseline_id"],req_version,scope["delivery_baseline_id"],baseline["version"],readiness["execution_snapshot_hash"],scope["id"],scope["current_revision"],package["id"],package["version"],membership_hash,body.acceptance_comment,actor.id,stamp))
        for rid in readiness["result_ids"]:db.execute("INSERT INTO final_acceptance_validation_results VALUES (?,?)",(acceptance_id,rid))
        for eid in readiness["evidence_ids"]:db.execute("INSERT INTO final_acceptance_evidence VALUES (?,?)",(acceptance_id,eid))
        for xid in exceptions:db.execute("INSERT INTO final_acceptance_exceptions VALUES (?,?)",(acceptance_id,xid))
        written=db.execute("SELECT * FROM final_acceptances WHERE id=?",(acceptance_id,)).fetchone()
        if not written or written["membership_hash"]!=membership_hash or written["accepted_by"]!=actor.id:raise HTTPException(500,"Final Acceptance read-after-write reconciliation failed")
        result=final_view(db,written);audit(db,project_id,actor.id,"HUMAN","FINAL_ACCEPTANCE_CONFIRMED","FINAL_ACCEPTANCE",acceptance_id,detail={"version":version,"membership_hash":membership_hash});idem_put(db,project_id,actor.id,"FINAL_ACCEPTANCE",key,result);return result


@router.get("/final-acceptances")
def list_final(project_id:str,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id)
    with connect() as db:return [final_view(db,x) for x in db.execute("SELECT * FROM final_acceptances WHERE project_id=? ORDER BY version",(project_id,)).fetchall()]


def phase4_truth_projection(project_id):
    with transaction() as db:
        scope=latest_committed_scope(db,project_id);final=db.execute("SELECT * FROM final_acceptances WHERE project_id=? ORDER BY version DESC LIMIT 1",(project_id,)).fetchone()
        if not scope:return {"qa_scope_status":"NOT_COMMITTED","validation":{"total":0,"pass":0,"fail":0,"blocked":0,"not_run":0},"evidence":{"required":0,"available":0,"missing":0,"invalid":0},"acceptance_readiness":"BLOCKED","acceptance_package_status":"NONE","gate3_status":"NOT_ACCEPTED","phase4_attention":[],"phase4_next_action":"Generate and commit QA Scope"}
        readiness=acceptance_readiness_value(db,project_id);package=db.execute("SELECT status FROM acceptance_packages WHERE project_id=? ORDER BY version DESC LIMIT 1",(project_id,)).fetchone();attention=[]
        for blocker in readiness["blocking_items"]:attention.append({"type":blocker,"message":blocker.replace("_"," ").title(),"severity":"HIGH" if blocker in {"REQUIRED_VALIDATION_FAIL","REQUIRED_VALIDATION_BLOCKED","UNRESOLVED_CRITICAL_DRIFT","INVALID_EVIDENCE"} else "MEDIUM"})
        if final:next_action="Phase 4 complete"
        elif "REQUIRED_VALIDATION_NOT_EXECUTED" in readiness["blocking_items"]:next_action="Execute required validations"
        elif any(x in readiness["blocking_items"] for x in ["REQUIRED_VALIDATION_FAIL","REQUIRED_VALIDATION_BLOCKED"]):next_action="Resolve failed validation"
        elif "REQUIRED_EVIDENCE_MISSING" in readiness["blocking_items"]:next_action="Attach missing evidence"
        elif any(x in readiness["blocking_items"] for x in ["NO_ACCEPTANCE_PACKAGE","STALE_ACCEPTANCE_PACKAGE"]):next_action="Generate Acceptance Package"
        elif readiness["ready"]:next_action="Perform Final Acceptance"
        else:next_action="Resolve acceptance blockers"
        return {"qa_scope_status":scope["status"],"qa_scope":{"id":scope["id"],"code":scope["qa_code"],"revision":scope["current_revision"]},"validation":readiness["validation_summary"],"requirement_validation_coverage":readiness["requirement_summary"],"evidence":{"required":readiness["validation_summary"]["total"],"available":readiness["evidence_summary"]["valid"],"missing":readiness["evidence_summary"]["missing"],"invalid":readiness["evidence_summary"]["invalid"]},"acceptance_readiness":"READY" if readiness["ready"] else "BLOCKED","acceptance_blockers":readiness["blocking_items"],"acceptance_package_status":package["status"] if package else "NONE","gate3_status":"ACCEPTED" if final else "NOT_ACCEPTED","final_acceptance":final_view(db,final) if final else None,"phase4_attention":attention,"phase4_next_action":next_action}


@router.get("/validation/truth")
def validation_truth(project_id:str,actor:Actor=Depends(current_actor)):
    require_project(actor,project_id);return phase4_truth_projection(project_id)


@router.post("/qa-bindings",status_code=201)
def create_binding(project_id:str,body:BindingIn,actor:Actor=Depends(current_actor)):
    human_owner(actor,project_id)
    with transaction() as db:
        if db.execute("SELECT 1 FROM qa_bindings WHERE project_id=?",(project_id,)).fetchone():raise HTTPException(409,"QA Again binding already exists")
        binding_id=uid("qabind");stamp=now();db.execute("INSERT INTO qa_bindings VALUES (?,?,?,?,?,?,?,?,?,?)",(binding_id,project_id,"QA_AGAIN",body.external_project_id,"UNBOUND",dumps(CAPABILITIES["QA_AGAIN"].as_dict()),None,actor.id,stamp,stamp));audit(db,project_id,actor.id,"HUMAN","QA_BINDING_CREATED","QA_BINDING",binding_id);return {"id":binding_id,"status":"UNBOUND","target_type":"QA_AGAIN"}


@router.post("/qa-bindings/{binding_id}:verify")
def verify_binding(project_id:str,binding_id:str,actor:Actor=Depends(current_actor)):
    human_owner(actor,project_id)
    with transaction() as db:
        row=db.execute("SELECT * FROM qa_bindings WHERE id=? AND project_id=?",(binding_id,project_id)).fetchone()
        if not row:raise HTTPException(404,"QA binding not found")
        try:adapter_for_validation_target("QA_AGAIN").list_project_validation(db,project_id,binding_id);status="READY"
        except ValidationTargetUnavailable:status="ERROR"
        db.execute("UPDATE qa_bindings SET status=?,last_verified_at=?,updated_at=? WHERE id=?",(status,now(),now(),binding_id));return {"id":binding_id,"status":status}
