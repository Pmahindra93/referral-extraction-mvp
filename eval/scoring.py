"""Scoring rules: how extracted records are compared to ground truth.

Accuracy definition (documented for the README):
- Every ground-truth field is one comparison; fbc counts as its 5 sub-fields.
- Scalars: normalized exact match (trim, collapse whitespace, case-insensitive,
  trailing punctuation stripped). Digit fields (NHS number, UBRN, phones) also
  ignore internal spaces/hyphens so formatting differences don't count as errors.
- Booleans: exact match.
- Lists (symptoms, myeloma_features): compared as sets of normalized items —
  order doesn't matter, content does.
- Overall % = matched comparisons / total comparisons across all files.
"""

import re

DIGIT_FIELDS = {"nhs_number", "ubrn", "home_telephone", "mobile", "practice_telephone"}
LIST_FIELDS = {"symptoms", "myeloma_features"}


def normalize(value, field: str = "") -> object:
    if isinstance(value, str):
        text = re.sub(r"\s+", " ", value).strip().lower().rstrip(".,;:")
        if field in DIGIT_FIELDS:
            text = re.sub(r"[\s\-]", "", text)
        return text
    return value


def field_matches(field: str, expected, actual) -> bool:
    if field in LIST_FIELDS:
        expected_set = {normalize(v) for v in (expected or [])}
        actual_set = {normalize(v) for v in (actual or [])}
        return expected_set == actual_set
    return normalize(expected, field) == normalize(actual, field)


def compare_record(truth: dict, extracted: dict) -> dict:
    """Return {comparison_name: {'match': bool, 'expected': ..., 'actual': ...}}."""
    results = {}
    for field, expected in truth.items():
        if field == "file":
            continue
        if field == "fbc":
            for sub, sub_expected in expected.items():
                sub_actual = (extracted.get("fbc") or {}).get(sub, "")
                results[f"fbc.{sub}"] = {
                    "match": field_matches(sub, sub_expected, sub_actual),
                    "expected": sub_expected,
                    "actual": sub_actual,
                }
            continue
        actual = extracted.get(field, "")
        results[field] = {
            "match": field_matches(field, expected, actual),
            "expected": expected,
            "actual": actual,
        }
    return results
