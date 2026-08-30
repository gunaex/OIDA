from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import os
import socket
import time
import uuid

from .auth import Actor
from .db import connect, is_postgres, now, transaction

log = logging.getLogger("oida.jobs")
TERMINAL = {"COMPLETED", "FAILED"}


def _audit(db, job_id: str, project_id: str, actor_id: str, actor_type: str, action: str, result: str = "SUCCESS", detail: dict | None = None):
    db.execute("INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?)",(
        f"aud_{uuid.uuid4().hex}",project_id,actor_id,actor_type,action,"ASYNC_AI_RUN",job_id,result,
        json.dumps(detail or {},separators=(",",":")),now()))


def enqueue(db, project_id: str, actor: Actor, operation: str, request: dict) -> dict:
    job_id = f"job_{uuid.uuid4().hex}"
    db.execute(
        "INSERT INTO async_ai_jobs (id,project_id,requested_by,operation,status,request_json,created_at) VALUES (?,?,?,?,?,?,?)",
        (job_id, project_id, actor.id, operation, "QUEUED", json.dumps(request, separators=(",", ":")), now()),
    )
    _audit(db,job_id,project_id,actor.id,"HUMAN","AI_RUN_QUEUED",detail={"operation":operation})
    return {"ai_run_id": job_id, "status": "QUEUED", "operation": operation}


def view(row) -> dict:
    value = dict(row)
    value["request"] = json.loads(value.pop("request_json"))
    raw = value.pop("result_json")
    value["result"] = json.loads(raw) if raw else None
    return value


def claim(worker_id: str, lease_seconds: int = 900):
    expires = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
    with transaction() as db:
        if is_postgres():
            row = db.execute(
                "SELECT * FROM async_ai_jobs WHERE status='QUEUED' OR (status='RUNNING' AND lease_expires_at<?) "
                "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1", (now(),)
            ).fetchone()
        else:
            row = db.execute(
                "SELECT * FROM async_ai_jobs WHERE status='QUEUED' OR (status='RUNNING' AND lease_expires_at<?) ORDER BY created_at LIMIT 1",
                (now(),),
            ).fetchone()
        if not row:
            return None
        db.execute(
            "UPDATE async_ai_jobs SET status='RUNNING',lease_owner=?,lease_expires_at=?,attempt_count=attempt_count+1,started_at=COALESCE(started_at,?) WHERE id=?",
            (worker_id, expires, now(), row["id"]),
        )
        _audit(db,row["id"],row["project_id"],worker_id,"SYSTEM","AI_RUN_STARTED",detail={"operation":row["operation"]})
        return {**view(row), "status": "RUNNING", "lease_owner": worker_id, "lease_expires_at": expires}


def _execute(job: dict) -> dict:
    # Imports are intentionally late: the web app owns domain use-cases, while this
    # module owns only durable scheduling and recovery.
    from .main import GenerateIn, generate_requirements_sync, regenerate_candidate_sync
    from .phase2 import GenerateDesignIn, generate_plan_sync, generate_solutions_sync, regenerate_plan_sync, regenerate_solution_candidate_sync
    from .phase3 import GenerateMaterializationIn, generate_materialization_plan_sync
    from .phase4 import GenerateIn as Phase4GenerateIn, generate_package_sync, generate_scope_sync

    with connect() as db:
        user = db.execute("SELECT id,email,display_name,actor_type,must_change_password FROM users WHERE id=?", (job["requested_by"],)).fetchone()
    if not user:
        raise RuntimeError("REQUESTING_USER_MISSING")
    actor = Actor(**dict(user))
    body = job["request"]
    key = f"async:{job['id']}"
    operation = job["operation"]
    if operation == "REQUIREMENTS":
        return generate_requirements_sync(job["project_id"], GenerateIn(**body), key, actor)
    if operation == "REQUIREMENTS_REGENERATE":
        return regenerate_candidate_sync(job["project_id"], body.pop("candidate_id"), GenerateIn(**body), key, actor)
    if operation == "SOLUTIONS":
        return generate_solutions_sync(job["project_id"], GenerateDesignIn(**body), key, actor)
    if operation == "SOLUTIONS_REGENERATE":
        return regenerate_solution_candidate_sync(job["project_id"], body.pop("candidate_id"), GenerateDesignIn(**body), key, actor)
    if operation == "DELIVERY_PLAN":
        return generate_plan_sync(job["project_id"], GenerateDesignIn(**body), key, actor)
    if operation == "DELIVERY_PLAN_REGENERATE":
        return regenerate_plan_sync(job["project_id"], body.pop("candidate_id"), GenerateDesignIn(**body), key, actor)
    if operation == "MATERIALIZATION":
        return generate_materialization_plan_sync(job["project_id"], GenerateMaterializationIn(**body), key, actor)
    if operation == "QA_SCOPE":
        return generate_scope_sync(job["project_id"], Phase4GenerateIn(**body), key, actor)
    if operation == "ACCEPTANCE_PACKAGE":
        return generate_package_sync(job["project_id"], Phase4GenerateIn(**body), key, actor)
    raise RuntimeError("UNSUPPORTED_AI_OPERATION")


def run_one(worker_id: str | None = None) -> bool:
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    job = claim(worker_id)
    if not job:
        return False
    try:
        result = _execute(job)
        failed = result.get("status") == "FAILED"
        with transaction() as db:
            db.execute(
                "UPDATE async_ai_jobs SET status=?,result_json=?,failure_code=?,domain_run_id=?,lease_owner=NULL,lease_expires_at=NULL,completed_at=? WHERE id=? AND lease_owner=?",
                ("FAILED" if failed else "COMPLETED", json.dumps(result, separators=(",", ":")), result.get("failure_code"),
                 result.get("ai_run_id"), now(), job["id"], worker_id),
            )
            _audit(db,job["id"],job["project_id"],worker_id,"SYSTEM","AI_RUN_FAILED" if failed else "AI_RUN_COMPLETED",
                   "FAILED" if failed else "SUCCESS",{"operation":job["operation"],"failure_code":result.get("failure_code")})
    except Exception as exc:
        log.exception("async AI job failed", extra={"job_id": job["id"], "operation": job["operation"]})
        with transaction() as db:
            db.execute(
                "UPDATE async_ai_jobs SET status='FAILED',failure_code='WORKER_EXECUTION_FAILED',result_json=?,lease_owner=NULL,lease_expires_at=NULL,completed_at=? WHERE id=? AND lease_owner=?",
                (json.dumps({"status":"FAILED","failure_code":"WORKER_EXECUTION_FAILED","message":type(exc).__name__}), now(), job["id"], worker_id),
            )
            _audit(db,job["id"],job["project_id"],worker_id,"SYSTEM","AI_RUN_FAILED","FAILED",
                   {"operation":job["operation"],"failure_code":"WORKER_EXECUTION_FAILED"})
    return True


def run_forever(poll_seconds: float = 2.0):
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    while True:
        if not run_one(worker_id):
            time.sleep(poll_seconds)
