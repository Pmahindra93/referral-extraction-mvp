# Referral Letter Extraction — MVP

A prototype for a Healthtech venture: it reads GP referral letters (typed text, Word
docs, PDFs, photos, scanned faxes) and produces the structured record a clinic ops
team currently types in by hand — with review flags wherever a human should look
before trusting a value.

**Measured accuracy: 84.9%** (1,854 / 2,184 fields) against the provided ground-truth
dataset of 56 NHS two-week-wait haematology referrals. Details and honest caveats
below.

## Quick start (bring your own keys)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

1. Create `env.local` in the project root (it's gitignored):
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   OPENAI_API_KEY=sk-...        # optional — enables the cross-model check
   ```
2. Place the dataset (not committed to this repo) at:
   ```
   data/referral-files/           # the 56 referral letters
   data/output-true-values.json   # ground truth
   ```
3. Run things:
   ```bash
   streamlit run app.py       # the review UI
   python -m eval.run         # accuracy vs ground truth (--limit N, --no-cache)
   pytest                     # 34 unit tests (pure logic only, no API calls)
   ```

Extractions are cached in `.cache/` keyed by (model, schema, filename), so re-runs
are free. `CLAUDE_MODEL=claude-opus-5 python -m eval.run` swaps the model for a run.

## What it does

**The UI** (`app.py`): upload one or more referral letters → the pipeline extracts →
review screen with the original letter on the left and the editable extracted fields
on the right. Fields that need a human get a 🚩 with the reason. Damaged documents
(cropped scans, illegible faxes) get a warning banner. An optional toggle runs a
second, independent model (GPT) and flags any field the two models disagree on.
Corrected records download as JSON.

**The eval** (`eval/`): runs the whole dataset and reports overall %, per-field %,
and per-file misses — the tool we used to iterate the prompt where it was actually
failing.

## Architecture

```
file → ingest → process → validate → output
         │         │          │         └─ record + review flags + needs_review
         │         │          └─ 3 layers: triage guards, format checks,
         │         │             cross-model disagreement (all FLAG, never overwrite)
         │         └─ ONE Claude call, structured output pinned to the schema
         └─ txt/docx read · pdf native · png/jpg (auto-recompressed) · heic → jpeg
```

Design choices worth knowing:

- **One well-prompted call, not an agent.** Extraction of explicitly-stated fields
  doesn't benefit from multi-step orchestration; it benefits from a precise schema
  and precise rules. Structured output (tool use) guarantees valid JSON every time.
- **Schemas are config, not code** (`schemas/*.json`). Each file fully describes a
  document type: fields, types, format patterns, critical flags, UI grouping, domain
  prompt rules. The pydantic model, LLM tool schema, system prompt, and validators
  are all generated from it. Adding a new specialty is a config file. Two ship today:
  the full haematology 2WW proforma (35 fields) and a generic cross-specialty
  referral schema.
- **Routing, not rejection.** A letter that isn't a haematology 2WW referral falls
  back to the generic schema and still yields a useful record; a document that isn't
  a referral at all gets a "needs human triage" stop instead of confidently wrong data.
- **Validation flags, never edits.** No automated layer changes an extracted value.
  The failure mode is designed to be "asks a human", not "confidently wrong".

## The accuracy number, honestly

**Scoring** (our definition, documented in `eval/scoring.py`): every ground-truth
field is one comparison (the FBC blood panel counts as its five sub-fields — 39 per
letter). Scalars are normalized exact match (case, whitespace, trailing punctuation);
digit fields (NHS number, UBRN, phones) additionally ignore internal spacing; lists
compare as sets. Failed extractions score zero on every field.

**Where the missing 15% lives** — we classified every miss:

| Class | Share of errors | Nature |
|---|---|---|
| Omissions (model said nothing, truth has a value) | 78% | Safe — empty critical fields are flagged |
| Wrong values | 20% | Mostly OCR slips on low-quality scans |
| Asserted where truth is empty | 2% | 3 cases, all tick-box reads on damaged scans that already carry a document-damage flag |

**Zero fabricated facts** — no invented names, numbers, or findings in 2,184 fields.
Two ground-truth fields (`language`, `ethnicity`) are provably absent from the
narrative-style letters, and several scans are physically cropped — no extraction
system can recover information that isn't in the document. The practical ceiling on
this eval is roughly 90%; accuracy on information actually present in readable
documents is comfortably in the range of published human chart-abstraction accuracy
(85–95%).

**Model choice is measured, not assumed:**

| Model | Accuracy | Price (in/out per MTok) |
|---|---|---|
| **Claude Sonnet 5** (default) | **84.9%** | $2 / $10 |
| Claude Opus 5 | 84.2% | $5 / $25 |
| Claude Opus 4.8 | 83.6% | $5 / $25 |
| GPT-5.6 Terra | 82.1% | $2 / $12 |

All four fail on the same handful of damaged files. Further gains come from
document quality handling, not model spend — so the cheap, fast model wins.
(Fairness caveat: the prompt was tuned against Sonnet's mistakes, so the
cross-vendor gap would likely narrow with terra-specific tuning. Terra's
independent 82% is also exactly what makes it useful as the disagreement
detector in the cross-model check: strong enough to be meaningful, different
enough that its errors don't correlate with Claude's.)

**The safety net is measured too.** Format checks catch structural junk; the
cross-model check catches ambiguous reads (verified live: a misread surname, a
pathway confusion); the crop detector fires on all three damaged scans in the
dataset. Every catastrophically-scoring file arrives flagged — which is the number
that makes a human-review workflow safe, and the real point of the product: the
comparison isn't *AI vs human accuracy*, it's *(AI + 30-second review)* vs
*(human + 5 minutes of typing)*.

## Scope decisions

**In**: six file formats, the full 2WW haematology proforma, a generic fallback
schema with routing, three-layer validation, review UI with editing and export,
eval harness, guardrails against guessing (verbatim-only rules, placeholder-text
rejection, illegibility disclosure — with two explicitly scoped inference
exceptions: sex from title, NHS trust from hospital name).

**Out, deliberately** (per the brief): auth, deployment, production error handling,
PII/data governance (the dataset is synthetic; a real deployment needs a DPIA,
UK-hosted or BAA-covered inference, and audit logging before touching patient data).
Note one deliberate demo-only default: the cross-model check is ON by default, which
sends letter content to two providers (Anthropic and OpenAI); a real deployment
would gate that behind the clinic's data-processing agreements.

## What I'd do next

1. **Document-quality triage before extraction** — detect cropped/blurry scans up
   front and request a re-scan; that's where the remaining error actually lives.
2. **Per-field confidence** from the model, so review effort ranks by risk.
3. **More specialties as config** — cardiology/dermatology 2WW are each an
   afternoon's schema file, plus a classify-then-pick router across all registered
   schemas (the current router handles two).
4. **Batch intake** — inbox/fax-gateway ingestion with the Batch API (50% cheaper),
   instead of manual upload.
5. **Measure the review workflow, not just the model** — time-per-letter and
   errors-caught-in-review with real ops users; that's the metric the business runs on.

## How this was built

Built in paired sessions with Claude Code (Anthropic's CLI agent), with
GitHub PRs per step reviewed by a human + Codex review bot. The full decision log —
including what the human changed about the AI's proposals and what the AI pushed
back on — is in [PROCESS.md](PROCESS.md). Project rules the agent worked under are
in [CLAUDE.md](CLAUDE.md).
