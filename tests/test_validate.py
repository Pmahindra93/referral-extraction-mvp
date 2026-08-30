"""Unit tests for the pure format-check layer of validation (no API)."""

from pipeline.schema import ReferralRecord
from pipeline.validate import format_flags


def _valid_record() -> ReferralRecord:
    return ReferralRecord(
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
    assert format_flags(_valid_record()) == {}


def test_bad_formats_are_flagged():
    record = _valid_record().model_copy(update={
        "date_of_birth": "7 Jan 1946",
        "nhs_number": "9994510533",
        "postcode": "not-a-postcode",
        "sex": "Male",
    })
    flags = format_flags(record)
    assert set(flags) == {"date_of_birth", "nhs_number", "postcode", "sex"}


def test_empty_critical_fields_are_flagged():
    record = _valid_record().model_copy(update={"surname": "", "nhs_number": ""})
    flags = format_flags(record)
    assert "surname" in flags and "nhs_number" in flags


def test_empty_optional_fields_are_not_flagged():
    record = _valid_record().model_copy(update={"ubrn": "", "mobile": ""})
    assert format_flags(record) == {}
