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
        "choices": [{"message": {"content": content}}],
        "usage": usage or {
            "prompt_tokens": 100,
            "prompt_cache_hit_tokens": 40,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    }
    return httpx.Response(status, json=body, headers=headers, request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"))


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
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["json"]["thinking"] == {"type": "enabled"}
    assert captured["json"]["reasoning_effort"] == "high"
    assert "JSON_SCHEMA=" in captured["json"]["messages"][0]["content"]
    assert adapter.last_metrics.provider == "deepseek"
    assert adapter.last_metrics.model == "deepseek-v4-pro"
    assert adapter.last_metrics.cache_hit_tokens == 40
    assert adapter.last_metrics.total_tokens == 150
    assert adapter.last_metrics.provider_request_id == "deepseek-request-1"


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


def test_unknown_provider_never_falls_back(monkeypatch):
    configured(monkeypatch)
    adapter = ai.adapter_for("not-a-provider")
    assert isinstance(adapter, ai.InvalidProviderAdapter)
    with pytest.raises(ai.AIProviderInvalid):
        adapter.generate_solutions(baseline())
