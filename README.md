# Referral Letter Extraction — MVP

Reads GP referral letters (txt, docx, pdf, png, jpg, heic) and produces the
structured record a clinic ops team currently types in by hand — flagging any
field a human should check before trusting it.

**Accuracy: 84.9%** (1,854 / 2,184 fields) against the provided ground truth.

## How to test it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Add keys to `env.local` (gitignored) in the project root, and place the dataset
(not committed) at `data/referral-files/` + `data/output-true-values.json`:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...        # optional: second-model cross-check
```

Then, in order:

```bash
streamlit run app.py         # try the product: upload letters from data/referral-files,
                             #   review flagged fields next to the original, export JSON
python -m eval.run           # reproduce the 84.9% (per-field breakdown + report;
                             #   --limit 5 for a quick pass)
pytest                       # 34 unit tests, no API calls needed
```

Good letters to try in the UI: `referral-ciu.txt` (clean), `referral-cyc.png`
(cropped scan — watch the damage flags), `referral-sbx.pdf` with the cross-check
toggle on (second model catches a misread surname).

## The accuracy number

`python -m eval.run` scores every ground-truth field (39 per letter, 56 letters):
normalized exact match for text, spacing-ignored for NHS numbers/phones, set
comparison for lists, failed extraction = 0. Empty-when-truth-has-a-value counts
as a miss — this is accuracy over everything asked for, not just what we filled.

**84.9% overall.** Classifying every miss: 78% are omissions (safe — flagged for
review), 20% wrong values (OCR slips on bad scans), 2% filled-on-empty (3 cases,
all on damaged scans that already carry a damage flag). Zero invented facts.

The ceiling is ~90%: some ground-truth fields (language, ethnicity) are provably
absent from the letters, and some scans are physically cropped. Tested across
models — same worst files every time, so the gap is the documents, not the model:

| Model | Accuracy | Price /MTok |
|---|---|---|
| **Claude Sonnet 5** (default) | **84.9%** | $2 / $10 |
| Claude Opus 5 | 84.2% | $5 / $25 |
| Claude Opus 4.8 | 83.6% | $5 / $25 |
| GPT-5.6 Terra | 82.1% | $2 / $12 |

## How I thought about it

**The user is a clinic ops team, not a developer** — so the product is an
upload-and-review UI, not a script. The comparison that matters isn't AI vs
human accuracy; it's *(AI + 30-second review)* vs *(human + 5 minutes of typing)*.

**Pipeline**: `ingest → process → validate → output`

- **One well-prompted Claude call**, not an agent — extraction needs a precise
  schema, not orchestration. Structured output guarantees valid JSON.
- **Schemas are config, not code** (`schemas/*.json`): each file generates the
  pydantic model, prompt, validators, and UI. A new specialty = one config file.
  Letters that aren't haematology 2WW fall back to a generic referral schema.
- **Validation flags, never edits**: format checks (dates, NHS number, postcode),
  triage guards (wrong document type, info outside the fields, cropped scans),
  and an optional second model whose disagreements become flags. The failure
  mode is "asks a human", never "confidently wrong" — measured, not asserted.

**Out of scope** (per the brief): auth, deployment, production error handling,
data governance (synthetic data — production needs a DPIA, UK-hosted inference,
audit logging; the on-by-default cross-check sends letters to two providers,
which real deployments would gate behind the clinic's DPAs).

## What I'd do next

1. **Document-quality triage** — detect cropped/blurry scans up front; that's
   where the real error lives.
2. **Checksums + registry lookups** — NHS numbers have a mod-11 check digit;
   ODS validates practices. Misreads become detectable.
3. **PDS lookup** — the NHS number (95% extracted) recovers the demographics the
   letters never state.
4. **Per-field confidence** — rank review effort by risk.
5. **More specialties** — each is one config file plus a router.
6. **Measure the review workflow** with real ops users — time per letter and
   errors caught; the metric the business runs on.
7. **An API, then FHIR** — wrap the pipeline in a small service
   (`POST /referrals` → record + flags; the UI becomes one client of it), then
   map records onto HL7 FHIR resources for EPR/e-RS integration. The UI is how
   humans trust the data; the API is how systems consume it; FHIR is how the
   NHS consumes it — same pipeline underneath all three.

---

Built in paired sessions with Claude Code; PRs reviewed by a human + Codex bot.
The full decision log — what I changed about the AI's proposals and where it
pushed back — is in [PROCESS.md](PROCESS.md). Agent rules in [CLAUDE.md](CLAUDE.md).
