# experiments/

Artifacts produced and consumed by the Karpathy loop — the automated
evaluate → analyze-errors → propose → verify → accept/reject cycle for the
individual-extraction pipelines. See
`documentation/karpathy_loop_design.md` for the full design and
`local-server/documentation/claudes_thoughts/individual_extraction_design_analysis.md`
for the rationale behind it.

## Layout

```
experiments/
├── reports/<run_id>.{json,md}   # error reports (§3.2) — one pair per evaluation run
├── ledger.jsonl                 # append-only experiment record (accepted + rejected) — Loop C, not yet built
└── README.md                    # this file
```

## `reports/`

Every evaluation of the individual-extraction quality corpus (currently
emitted by `tests/integration/pipelines/test_quality_individual_extraction_open.py::test_open_v1_soft_metrics_and_error_report`,
and per-variant by `scripts/quality_tournament.py` — see below)
writes a `<run_id>.json` / `<run_id>.md` pair here:

- **`<run_id>.json`** — machine-readable: per-scenario strict + soft P/R/F1,
  `candidate_recall`, `predicate_recall`, `label_accuracy`, dev/holdout means,
  and every GT triple the strict metric missed, classified by failure stage
  (`candidate_missing` → `relation_not_derived` → `label_mismatch` →
  `predicate_mismatch`) with its source sentence and the nearest actual
  output. This is the primary input to Loop C experimenter agents — the
  "look at your errors" step, precomputed.
- **`<run_id>.md`** — a short human/agent-readable digest: top failure
  classes, the 5 worst scenarios, and a handful of concrete examples.

Report files are generated artifacts (gitignored — see `.gitignore`); only
this README and the `reports/` directory itself are tracked.

## Loop B: `scripts/quality_tournament.py`

`python scripts/quality_tournament.py --pipeline individual` runs the variant
tournament (§4.2): every registered variant (see the module docstring and
`build_registry()` in that script for which variants are registered today and
why) is Loop-A-tuned on dev, then scored on the full corpus. Output:

- a per-variant error report pair in `reports/tournament_<variant>_<run_id>.{json,md}`
  (same shape as above — produced by the same `_harness/error_report.py` code);
- a scoreboard digest in `reports/tournament_<run_id>.md`, ranking variants by
  mean dev soft-F1 with strict-F1 and the §3.1 diagnostics alongside;
- a scoreboard telemetry row per variant in
  `tests/integration/fixtures/pipelines/_metrics/quality_tournament_individual_extraction.jsonl`
  (gitignored, same JSONL schema `quality_loop.py` uses).

## `ledger.jsonl`

Not yet built — this is Loop C's append-only record of every experiment
(accepted and rejected) per `documentation/karpathy_loop_design.md` §6. Listed
here so the layout matches the design doc ahead of time.
