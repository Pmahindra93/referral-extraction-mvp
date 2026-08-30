"""Unit tests for the pure validation layers (no API)."""

from pipeline.registry import get_schema
from pipeline.validate import format_flags, triage_flags

HAEM = get_schema("haematology_2ww")


def _valid_record():
    return HAEM.model(
        document_type="referral",
        surname="Bennett",
        sex="M",
        date_of_birth="07/01/1946",
        nhs_number="999 451 0533",
        postcode="E2 0AG",
        practice_postcode="E2 9LS",
        referral_date="18/05/2026",
        ubrn="5710-8264-2540",
        suspected_pathway="myeloma",
        discussed_with_patient="Y",
    )


def test_clean_record_has_no_flags():
    assert format_flags(_valid_record(), HAEM) == {}


def test_bad_formats_are_flagged():
    record = _valid_record().model_copy(update={
        "date_of_birth": "7 Jan 1946",
        "nhs_number": "9994510533",
        "postcode": "not-a-postcode",
        "sex": "Male",
    })
    flags = format_flags(record, HAEM)
    assert set(flags) == {"date_of_birth", "nhs_number", "postcode", "sex"}


def test_empty_critical_fields_are_flagged():
    record = _valid_record().model_copy(update={"surname": "", "nhs_number": ""})
    flags = format_flags(record, HAEM)
    assert "surname" in flags and "nhs_number" in flags


def test_empty_optional_fields_are_not_flagged():
    record = _valid_record().model_copy(update={"ubrn": "", "mobile": ""})
    assert format_flags(record, HAEM) == {}


def test_generic_schema_uses_its_own_rules():
    generic = get_schema("generic_referral")
    record = generic.model(document_type="referral", date_of_birth="1946-01-07")
    flags = format_flags(record, generic)
    assert "date_of_birth" in flags
    assert "reason_for_referral" in flags  # critical in the generic schema


def test_expected_referral_has_no_triage_flags():
    assert triage_flags(_valid_record(), HAEM) == {}


def test_wrong_document_type_is_flagged_for_triage():
    record = _valid_record().model_copy(update={"document_type": "discharge summary"})
    flags = triage_flags(record, HAEM)
    assert "discharge summary" in flags["document_type"]


def test_unknown_document_type_is_flagged_for_triage():
    record = _valid_record().model_copy(update={"document_type": ""})
    assert "document_type" in triage_flags(record, HAEM)


def test_additional_findings_are_flagged():
    record = _valid_record().model_copy(
        update={"additional_findings": "Penicillin allergy noted in margin"}
    )
    assert "additional_findings" in triage_flags(record, HAEM)
