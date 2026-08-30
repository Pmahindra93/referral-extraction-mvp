"""Validate stage: flag fields for human review. NEVER changes extracted values.

Three layers:
1. Triage guards (pure, always on): is this actually the document type the
   schema expects, and did the model find significant information outside the
   standard fields?
2. Format checks (pure, free, always on): patterns and critical fields come
   from the active schema's config.
3. Cross-model check (optional, needs OPENAI_API_KEY): GPT independently extracts
   the same letter; fields where the two models disagree are flagged.
"""

import re
from pathlib import Path

from pydantic import BaseModel

from eval.scoring import field_matches
from pipeline import config
from pipeline.registry import Schema, get_schema

_TRIAGE_FIELDS = ("document_type", "additional_findings")


def triage_flags(record: BaseModel, schema: Schema) -> dict[str, str]:
    """Guards against processing the wrong document or silently dropping info."""
    flags = {}
    doc_type = record.document_type.strip().lower()
    if doc_type != "referral":
        described = record.document_type or "unknown document type"
        flags["document_type"] = (
            f"model does not think this is {schema.document_description} "
            f"(read it as: '{described}') — needs human triage"
        )
    if record.additional_findings.strip():
        flags["additional_findings"] = (
            "significant information found outside the standard fields — review"
        )
    return flags


def format_flags(record: BaseModel, schema: Schema | None = None) -> dict[str, str]:
    """Pure format checks driven by the schema config. Returns {field: reason}."""
    schema = schema or get_schema()
    flags = {}
    data = record.model_dump()
    for field, (pattern, reason) in schema.format_rules.items():
        value = data[field]
        if value and not re.match(pattern, value):
            flags[field] = f"{reason} (got '{value}')"
    for field in schema.critical_fields:
        if not data[field]:
            flags[field] = "critical field is empty — check the letter"
    return flags


def cross_model_flags(
    path: Path, record: BaseModel, schema: Schema
) -> dict[str, str]:
    """Independent GPT extraction; flag fields where the two models disagree.

    Flags only — Claude's values are never overwritten. Returns {} if no
    OPENAI_API_KEY is configured.
    """
    if not config.OPENAI_API_KEY:
        return {}
    other = _openai_extract(path, schema)
    flags = {}
    ours = record.model_dump()
    for field, our_value in ours.items():
        if field in _TRIAGE_FIELDS:
            continue  # free-text triage fields; models word these differently
        if isinstance(our_value, dict):
            for sub, our_sub in our_value.items():
                their_sub = (other.get(field) or {}).get(sub, "")
                if not field_matches(sub, our_sub, their_sub):
                    flags[f"{field}.{sub}"] = f"second model read '{their_sub}'"
            continue
        their_value = other.get(field, "")
        if not field_matches(field, our_value, their_value):
            flags[field] = f"second model read '{their_value}'"
    return flags


def _openai_extract(path: Path, schema: Schema) -> dict:
    """Minimal GPT extraction of the same letter, reusing ingested content."""
    from openai import OpenAI

    from pipeline.ingest import ingest
    from pipeline.process import build_system_prompt

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
    content.append({"type": "input_text", "text": "Extract the structured data from this document."})

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.responses.parse(
        model=config.OPENAI_MODEL,
        instructions=build_system_prompt(schema),
        input=[{"role": "user", "content": content}],
        text_format=schema.model,
    )
    return response.output_parsed.model_dump()


def validate(
    path: Path,
    record: BaseModel,
    schema: Schema | None = None,
    cross_check: bool = False,
) -> dict[str, str]:
    """All review flags for one extracted record: {field: reason}."""
    schema = schema or get_schema()
    flags = {**triage_flags(record, schema), **format_flags(record, schema)}
    if cross_check:
        for field, reason in cross_model_flags(path, record, schema).items():
            flags.setdefault(field, reason)
    return flags
