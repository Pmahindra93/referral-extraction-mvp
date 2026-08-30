# Build Plan

Working plan for the referral-extraction MVP. Read `CLAUDE.md` first for architecture and
rules. Tick items as they land; each step gets its own branch, merged to `main` when working.

## Agreed design (summary)

- Four-stage pipeline: **ingest → process → validate → output**, each its own module.
- Extraction: one Claude structured-output call per letter, schema = ground-truth fields.
- Validation flags fields for review (format checks + optional OpenAI cross-check);
  it never overwrites Claude's values.
- Eval script scores all 56 files vs `output-true-values.json`: overall %, per-field %,
  per-file misses. Scoring: normalized exact match for scalars, set comparison for lists,
  nested comparison for fbc.
- Streamlit UI: upload → extract → side-by-side review (letter | editable fields,
  flags highlighted) → export JSON.
- Unit tests on pure logic only (ingest format handling, eval normalization). No LLM tests.
- BYOK via `env.local` (gitignored).

## Steps

- [x] **Step 0 — Setup**: git repo, GitHub remote, `.gitignore`, `env.local`, `CLAUDE.md`, `PLAN.md`
- [ ] **Step 1 — Scaffold** (`step-1-scaffold`): package layout, `requirements.txt`,
      env loading, schema definition (pydantic or dict) matching ground truth
- [ ] **Step 2 — Ingest** (`step-2-ingest`): txt/docx/pdf/png/jpg/heic → Claude-ready
      content blocks; unit test for format routing + heic conversion
- [ ] **Step 3 — Process** (`step-3-process`): Claude extraction call with structured
      output; disk cache keyed by filename
- [ ] **Step 4 — Eval** (`step-4-eval`): scoring script over all 56 files; iterate the
      extraction prompt on per-field failures until accuracy is strong; unit test for
      normalization/scoring
- [ ] **Step 5 — Validate** (`step-5-validate`): format checks (dates, NHS number,
      postcode); optional OpenAI cross-model disagreement flags
- [ ] **Step 6 — UI** (`step-6-ui`): Streamlit upload + review screen + JSON export
- [ ] **Step 7 — README**: architecture, BYOK setup, accuracy result, decisions,
      what I'd do next

## Status / notes

- Dataset: 56 files in `data/referral-files/` (8 txt, 8 docx, 16 pdf, 10 png, 10 jpg,
  4 heic). All are NHS 2WW haematology referrals to Homerton. The `data/` folder is
  gitignored — provided files must never be pushed to GitHub.
- Accuracy number to report comes from Step 4's final run.
- Keys: user fills `env.local` manually.
