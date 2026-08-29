import pytest

from app.execution_targets import (
    DeterministicExternalAdapter,
    TargetCreateFailed,
    TargetCreateRequest,
    TargetTimeout,
)


def request():
    return TargetCreateRequest(
        execution_item_id="exec-1",
        project_id="project-1",
        binding_id="binding-1",
        title="Build secure invoice flow",
        description="Implement the frozen delivery item with exact lineage.",
        owner_role="Delivery Lead",
        priority="HIGH",
        milestone_ref="milestone-1",
        dependencies=[],
        idempotency_key="plan:item",
    )


def test_target_contract_create_readback_and_semantic_deduplication():
    adapter = DeterministicExternalAdapter()
    first = adapter.create_work_item(None, request())
    second = adapter.create_work_item(None, request())
    assert first.external_id == second.external_id
    assert adapter.creates == 1
    assert adapter.get_work_item(None, "project-1", "binding-1", first.external_id) == first
    updated = adapter.update_work_item(None, "project-1", "binding-1", first.external_id, {"priority":"LOW"})
    assert updated.priority == "LOW" and adapter.list_project_work(None,"project-1","binding-1") == [updated]


@pytest.mark.parametrize(
    ("mode", "error"),
    [("timeout", TargetTimeout), ("failure", TargetCreateFailed)],
)
def test_target_contract_reports_write_failures(mode, error):
    with pytest.raises(error):
        DeterministicExternalAdapter(mode).create_work_item(None, request())


def test_target_contract_reports_unconfirmed_readback():
    adapter = DeterministicExternalAdapter("readback_missing")
    created = adapter.create_work_item(None, request())
    assert adapter.get_work_item(None, "project-1", "binding-1", created.external_id) is None


def test_target_contract_surfaces_changed_and_deleted_items():
    adapter = DeterministicExternalAdapter()
    created = adapter.create_work_item(None, request())
    adapter.items[created.external_id].owner_role = "Changed Owner"
    assert adapter.get_work_item(None, "project-1", "binding-1", created.external_id).owner_role == "Changed Owner"
    del adapter.items[created.external_id]
    assert adapter.get_work_item(None, "project-1", "binding-1", created.external_id) is None
