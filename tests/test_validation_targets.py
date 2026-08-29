import pytest

from app.validation_targets import DeterministicValidationAdapter, ValidationCreateRequest, ValidationTargetCreateFailed, ValidationTargetTimeout


def request():
    return ValidationCreateRequest("val-1","project-1","binding-1","Validate ownership boundary","Verify secure customer isolation.","Cross-customer access is denied.","Security QA Lead","scope:item")


def test_validation_target_create_readback_list_and_dedup():
    adapter=DeterministicValidationAdapter();first=adapter.create_validation_item(None,request());second=adapter.create_validation_item(None,request())
    assert first.external_id==second.external_id and adapter.creates==1
    assert adapter.get_validation_item(None,"project-1","binding-1",first.external_id)==first
    assert adapter.list_project_validation(None,"project-1","binding-1")==[first]


@pytest.mark.parametrize(("mode","error"),[("timeout",ValidationTargetTimeout),("failure",ValidationTargetCreateFailed)])
def test_validation_target_failures(mode,error):
    with pytest.raises(error):DeterministicValidationAdapter(mode).create_validation_item(None,request())


def test_validation_target_missing_readback_is_explicit():
    adapter=DeterministicValidationAdapter("readback_missing");created=adapter.create_validation_item(None,request())
    assert adapter.get_validation_item(None,"project-1","binding-1",created.external_id) is None
