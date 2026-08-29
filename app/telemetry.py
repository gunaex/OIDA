from __future__ import annotations

import uuid

from .db import now


def record_ai_telemetry(db, project_id: str, run_kind: str, run_id: str, adapter, fallback_error=None) -> dict:
    metrics = getattr(adapter, "last_metrics", None)
    value = metrics.as_dict() if metrics else {
        "provider": adapter.provider,
        "model": adapter.model,
        "reasoning_effort": getattr(adapter, "reasoning_effort", None),
        "input_tokens": None,
        "cache_hit_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "latency_ms": None,
        "provider_request_id": None,
        "error_class": fallback_error,
    }
    if fallback_error and not value.get("error_class"):
        value["error_class"] = fallback_error
    db.execute(
        "INSERT INTO ai_run_telemetry VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(run_kind,run_id) DO UPDATE SET id=excluded.id,project_id=excluded.project_id,provider=excluded.provider,model=excluded.model,reasoning_effort=excluded.reasoning_effort,input_tokens=excluded.input_tokens,cache_hit_tokens=excluded.cache_hit_tokens,output_tokens=excluded.output_tokens,total_tokens=excluded.total_tokens,latency_ms=excluded.latency_ms,provider_request_id=excluded.provider_request_id,error_class=excluded.error_class,created_at=excluded.created_at",
        (f"aitel_{uuid.uuid4().hex}", project_id, run_kind, run_id, value["provider"], value["model"],
         value.get("reasoning_effort"), value.get("input_tokens"), value.get("cache_hit_tokens"),
         value.get("output_tokens"), value.get("total_tokens"), value.get("latency_ms"),
         value.get("provider_request_id"), value.get("error_class"), now()),
    )
    return value
