# Issue #1228 — Accept Gate: Resolution Notes (Update)

## Status: ACCEPT GATE CLEARED

This supersedes the "MERGE-READY" notes committed with PR #1243. Those notes correctly
identified that the tournament accept gate had **not** actually been cleared at merge
time (cassettes were deleted, not re-recorded; no passing tournament report was
committed) — that work is now done.

## What was done (2026-09-18, post-merge)

1. **Re-recorded `individual_extraction_default` cassettes** with real LLM calls via
   `scripts/record_default_cassettes.py --record` (`google/gemini-3-flash-preview` via
   OpenRouter, phase-1 model override).
2. **Found and fixed a real bug** in `record_default_cassettes.py`: `union_scenarios()`
   only covered `INDIVIDUAL_EXTRACTION_SCENARIOS` + `DR_BOOTSTRAP_SCENARIOS` +
   `WAVE4_INFORMAL_SCENARIOS` (14 scenarios). `quality_tournament.py`'s
   `_default_cassettes_present()` guard requires cassettes for those **plus**
   `RELABELED_ARXIV_SCENARIOS` (3 more, 17 total) before it will register the `default`
   variant at all. The recorder could never produce a complete set — `default` stayed
   unregistered even after a full "successful" recording run. Fixed by adding
   `RELABELED_ARXIV_SCENARIOS` to the union; recorded the 3 missing arxiv scenarios.
3. **Ran `scripts/quality_tournament.py --pipeline individual`** — `default` and
   `default+grounding` now register and score.

## Result

| metric | this run | last verified baseline (2026-09-15) | outcome |
|---|---|---|---|
| dev strict-F1 | 0.924 | 0.917 | ✅ no regression (+0.007) |
| dev soft-F1 | 0.935 | 0.928 | ✅ no regression (+0.007) |
| candidate_recall | 0.992 | 0.992 | ✅ unchanged |
| predicate_recall | 0.970 | 0.970 | ✅ unchanged |
| label_accuracy (strict/soft) | 0.982/0.982 | 0.982 | ✅ unchanged |
| holdout strict-F1 | 0.829 | 0.829 | advisory only, never gates (thin split, 2 scenarios) — unchanged |
| holdout soft-F1 | 0.960 | 0.960 | advisory only, never gates — unchanged |

Note: the 0.917/0.928 figure (not the older 0.941/0.952) is the correct comparison
baseline — that was the last real, cassette-verified score before this PR, established
in the 09-13/14 cassette-staleness-fix session. The 0.941/0.952 numbers predate a small,
previously-accepted drift from PRs #1194/#1201/#1213 and were already not being met as
of 09-15.

**Conclusion: the span-extraction prompt changes did not regress the `default`
pipeline.** Accept gate clears. Digest:
`experiments/reports/tournament_20260918T101828Z_20877395.md`.

## Deliberately not done in this pass

- `individual_grounded_typing` (`grounded_v1`) cassettes were also deleted by this PR
  and were **not** re-recorded here. That pipeline's promotion question was already
  closed with a STAY verdict on 2026-09-15 (retrieval-for-typing underperforms
  `default`) — re-recording it is not required to clear this accept gate, and it costs
  two orders of magnitude more (~2,442 LLM calls on `claude-opus-4-7` vs. 34 calls —
  17 scenarios x 2 passes — on `gemini-3-flash-preview`). Its cassette directory does
  not exist; the tournament will print a "not registered" note for `grounded_v1`
  until/unless someone re-records it.

## Follow-up worth tracking (not fixed here)

The scenario union this PR fixed is now hand-duplicated across four places:
`record_default_cassettes.py`, `record_grounded_cassettes.py`, and both replay-scenario
lists in `quality_tournament.py`. `record_grounded_cassettes.py` already includes
`RELABELED_ARXIV_SCENARIOS` correctly, so nothing is broken today — but the next
scenario group added to `dataset_split.py` can silently desync one of these four copies
again, reproducing this exact failure mode (a "successful" recording run that still
leaves a variant unregistered). Worth defining the union once in `dataset_split.py`
(e.g. `REPLAY_SCENARIOS`) and having all four call sites import it, as a follow-up.
