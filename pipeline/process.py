"""Process stage: one Claude structured-output call per referral letter.

Uses tool-use with the ReferralRecord JSON schema so the model must return
exactly our fields. Results are cached to disk keyed by filename so re-runs
(eval iterations, UI reloads) don't re-pay the API.
"""

import json
from pathlib import Path

import anthropic

from pipeline import config
from pipeline.ingest import ingest
from pipeline.schema import EXTRACTION_JSON_SCHEMA, ReferralRecord

SYSTEM_PROMPT = """\
You are a meticulous clinical data-entry assistant for an NHS clinic ops team.
You will be given one GP referral letter (typed text, a scanned image, or a PDF).
These are urgent two-week-wait (2WW) haematology cancer referrals.

Extract the requested fields exactly as they appear in the letter. Rules:
- Copy values verbatim where possible; do not paraphrase or invent anything.
- If a field is genuinely absent, use "" (empty string), false, or [] as appropriate.
- Dates: DD/MM/YYYY. NHS number: "XXX XXX XXXX" with spaces. UBRN: "XXXX-XXXX-XXXX".
- address / practice_address: street address only, WITHOUT the postcode
  (postcode goes in its own field). Hb is a number only (no units).
- The condition flags (leukaemia, lymphadenopathy, myeloma, splenomegaly) are the
  ticked suspicion boxes on the referral; suspected_pathway is the named suspected
  condition (e.g. "myeloma", "acute leukaemia").
- symptoms and myeloma_features are lists of the individual items stated, using the
  letter's own wording (e.g. "Itching", "Bruising/Bleeding", "Renal impairment").
- discussed_with_patient: "Y" or "N".
- For scanned images, read carefully; transcribe exactly what is written."""


def _tool_definition() -> dict:
    return {
        "name": "record_referral",
        "description": "Record the structured referral data extracted from the letter.",
        "input_schema": EXTRACTION_JSON_SCHEMA,
    }


def _cache_path(file_name: str) -> Path:
    return config.CACHE_DIR / f"{file_name}.json"


def extract(path: Path, use_cache: bool = True) -> ReferralRecord:
    """Run the full ingest -> Claude extraction for one file."""
    cache_file = _cache_path(path.name)
    if use_cache and cache_file.exists():
        return ReferralRecord.model_validate_json(cache_file.read_text())

    client = anthropic.Anthropic(api_key=config.require_anthropic_key())
    content = ingest(path) + [
        {"type": "text", "text": "Extract the referral data from this letter."}
    ]
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[_tool_definition()],
        tool_choice={"type": "tool", "name": "record_referral"},
        messages=[{"role": "user", "content": content}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    record = ReferralRecord.model_validate(tool_use.input)

    config.CACHE_DIR.mkdir(exist_ok=True)
    cache_file.write_text(record.model_dump_json(indent=2))
    return record


def extract_bytes(data: bytes, file_name: str, use_cache: bool = True) -> ReferralRecord:
    """Extraction entry point for uploaded files (UI): write to a temp location first."""
    tmp_dir = config.CACHE_DIR / "uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / file_name
    tmp_path.write_bytes(data)
    return extract(tmp_path, use_cache=use_cache)
