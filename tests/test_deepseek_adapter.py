import json
from types import SimpleNamespace

import httpx
import pytest

from app import ai


def configured(monkeypatch):
    monkeypatch.setattr(ai, "settings", SimpleNamespace(
        ai_provider="deepseek",
        ai_model="deepseek-v4-pro",
        ai_reasoning_effort="high",
        openai_api_key="",
        deepseek_api_key="unit-test-placeholder",
        deepseek_base_url="https://api.deepseek.com",
    ))


def baseline():
    return ai.RequirementBaselineInput(
        project_name="Acceptance Project",
        objective="Deliver a traceable solution",
        baseline_id="rb_1",
        baseline_version=1,
        requirements=[{
            "requirement_code": "REQ-001",
            "requirement_revision_id": "rr_1",
            "title": "Secure access",
            "statement": "Authorized users shall access their project records securely.",
            "priority": "MUST",
            "acceptance_criteria": ["An authorized user can access the project."],
        }],
    )


def response(content, status=200, usage=None, headers=None):
    body = {
        "id": "deepseek-request-1",
        "status": "completed",
        "output": [{"type":"message", "content":[{"type":"output_text", "text":content}]}],
        "usage": usage or {
            "input_tokens": 100,
            "input_tokens_details": {"cached_tokens":40},
            "output_tokens": 50,
            "total_tokens": 150,
        },
    }
    return httpx.Response(status, json=body, headers=headers, request=httpx.Request("POST", "https://api.deepseek.com/responses"))


def valid_solution_json():
    return ai.FakeAdapter().generate_solutions(baseline()).model_dump_json()


def test_deepseek_valid_structured_output_and_metrics(monkeypatch):
    configured(monkeypatch)
    captured = {}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(valid_solution_json())

    monkeypatch.setattr(ai.httpx, "post", post)
    adapter = ai.adapter_for()
    output = adapter.generate_solutions(baseline())

    assert isinstance(adapter, ai.DeepSeekAdapter)
    assert len(output.alternatives) == 3
    assert captured["url"] == "https://api.deepseek.com/responses"
    assert captured["json"]["text"]["format"]["type"] == "json_schema"
    assert captured["json"]["text"]["format"]["strict"] is True
    assert captured["json"]["reasoning"] == {"effort":"high"}
    assert adapter.last_metrics.provider == "deepseek"
    assert adapter.last_metrics.model == "deepseek-v4-pro"
    assert adapter.last_metrics.cache_hit_tokens == 40
    assert adapter.last_metrics.total_tokens == 150
    assert adapter.last_metrics.provider_request_id == "deepseek-request-1"


def test_deepseek_bounded_repair_aggregates_billable_metrics(monkeypatch):
    configured(monkeypatch)
    calls=[]
    def post(*args,**kwargs):
        calls.append(kwargs["json"])
        if len(calls)==1:
            return response("not-json",usage={"input_tokens":20,"input_tokens_details":{"cached_tokens":0},"output_tokens":10,"total_tokens":30})
        return response(valid_solution_json(),usage={"input_tokens":25,"input_tokens_details":{"cached_tokens":5},"output_tokens":15,"total_tokens":40})
    monkeypatch.setattr(ai.httpx,"post",post)
    adapter=ai.DeepSeekAdapter();output=adapter.generate_solutions(baseline())
    assert len(output.alternatives)==3 and len(calls)==2
    assert calls[1]["input"][1]["content"].find('"repair_attempt":1')!=-1
    assert adapter.last_metrics.input_tokens==45
    assert adapter.last_metrics.cache_hit_tokens==5
    assert adapter.last_metrics.output_tokens==25
    assert adapter.last_metrics.total_tokens==70


@pytest.mark.parametrize("content", ["not-json", json.dumps({"alternatives": [], "findings": []})])
def test_deepseek_rejects_malformed_or_schema_invalid_output(monkeypatch, content):
    configured(monkeypatch)
    monkeypatch.setattr(ai.httpx, "post", lambda *args, **kwargs: response(content))
    adapter = ai.DeepSeekAdapter()
    with pytest.raises(ai.AIInvalidOutput):
        adapter.generate_solutions(baseline())
    assert adapter.last_metrics.error_class == "AI_OUTPUT_INVALID"


def test_deepseek_timeout_is_normalized(monkeypatch):
    configured(monkeypatch)
    request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("timed out", request=request)

    monkeypatch.setattr(ai.httpx, "post", timeout)
    adapter = ai.DeepSeekAdapter()
    with pytest.raises(ai.AITimeout):
        adapter.generate_solutions(baseline())
    assert adapter.last_metrics.error_class == "AI_TIMEOUT"


@pytest.mark.parametrize("status,error", [(401, ai.AIAuthError), (429, ai.AIRateLimited)])
def test_deepseek_auth_and_rate_limit_are_normalized(monkeypatch, status, error):
    configured(monkeypatch)
    monkeypatch.setattr(ai.httpx, "post", lambda *args, **kwargs: response("{}", status, headers={"x-request-id": "error-request"}))
    adapter = ai.DeepSeekAdapter()
    with pytest.raises(error):
        adapter.generate_solutions(baseline())
    assert adapter.last_metrics.error_class == error.code
    assert adapter.last_metrics.provider_request_id == "error-request"


def test_deepseek_unknown_requirement_reference_is_rejected(monkeypatch):
    configured(monkeypatch)
    data = json.loads(valid_solution_json())
    data["alternatives"][0]["requirement_coverage"][0]["requirement_revision_id"] = "rr_unknown"
    monkeypatch.setattr(ai.httpx, "post", lambda *args, **kwargs: response(json.dumps(data)))
    adapter = ai.DeepSeekAdapter()
    with pytest.raises(ai.AIInvalidOutput):
        adapter.generate_solutions(baseline())
    assert adapter.last_metrics.error_class == "AI_OUTPUT_INVALID"


def test_deepseek_domain_repair_is_bounded(monkeypatch):
    from tests.test_phase3_ai_contract import execution_baseline, valid_output
    configured(monkeypatch);adapter=ai.DeepSeekAdapter();calls=[]
    def structured(*args,**kwargs):
        calls.append(1)
        adapter.last_metrics=ai.AIRequestMetrics("deepseek","deepseek-v4-pro",input_tokens=10,output_tokens=5,total_tokens=15,latency_ms=1)
        return valid_output("unknown-ref") if len(calls)==1 else valid_output("item-1")
    monkeypatch.setattr(adapter,"_structured",structured)
    output=adapter.generate_materialization_plan(execution_baseline())
    assert output.items[0].source_delivery_item_ref=="item-1" and len(calls)==2
    assert adapter.last_metrics.total_tokens==30


def test_responses_http_failure_never_silently_falls_back_to_chat(monkeypatch):
    configured(monkeypatch);calls=[]
    def failed(url,**kwargs):
        calls.append(url)
        return response("{}",500)
    monkeypatch.setattr(ai.httpx,"post",failed)
    with pytest.raises(ai.AIUnavailable):ai.DeepSeekAdapter().generate_solutions(baseline())
    assert calls==["https://api.deepseek.com/responses"]


def test_unknown_provider_never_falls_back(monkeypatch):
    configured(monkeypatch)
    adapter = ai.adapter_for("not-a-provider")
    assert isinstance(adapter, ai.InvalidProviderAdapter)
    with pytest.raises(ai.AIProviderInvalid):
        adapter.generate_solutions(baseline())
