"""Process stage: one Claude structured-output call per referral letter.

Uses tool-use with the active schema's JSON schema so the model must return
exactly that schema's fields. Prompts are generated from the schema config.
Results are cached to disk keyed by (schema, filename) so re-runs (eval
iterations, UI reloads) don't re-pay the API.

extract() pins one schema (the eval path). extract_routed() classifies first:
letters matching the default schema get the full specialty extraction; anything
else falls back to the generic referral schema.
"""

from pathlib import Path

import anthropic
from pydantic import BaseModel

from pipeline import config
from pipeline.ingest import ingest
from pipeline.registry import DEFAULT_SCHEMA, FALLBACK_SCHEMA, Schema, get_schema

_BASE_PROMPT = """\
You are a meticulous clinical data-entry assistant for an NHS clinic ops team.
You will be given one document (typed text, a scanned image, or a PDF).
You are expecting {document_description}.

First set document_type: 'referral' if the document really is what you are
expecting; otherwise briefly describe what the document actually is. If it is
not what you expected, still extract whatever fields you can.

Extract the requested fields exactly as they appear in the letter. Rules:
- Copy values verbatim where possible; do not paraphrase or invent anything.
- If a field is genuinely absent, use "" (empty string), false, or [] as appropriate.
- If something significant does not fit any field (safeguarding concerns, allergy
  warnings, DNR status, a second patient), put it in additional_findings verbatim —
  never silently drop information. Leave additional_findings empty otherwise.
- For scanned images, read carefully; transcribe exactly what is written.

{domain_prompt}"""


def build_system_prompt(schema: Schema) -> str:
    return _BASE_PROMPT.format(
        document_description=schema.document_description,
        domain_prompt=schema.domain_prompt,
    ).strip()


def _tool_definition(schema: Schema) -> dict:
    return {
        "name": "record_document",
        "description": "Record the structured data extracted from the document.",
        "input_schema": schema.json_schema,
    }


def _cache_path(file_name: str, schema: Schema) -> Path:
    return config.CACHE_DIR / f"{schema.name}--{file_name}.json"


def extract(path: Path, schema: Schema | None = None, use_cache: bool = True) -> BaseModel:
    """Run ingest -> Claude extraction for one file against one pinned schema."""
    schema = schema or get_schema(DEFAULT_SCHEMA)
    cache_file = _cache_path(path.name, schema)
    if use_cache and cache_file.exists():
        return schema.model.model_validate_json(cache_file.read_text())

    client = anthropic.Anthropic(api_key=config.require_anthropic_key())
    content = ingest(path) + [
        {"type": "text", "text": "Extract the structured data from this document."}
    ]
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=4096,
        system=build_system_prompt(schema),
        tools=[_tool_definition(schema)],
        tool_choice={"type": "tool", "name": "record_document"},
        messages=[{"role": "user", "content": content}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    record = schema.model.model_validate(tool_use.input)

    config.CACHE_DIR.mkdir(exist_ok=True)
    cache_file.write_text(record.model_dump_json(indent=2))
    return record


def is_expected_type(record: BaseModel) -> bool:
    return record.document_type.strip().lower() == "referral"


def extract_routed(path: Path, use_cache: bool = True) -> tuple[BaseModel, Schema]:
    """Specialty extraction if the letter matches the default schema; otherwise
    fall back to the generic referral schema. Returns (record, schema used)."""
    schema = get_schema(DEFAULT_SCHEMA)
    record = extract(path, schema=schema, use_cache=use_cache)
    if is_expected_type(record):
        return record, schema

    fallback = get_schema(FALLBACK_SCHEMA)
    fallback_record = extract(path, schema=fallback, use_cache=use_cache)
    if is_expected_type(fallback_record):
        return fallback_record, fallback
    # Not a referral of any kind: keep the specialty attempt (its triage flag
    # tells the reviewer what the model thinks the document is).
    return record, schema


def extract_bytes(
    data: bytes, file_name: str, use_cache: bool = True
) -> tuple[BaseModel, Schema]:
    """Routed extraction entry point for uploaded files (UI)."""
    tmp_dir = config.CACHE_DIR / "uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / file_name
    tmp_path.write_bytes(data)
    return extract_routed(tmp_path, use_cache=use_cache)
