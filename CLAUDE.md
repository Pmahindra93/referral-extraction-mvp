# Referral Letter Extraction — MVP

Take-home task (Founders Factory, Tech & AI Lead). Time budget 2–3 hours. This is an
interview prototype: optimise for judgment, speed, and clarity — not production polish.

## What this is

A prototype for a healthtech venture: extracts structured data from GP referral letters
(NHS 2WW haematology referrals) so a clinic ops team doesn't have to type them in manually.

- Input: 56 sample letters in `data/referral-files/` (txt, docx, pdf, png, jpg, heic)
- Ground truth: `data/output-true-values.json` (~40 fields per letter) — **never modify this file**
- The `data/` folder (provided dataset + task brief) is gitignored — it must never be
  pushed to GitHub. The README tells reviewers where to place their own copy.
- Deliverables: working code, a % accuracy vs ground truth, README with reasoning

## Architecture — fixed, do not deviate without asking

Four-stage pipeline, each stage a separate module with a clean interface:

```
ingest → process → validate → output
```

1. **ingest** — file → Claude-ready content. txt read directly; docx via python-docx;
   pdf sent natively to Claude; png/jpg as vision images; heic converted to jpeg via
   pillow-heif first (Claude does not accept heic).
2. **process** — ONE well-prompted Claude call per letter with structured output pinned
   to the ground-truth schema. No multi-step agent, no chained calls.
3. **validate** — checks on the extracted record: schema/format checks (dates, NHS number,
   postcode), and optionally an independent OpenAI extraction for cross-model disagreement.
   Validation **flags** fields for human review — it never overwrites Claude's values.
4. **output** — final JSON per letter + review flags.

Plus:
- `eval/` — scores pipeline output against ground truth (per-field, per-file, overall %)
- `app.py` — Streamlit UI: upload → extract → side-by-side review (letter left, editable
  fields right, flagged fields highlighted) → export JSON

## Stack & conventions

- Python + Streamlit. One language for everything.
- Models: Claude (Anthropic API) for extraction; OpenAI optionally for cross-validation.
- Keys come from `env.local` (gitignored): `ANTHROPIC_API_KEY`, optional `OPENAI_API_KEY`.
  Never hardcode keys. BYOK — the README explains setup.
- Cache extraction results to disk (keyed by filename) so re-runs don't re-pay the API.
  Eval and UI read from cache when available.
- The extraction schema = the ground-truth fields exactly. Dates DD/MM/YYYY, NHS numbers
  as "XXX XXX XXXX", booleans for condition flags, lists for symptoms/myeloma_features,
  nested object for fbc.

## Testing

- A couple of simple unit tests on pure logic only: ingestion format handling and eval
  normalization/scoring. Do NOT write tests that call LLM APIs.
- The real quality gate is the eval script: run it after prompt changes, iterate on the
  per-field breakdown, not the overall number.

## Scope guardrails

- OUT of scope (explicitly, per the brief): auth, deployment, production-grade error
  handling, configurable schemas, PII/data-governance handling (data is synthetic).
- Don't add features beyond the agreed design. If something seems missing, ask first.
- Rough edges are fine if they're documented in the README's "what I'd do next" section.

## Workflow

- The build plan and current status live in `PLAN.md` — read it at the start of a session,
  tick items off as they're done.
- One git branch per build step (e.g. `step-2-ingest`), merged to `main` when the step works.

## Commands

- Run eval: `python -m eval.run` (or as implemented — keep it one command)
- Run app: `streamlit run app.py`
- Run tests: `pytest`
