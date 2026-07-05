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
emitted by `tests/integration/pipelines/test_quality_individual_extraction_open.py::test_open_v1_soft_metrics_and_error_report`)
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

## `ledger.jsonl`

Not yet built — this is Loop C's append-only record of every experiment
(accepted and rejected) per `documentation/karpathy_loop_design.md` §6. Listed
here so the layout matches the design doc ahead of time.
