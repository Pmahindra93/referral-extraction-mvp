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
- [x] **Step 1 — Scaffold** (PR #1): package layout, `requirements.txt`, env loading,
      pydantic schema verified against ground truth (35 fields, exact match)
- [x] **Step 2 — Ingest** (PR #2): all six formats → Claude content blocks; 6 unit
      tests; all 56 dataset files ingest cleanly
- [x] **Step 3 — Process** (PR #3): Claude tool-use extraction + disk cache. NOT yet
      run against the live API (keys pending)
- [x] **Step 4 — Eval** (PR #4): scoring rules + `python -m eval.run`; 7 unit tests.
      Live accuracy run + prompt iteration still TO DO once keys land
- [x] **Step 5 — Validate** (PR #5): format checks (4 tests) + optional GPT
      cross-model disagreement flags (flags only, never overwrites)
- [x] **Step 6 — UI** (PR #6): Streamlit upload + tabbed side-by-side review + JSON
      export; headless AppTest render passes
- [ ] **Step 7 — README**: architecture, BYOK setup, accuracy result, decisions,
      what I'd do next. Blocked on the live eval number.

## Next session: start here

1. User puts keys in `env.local` (gitignored).
2. `.venv/bin/python -m eval.run --limit 3` — sanity-check the extraction end to end.
3. Full run `python -m eval.run`, then iterate the prompt in `pipeline/process.py`
   on the worst fields from `outputs/eval-report.json` (use `--no-cache` after
   prompt changes).
4. Try the UI: `streamlit run app.py`.
5. Write README (Step 7) with the final accuracy number.
6. PRs #1–#6 are stacked (each targets the previous branch); user reviews and
   merges on GitHub — never merge for them.

## Status / notes

- Dataset: 56 files in `data/referral-files/` (8 txt, 8 docx, 16 pdf, 10 png, 10 jpg,
  4 heic). All are NHS 2WW haematology referrals to Homerton. The `data/` folder is
  gitignored — provided files must never be pushed to GitHub.
- Accuracy number to report comes from Step 4's final run.
- Keys: user fills `env.local` manually.
