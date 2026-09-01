# Process log — how this was built, and who decided what

This project was built in paired sessions between a human (reviewing, steering,
testing) and Claude Code (writing code, running evals, doing analysis). The task
brief asks what was delegated, what was reviewed or rewritten, and where the human
pushed back — this file is that record, kept as we went.

## The workflow

- **Plan first**: we read the brief and dataset together, agreed a design in
  conversation, and wrote it into `CLAUDE.md` (rules the agent must follow) and
  `PLAN.md` (build steps + status, so any future session can pick up mid-stream).
- **One branch per step, PR per branch**: the agent implemented and pushed; the
  human reviewed on GitHub, with the Codex review bot as a second reviewer. The
  agent was explicitly forbidden from merging (later delegated once trust was
  established — which promptly produced the one real mess of the project, see below).
- **Eval-driven iteration**: every prompt change was justified by a mismatch
  analysis from the previous full run, and verified by a fresh full run.

## Where the human changed the AI's proposal

1. **"Why a CLI? Ops teams won't use a terminal."** The AI proposed a CLI-first
   pipeline with the UI as a stretch goal. The human pointed out the user is a
   clinic ops team; the product became upload → side-by-side review UI, with the
   eval as an internal tool. This reframing shaped everything after it.

2. **Explicit pipeline stages + tests.** The AI had validation as an optional
   bolt-on. The human required the `ingest → process → validate → output` structure
   as first-class stages with clean interfaces, plus unit tests on the pure logic.
   Validation being first-class is why the flag layers ended up measurable.

3. **Dataset must never reach GitHub.** After the first push, the human required
   the provided files be kept out of the repo. The repo was rebuilt in a clean
   folder with `data/` gitignored, and the original repo deleted and recreated so
   no dataset bytes exist anywhere in history.

4. **The hardcoding challenge.** When the AI claimed the architecture was "80%
   ready" for multiple specialties, the human asked what the 20% was — and then
   "the demo fails for anyone outside the specialty" pushed the schema registry
   (schemas as config + generic fallback + routing) into scope. This was the best
   scope change of the project.

5. **Model choices.** Claude-for-extraction + OpenAI-for-validation was the human's
   idea from the start. The human also: swapped the stale `gpt-4o` for
   `gpt-5.6-terra`, supplied the `responses.parse(text_format=...)` pattern that
   simplified the cross-check code, and asked for the Sonnet-vs-Opus comparison
   that turned the model choice from an assumption into a measurement.

6. **Guardrails scrutiny.** "Have we put sufficient guardrails — if you can't find
   information, don't guess?" prompted the fabrication analysis (78% omissions /
   20% wrong values / 2% empty-truth assertions, zero invented facts) and two new
   prompt rules (illegible → empty + disclosed; placeholder text is not a value).
   Accuracy went *up* (84.5% → 84.9%) while assertions-on-empty dropped 7 → 3.

7. **UI feedback from actual testing.** The human test-drove the app and asked:
   where are the cross-check results, and move the download button up. That
   surfaced a real cost bug (the GPT cross-check re-ran on every widget
   interaction — now cached) and made the cross-model results a visible summary.

## Where the AI pushed back or flagged risk

- **Validation flags, never overwrites** — proposed early and defended throughout:
  a second model's "correction" can be wrong; flags preserve accuracy and put the
  human in the loop.
- **Don't game unwinnable fields** — `language`/`ethnicity` are absent from the
  narrative letters; guessing "English" would score points and violate the
  no-invention principle. Declined, documented as ceiling instead.
- **Deferred N-schema routing** — Codex suggested routing across all registered
  schemas; with two schemas that's speculative machinery. Deferred to next steps,
  stated openly on the PR.
- **Opus won't help** — predicted before the comparison ran, on the grounds that
  the misses were dataset damage, not capability. The measurement confirmed it.

## What review caught (human + Codex)

Two rounds of Codex review found five real issues the AI fixed: an upload-filename
path traversal (P1), failed extractions inflating the accuracy denominator — twice,
the second time because the first fix still let empty-truth fields "match" (P1),
an OpenAI SDK version floor too low for the API used (P2), and a routing
discriminator that could silently default and misroute (P2). One suggestion was
consciously deferred rather than silently ignored.

## Honest mistakes along the way

- The first push briefly put the dataset on GitHub (fixed by repo delete/recreate).
- An eval run was piped through `tail`, hiding all progress for 8 minutes.
- `referral-hzq.png` failed silently for one full eval round (image over the API
  size cap) — caught because the eval scores failures instead of skipping them.
- The comments/investigations prompt rules regressed each other once before
  settling (81.7 → 82.8 with a comments crash → 83.5 → 84.5 → 84.9).
- The delegated stacked-merge raced GitHub's branch retargeting and scattered the
  merges across bases; recovered from the stack tip in one merge. Sequential
  stacked PRs + automation need a wait-for-retarget between merges.

## Experiments that didn't make the cut

- **Bigger models** (asked by the human): Opus 5 scored 84.2%, Opus 4.8 83.6%,
  GPT-5.6 Terra 82.1% — vs Sonnet 5's 84.9%, all failing on the same damaged
  files. Kept the cheap model; recorded the comparison in the README.
- **Few-shot exemplar** (proposed by the AI, tested at the human's suggestion):
  a synthetic worked letter+record in the prompt, built contamination-safe
  (fictional patient — using an eval letter would be training on the test set),
  with a keep threshold of +1.0pt agreed before running. Result: 84.5%, within
  noise of baseline — the boundary conventions it teaches were already captured
  by the description tuning. Discarded per the pre-agreed rule.
- **Tick-box reading hint** (the human noticed demographics appear as checkbox
  rows on the proforma scans): a targeted prompt hint, re-tested on exactly the
  14 image-type language/ethnicity misses — zero new wins; where the row is
  legible the model already reads it without the hint. Discarded.

Three independent negative results (models, few-shot, checkbox hint) all point
the same way: the remaining error is document damage, not prompting — so the
next levers are image preprocessing and checksums.

## Timeline of accuracy

| Round | Change | Accuracy |
|---|---|---|
| 1 | First live run, no tuning | 81.7% |
| 2 | Trust mapping, sex inference, pathway closed set, list rules | 82.8% |
| 3 | Comments/boilerplate separation, discussed_with_patient signal | 83.5% |
| 4 | Suspicion-statement exclusion, crop detection, required fields | 84.5% |
| 5 | Anti-guessing rules (illegible → empty, placeholders rejected) | **84.9%** |
