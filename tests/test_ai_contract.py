import pytest

from app.ai import (
    AIContextIncomplete, AIGroundingInsufficient, AIInvalidOutput, AITimeout, AIUnavailable,
    ContextInput, DisabledAdapter, FakeAdapter,
)


def context():
    return ContextInput("Portal", "Build portal", 1, [{"id": "ctx_1", "title": "Brief",
        "content": "Authenticated customers can view invoices and submit support requests."}])


def test_valid_structured_output_and_grounding():
    output = FakeAdapter().generate(context())
    assert output.candidates
    assert output.candidates[0].source_context_item_ids == ["ctx_1"]
    assert output.candidates[0].acceptance_criteria


@pytest.mark.parametrize("mode,error", [
    ("invalid", AIInvalidOutput), ("timeout", AITimeout),
    ("unavailable", AIUnavailable), ("grounding", AIGroundingInsufficient),
])
def test_failure_contracts(mode, error):
    adapter = FakeAdapter(); adapter.mode = mode
    with pytest.raises(error): adapter.generate(context())


def test_disabled_provider_is_honest():
    with pytest.raises(AIUnavailable): DisabledAdapter().generate(context())


def test_context_incomplete_is_explicit():
    with pytest.raises(AIContextIncomplete):
        FakeAdapter().generate(ContextInput("Portal", "Build portal", 0, []))
