"""Unit tests for the schema registry (config -> model/prompt/rules generation)."""

import json

import pytest

from pipeline.config import GROUND_TRUTH_PATH
from pipeline.process import build_system_prompt
from pipeline.registry import get_schema, list_schemas

TRIAGE_FIELDS = {"document_type", "additional_findings"}


def test_both_schemas_are_registered():
    assert {"haematology_2ww", "generic_referral"} <= set(list_schemas())


def test_unknown_schema_raises_with_available_names():
    with pytest.raises(ValueError, match="haematology_2ww"):
        get_schema("cardiology_2ww")


@pytest.mark.skipif(not GROUND_TRUTH_PATH.exists(), reason="local data/ not present")
def test_haematology_model_matches_ground_truth_exactly():
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text())
    truth_keys = set().union(*[set(r) for r in ground_truth]) - {"file"}
    model_keys = set(get_schema("haematology_2ww").model.model_fields) - TRIAGE_FIELDS
    assert model_keys == truth_keys


def test_triage_fields_injected_into_every_schema():
    for name in list_schemas():
        schema = get_schema(name)
        assert TRIAGE_FIELDS <= set(schema.model.model_fields)
        assert schema.groups["Triage"] == ["document_type", "additional_findings"]


def test_nested_object_field_builds():
    record = get_schema("haematology_2ww").model()
    assert record.fbc.wbc == ""


def test_format_rules_and_criticals_come_from_config():
    schema = get_schema("generic_referral")
    assert "date_of_birth" in schema.format_rules
    assert "reason_for_referral" in schema.critical_fields


def test_prompt_is_generated_from_schema_config():
    haem, generic = get_schema("haematology_2ww"), get_schema("generic_referral")
    assert "haematology" in build_system_prompt(haem)
    assert "any specialty" in build_system_prompt(generic)
    assert "additional_findings" in build_system_prompt(generic)
