"""Validate stage: flag fields for human review. NEVER changes extracted values.

Two layers:
1. Format checks (pure, free, always on): dates, NHS number, UBRN, postcode,
   sex, discussed_with_patient.
2. Cross-model check (optional, needs OPENAI_API_KEY): GPT independently extracts
   the same letter; fields where the two models disagree are flagged.
"""

import json
import re
from pathlib import Path

from eval.scoring import field_matches
from pipeline import config
from pipeline.schema import EXTRACTION_JSON_SCHEMA, ReferralRecord

_FORMAT_RULES = {
    "date_of_birth": (r"^\d{2}/\d{2}/\d{4}$", "expected DD/MM/YYYY"),
    "referral_date": (r"^\d{2}/\d{2}/\d{4}$", "expected DD/MM/YYYY"),
    "nhs_number": (r"^\d{3} \d{3} \d{4}$", "expected 'XXX XXX XXXX'"),
    "ubrn": (r"^\d{4}-\d{4}-\d{4}$", "expected 'XXXX-XXXX-XXXX'"),
    "postcode": (r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", "not a valid UK postcode"),
    "practice_postcode": (r"^[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}$", "not a valid UK postcode"),
    "sex": (r"^[MF]$", "expected 'M' or 'F'"),
    "discussed_with_patient": (r"^[YN]$", "expected 'Y' or 'N'"),
}

_CRITICAL_FIELDS = ["nhs_number", "date_of_birth", "surname", "suspected_pathway"]


def format_flags(record: ReferralRecord) -> dict[str, str]:
    """Pure format checks. Returns {field: reason}."""
    flags = {}
    data = record.model_dump()
    for field, (pattern, reason) in _FORMAT_RULES.items():
        value = data[field]
        if value and not re.match(pattern, value):
            flags[field] = f"{reason} (got '{value}')"
    for field in _CRITICAL_FIELDS:
        if not data[field]:
            flags[field] = "critical field is empty — check the letter"
    return flags


def cross_model_flags(path: Path, record: ReferralRecord) -> dict[str, str]:
    """Independent GPT extraction; flag fields where the two models disagree.

    Flags only — Claude's values are never overwritten. Returns {} if no
    OPENAI_API_KEY is configured.
    """
    if not config.OPENAI_API_KEY:
        return {}
    other = _openai_extract(path)
    flags = {}
    ours = record.model_dump()
    for field, our_value in ours.items():
        if field == "fbc":
            for sub, our_sub in our_value.items():
                their_sub = (other.get("fbc") or {}).get(sub, "")
                if not field_matches(sub, our_sub, their_sub):
                    flags[f"fbc.{sub}"] = f"second model read '{their_sub}'"
            continue
        their_value = other.get(field, "")
        if not field_matches(field, our_value, their_value):
            flags[field] = f"second model read '{their_value}'"
    return flags


def _openai_extract(path: Path) -> dict:
    """Minimal GPT extraction of the same letter, reusing ingested content."""
    from openai import OpenAI

    from pipeline.ingest import ingest
    from pipeline.process import SYSTEM_PROMPT

    content = []
    for block in ingest(path):
        if block["type"] == "text":
            content.append({"type": "input_text", "text": block["text"]})
        elif block["type"] == "image":
            data_url = f"data:{block['source']['media_type']};base64,{block['source']['data']}"
            content.append({"type": "input_image", "image_url": data_url})
        elif block["type"] == "document":
            content.append({
                "type": "input_file",
                "filename": path.name,
                "file_data": f"data:application/pdf;base64,{block['source']['data']}",
            })
    content.append({"type": "input_text", "text": "Extract the referral data from this letter."})

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    schema = {**EXTRACTION_JSON_SCHEMA, "additionalProperties": False}
    schema["required"] = list(schema["properties"])
    response = client.responses.create(
        model=config.OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
        input=[{"role": "user", "content": content}],
        text={
            "format": {
                "type": "json_schema",
                "name": "referral_record",
                "schema": schema,
                "strict": False,
            }
        },
    )
    return json.loads(response.output_text)


def validate(path: Path, record: ReferralRecord, cross_check: bool = False) -> dict[str, str]:
    """All review flags for one extracted record: {field: reason}."""
    flags = format_flags(record)
    if cross_check:
        for field, reason in cross_model_flags(path, record).items():
            flags.setdefault(field, reason)
    return flags
