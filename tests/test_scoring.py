"""Unit tests for eval normalization and comparison logic (pure, no API)."""

from eval.scoring import compare_record, field_matches, normalize


def test_normalize_whitespace_and_case():
    assert normalize("  Dr  Naveen   Malik ") == "dr naveen malik"


def test_digit_fields_ignore_internal_spacing():
    assert field_matches("nhs_number", "999 451 0533", "9994510533")
    assert field_matches("ubrn", "5710-8264-2540", "5710 8264 2540")


def test_non_digit_fields_keep_internal_spacing_distinct():
    assert not field_matches("surname", "Ben nett", "Bennett")


def test_lists_compare_as_sets():
    assert field_matches("symptoms", ["Itching", "Abdominal pain"],
                         ["abdominal pain", "Itching"])
    assert not field_matches("symptoms", ["Itching"], ["Itching", "Fever"])


def test_booleans_exact():
    assert field_matches("myeloma", True, True)
    assert not field_matches("myeloma", True, False)


def test_compare_record_flattens_fbc_and_skips_file():
    truth = {
        "file": "x.txt",
        "surname": "Bennett",
        "fbc": {"wbc": "3.4", "hb": "102"},
    }
    extracted = {"surname": "bennett", "fbc": {"wbc": "3.4", "hb": "101"}}
    results = compare_record(truth, extracted)
    assert set(results) == {"surname", "fbc.wbc", "fbc.hb"}
    assert results["surname"]["match"] and results["fbc.wbc"]["match"]
    assert not results["fbc.hb"]["match"]


def test_missing_field_counts_as_mismatch():
    results = compare_record({"file": "x", "surname": "Bennett"}, {})
    assert not results["surname"]["match"]
