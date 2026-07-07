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
├── ledger.py                    # read/write helpers + CLI for ledger.jsonl (Loop C)
├── ledger.jsonl                 # append-only experiment record (accepted + rejected)
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

Each run also scores every variant's tuned config against the Wave 1 DR
bootstrap scenarios (`dataset_split.py`'s `DR_BOOTSTRAP_SCENARIOS`,
`karpathy_loop_dr_ontology_design.md` §5) as a **separate, always-reported
diagnostic pass**: a `bootstrap` row per variant in the same scoreboard
telemetry file (`fixture_id="bootstrap"`), and its own section in the
`tournament_<run_id>.md` digest. This pass is a sanity check — real,
independently-produced ground truth graded against the imported DR spec, too
thin (4 scenarios covering 4 of 12 layers) to holdout-split or optimize
against — and is never mixed into `dev`/`holdout` aggregation, the error
report's `failure_stage_counts` (Loop C target selection), or the §6 accept
gate: `acceptGate` in `.claude/workflows/karpathy-loop.js` takes only `dev`
and `holdout` as arguments and structurally cannot read bootstrap metrics.

## Loop C: `.claude/workflows/karpathy-loop.js`

`documentation/karpathy_loop_design.md` §4.3/§4.4 — the agent-in-the-loop
refinement cycle. Each invocation of the Workflow runs exactly **one**
iteration:

1. **Evaluate** — runs Loop B (`quality_tournament.py`) and reads back the
   incumbent's scoreboard + error report, including the incumbent's Wave 1
   bootstrap diagnostics (reported as `bootstrap` for visibility and the
   ledger — see the Loop B section above — never as an input to any decision
   below).
2. **Select** — reads `ledger.jsonl` for hypotheses already rejected, then
   ranks the incumbent's failure classes (`failure_stage_counts` in the error
   report) by GT-triple count and maps the top ones to hypotheses from the
   seeded backlog (design doc §7 items 1–6; item 0, the live-LLM-path bugfix,
   already landed in Phase 2).
3. **Experiment** — fans out one experimenter agent per selected hypothesis,
   each in its own git worktree (`isolation: 'worktree'`), each implementing
   exactly one change and reporting a Loop-A-tuned dev/holdout evaluation of
   it.
4. **Verify** — an adversarial agent checks each candidate for gate integrity
   (no edits to the harness/GT fixtures/split/ledger, tests reproduce, single
   change, diff matches the stated hypothesis).
5. **Decide** — the accept gate (design doc §6: dev soft-F1 improves by
   > 0.005, dev strict-F1 doesn't regress, holdout strict-F1 doesn't collapse
   by more than 0.02) is applied to the best verified candidate. Accepted →
   merge into `experiment/karpathy-loop`, refresh cassettes if the change
   touched a prompt, append a ledger entry. Everything else (including a
   verified-but-not-best candidate) → discard the worktree, append a ledger
   entry with the rejection reason.

Invoke it with the `Workflow` tool, e.g. `{name: "karpathy-loop", args:
{iteration: 1}}`. Because each call is one iteration, driving the full loop
means calling it repeatedly (e.g. via `/loop`) and threading state through
`args` from the previous call's return value — see the workflow's own
`meta.whenToUse` for the exact fields (`iteration`, `consecutiveNoAccept`,
`hypothesisCount`, `integrationBranch`, `holdoutFloors`,
`maxConsecutiveNoAccept`, `cumulativeCostUsd`, `totalBudgetUsd`). The
returned `status` (`"stopped"` / `"accepted"` / `"no_accept"` / `"error"`)
and `stop` field tell the driver whether to keep iterating — stop conditions
are the holdout floors being met, three consecutive no-accept iterations
(plateau), or the cost/iteration budget in `args` being exhausted (design doc
§4.3 step 6).

Running this against the real corpus is expensive (a full Loop B tournament
plus several worktree-isolated coding agents per iteration) and is Phase 7 in
the design doc's build plan — out of scope for the infrastructure itself.

## `ledger.py` / `ledger.jsonl`

Loop C's append-only record of every experiment (accepted and rejected), per
`documentation/karpathy_loop_design.md` §8. `experiments/ledger.py` provides
the read/write helpers (`append_entry`, `read_entries`,
`rejected_hypotheses`) plus a small CLI so a Loop C sub-agent — which has
shell access but no in-process import path into this package — can record a
decision without hand-writing JSON:

```bash
# from local-server/, venv active
python experiments/ledger.py append '{"experiment_id": "12-copular", ...}'
python experiments/ledger.py rejected-hypotheses
```

The ledger is append-only by construction (`append_entry` only ever opens the
file in `"a"` mode) — rewriting or truncating it is one of the accept gate's
integrity violations (§6 item 4), enforced by the Loop C verifier agent via a
path check on `git diff`.

### Baseline resets

A `decision: "baseline_reset"` entry marks a measurement-layer or
ontology/corpus swap — e.g. the DR ontology import replacing the placeholder
3-class ontology
(`documentation/karpathy_loop_dr_ontology_design.md` §9, #1109 Phase 3).
`scripts/import_dr_ontology.py` appends one automatically on a successful
import, recording the imported `spec_version`; re-running the import against
an unchanged `spec_version` does not append a duplicate
(`record_baseline_reset_if_new`).

`rejected_hypotheses()` (and any future ledger read that feeds a loop
decision) is scoped through `entries_since_last_baseline_reset()`, which
excludes every entry recorded before the most recent checkpoint. This is the
mechanism — not a documented convention — behind the rule that pre-reset
dev/holdout scores never judge post-reset experiments: a hypothesis rejected
against a since-retired baseline is eligible for retry immediately after the
reset, with no manual ledger cleanup required.

```bash
# from local-server/, venv active — recording a reset manually (the DR
# import script does this for you on a spec-version change)
python experiments/ledger.py baseline-reset \
    --ontology-context dr_spec --spec-version 0.8.4 --base-commit "$(git rev-parse HEAD)" \
    'Replaced the placeholder ontology with the imported DR spec.'
```
