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
│                                #   tournament_<run_id>_benchmark.json: the benchmark pass
│                                #   benchmark_<document>_<label>_<stamp>.{json,md}: a scored proposal
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

## The benchmark

Loop C's objective since 2026-11 (`documentation/karpathy_loop_design.md` §3.4): three long
documents with hand-made gold extractions under
`tests/integration/fixtures/pipelines/extraction_benchmark/` (read its README first). A run is
scored on the individuals that would reach the review queue: found F1, typed F1, core recall,
type accuracy, relationship recall, and the failure counts Loop C selects targets from.

```bash
# from local-server/, venv active
python scripts/benchmark_replay.py                    # offline: replay the cassettes, score
python scripts/benchmark_replay.py --record --spend   # record with the live LLM (cheap model)
python scripts/benchmark_replay.py --implementation find_then_type   # the other implementation

# against a running server (./dev.sh)
python scripts/extraction_benchmark.py validate
python scripts/extraction_benchmark.py load                              # gold -> datasets bench-*
python scripts/extraction_benchmark.py run --document edit_check --spend # extract with a configuration, score
python scripts/extraction_benchmark.py score --document edit_check --proposal <id>
```

`benchmark_replay.py` runs the `default` pipeline in process, each document as a source (chunked,
merged, planned), against the pinned DR spec the gold files were made for, with real embeddings
and a schema index so the class catalog offered per chunk is the one the app would offer. It
reports `not_recorded` or `stale` instead of numbers when the cassettes are missing or no longer
answer the prompts, and `failed` when the extraction itself failed with every prompt answered (a
run with a failed chunk is not scored), and exits 2. A run over some of the documents
(`--document`) is `partial` and prints each document's score without a dev or holdout mean.
Building the ontology takes about a minute.

`extraction_benchmark.py run` measures what a user gets: the server's own code, a pipeline
configuration's model and stage prompts, and a real proposal left in the review queue.

## Prerequisites to a full run

Both cassette sets must answer the current prompts. The cassette key hashes the whole prompt, so
any change to a prompt or to what feeds it (the class catalog, the predicate list, chunking, the
DR spec snapshot) invalidates them; the tournament then exits 3 and Loop C stops at Evaluate until
both are recorded again:

```bash
python scripts/record_default_cassettes.py --record
python scripts/benchmark_replay.py --record --spend
```

Both were recorded on 2026-11-12 with `google/gemini-3-flash-preview` (34 calls each, about 150k
tokens per set). Either recorder refuses to save a response the provider cut short or errored on
part-way: the pipeline reads such a response as "found nothing", and a cassette would replay that
one-off failure as the pipeline's answer from then on.

### The baseline (recorded 2026-11-12, `default` pipeline, scored on main at c55e3494)

| | found F1 | typed F1 | recall (core) | precision | type accuracy | relationship recall |
|---|---|---|---|---|---|---|
| `edit_check` (dev) | 0.259 | 0.068 | 0.250 (0.333) | 0.268 | 0.263 | 0.000 |
| `gitlab_architecture` (dev) | 0.564 | 0.160 | 0.434 (0.794) | 0.803 | 0.283 | 0.036 |
| `wikimedia_enterprise` (holdout) | 0.326 | 0.156 | 0.232 (0.289) | 0.548 | 0.478 | 0.000 |
| **dev mean** | **0.411** | **0.114** | 0.342 (0.564) | 0.535 | 0.273 | 0.018 |

Triple-corpus guard for the same recordings: dev strict-F1 0.932, soft-F1 0.943.

Type accuracy counts a found individual as typed correctly only when every class the run gave it
is the gold class or an acceptable one. On the dev documents 49% of found individuals have an
accepted class among those given (`type_accuracy_any`) and 27% have only accepted classes: the
difference is individuals proposed in several classes at once (GitLab Workhorse in four).

**How much a second take moves it.** The documents were recorded three times with nothing changed
(temperature 0). Dev found F1 came out 0.405 to 0.411 and dev typed F1 0.109 to 0.117; the holdout
document's typed F1 0.156 to 0.184. About 86% of the individuals an identify call names are the
same from one take to the next. The accept gate's margins (0.02 on dev, 0.04 on the holdout
document) are set above that; a gain inside it is not a result.

### The find-then-type implementation (recorded 2026-11-13, Claude Haiku 5.5)

`--implementation find_then_type` runs the benchmark through `FindThenTypeOrchestrator`
(`domain/pipelines/individual_extraction/find_then_type.py`): each chunk is read once for what it
mentions, each distinct mention of the source is typed once against every class of the ontology,
and pass 2 relates the typed individuals of each chunk. It has its own cassettes
(`tests/integration/fixtures/cassettes/extraction_benchmark_find_then_type/`), recorded with
`claude-haiku-5-5` through the Anthropic provider: 604 calls for the three documents, of which 570
are typing calls that share one cached system prompt (the catalog, about 19k tokens), about $0.30
in all and two to four minutes a document.

The catalog lists each class with the first 260 characters of its definition, not the whole of it
(`_DEFINITION_CHARS` in `domain/extraction/find_then_type.py`). The 193 definitions of the pinned
DR ontology run from 584 to 1482 characters, so about a quarter of their text is offered, and the
part that says which class to use instead is cut from nearly all of them. Offering more of a
definition is an untried change; it changes the prompt, so the cassettes would be recorded again.

| | found F1 | typed F1 | recall (core) | precision | type accuracy | relationship recall |
|---|---|---|---|---|---|---|
| `edit_check` (dev) | 0.433 | 0.389 | 0.513 (0.738) | 0.375 | 0.897 | 0.094 |
| `gitlab_architecture` (dev) | 0.635 | 0.541 | 0.607 (0.889) | 0.667 | 0.851 | 0.265 |
| `wikimedia_enterprise` (holdout) | 0.513 | 0.481 | 0.485 (0.658) | 0.545 | 0.938 | 0.036 |
| **dev mean** | **0.534** | **0.465** | 0.560 (0.814) | 0.521 | 0.874 | 0.180 |

Dev failure counts: 18 core and 67 supporting individuals missed, 15 mistyped, 93 spurious, 9
known distractors extracted, 109 relationships missed. Against the baseline above, the gain is in
typing (an individual has one class, chosen from the whole catalog) and in recall (statements are
found); what it proposes that gold does not hold is now the largest count.

This is one recording. The models it runs on take no temperature, so a second take will differ;
how much has not been measured, and the two-pass shape's margins above do not carry over. Loop C
still measures and optimises the `default` implementation: the tournament does not run this one.
`tests/integration/pipelines/test_extraction_benchmark_replay.py` replays these cassettes, so a
change that makes them stale fails that test until they are recorded again:

```bash
python scripts/benchmark_replay.py --record --spend --implementation find_then_type
```

Where the baseline loses, on the dev documents: 126 gold individuals not found (41 of them core),
52 found but not typed correctly, 57 predictions that match nothing, 8 known distractors
extracted, and 133 of 136 stated relationships missing. By layer, statements are the gap: 2 of the
41 motivation-layer individuals on the dev documents are found (1 of 43 on the holdout document).

`python scripts/record_default_cassettes.py --dry-run` prints what a recording would call without
calling anything.

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

The run ends with the benchmark pass (above): a "Benchmark" section in the digest,
`reports/tournament_<run_id>_benchmark.json` with each document's score and the lists behind it,
and `benchmark_dev` / `benchmark_holdout` rows in the telemetry file.

A variant whose cassettes no longer answer its prompts is flagged in a "STALE CASSETTES" section
at the top of the digest and the run exits 3. The extraction service turns a missing recording
into "no triples", so before this check a stale cassette set read as a pipeline scoring 0.

Each run also scores every variant's tuned config against the Wave 1 DR
bootstrap scenarios (`dataset_split.py`'s `DR_BOOTSTRAP_SCENARIOS`,
`karpathy_loop_dr_ontology_design.md` §5) as a **separate, always-reported
diagnostic pass**: a `bootstrap` row per variant in the same scoreboard
telemetry file (`fixture_id="bootstrap"`), and its own section in the
`tournament_<run_id>.md` digest. This pass is a sanity check — real,
independently-produced ground truth graded against the imported DR spec, too
thin (2 scenarios currently on disk, of a 4-scenario target — see
`karpathy_loop_dr_ontology_design.md` §5 — covering at most 4 of 12 layers)
to holdout-split or optimize
against — and is never mixed into `dev`/`holdout` aggregation, Loop C's target
selection (which ranks the benchmark's `failure_counts`), or the §6 accept
gate: `acceptGate` in `.claude/workflows/karpathy-loop.js` reads the benchmark's
`dev` and `holdout` measures and the triple corpus's `guard` measure, and
structurally cannot read bootstrap metrics.

## Recognition A/B measurement: `scripts/measure_recognition_quality_effect.py`

Issue #1137 Phase 5: quantifies whether the individual-recognition stage
(`adapters/recognition/individual_recognizer.py`; see also
`tests/integration/fixtures/pipelines/individual_recognition/README.md` for
its dedicated cross-document dedup metrics) changes extraction quality on the
error-report corpus, using the same harness as above (no new metric) run
twice — recognition off vs on — and diffing the two report pairs.

```bash
# from local-server/, venv active
python scripts/measure_recognition_quality_effect.py
```

Measured result (open_v1 rule-mode, `QUALITY_SCENARIOS`, 8 scenarios):
`label_mismatch` count and dev/holdout strict-F1/soft-F1 are **unchanged**
(13/13 label_mismatch; every F1 delta 0.0000). Recognition does relabel two
GT triples' failure-stage classification in one scenario
(`relation_not_derived` → `candidate_missing`, a diagnostic-only
reclassification with no P/R/F1 effect) by canonicalizing a repeated
in-document mention — but moves no aggregate quality number. Expected: this
corpus scores each scenario from an empty graph, and open_v1 rule mode emits
no class grounding, so recognition can only act on mentions repeated within a
single scenario's own text, not across documents (that cross-document case is
what the `individual_recognition` episode corpus measures instead).

## Loop C: `.claude/workflows/karpathy-loop.js`

`documentation/karpathy_loop_design.md` §4.3/§4.4 — the agent-in-the-loop
refinement cycle. Each invocation of the Workflow runs exactly **one**
iteration:

1. **Evaluate** — runs Loop B and reads the incumbent's benchmark measures (dev: `edit_check`,
   `gitlab_architecture`; holdout: `wikimedia_enterprise`), its failure counts, and the triple
   corpus's guard measure (the `default` variant's dev strict-F1). A stale or missing recording
   ends the iteration with `status: "error"` before anything is spent.
2. **Select** — reads `ledger.jsonl` for hypotheses already decided, ranks the benchmark's failure
   kinds (`missed_core`, `missed_supporting`, `mistyped`, `spurious`, `excluded_extracted`,
   `relationship_missed`) by count and maps the top ones to the seeded backlog (design doc §7).
   Hypotheses marked `blocked` are never selected: the gate reads the individuals' found F1 and
   typed F1 only, so a change that moves nothing but relationships or confidences cannot pass it.
3. **Experiment** — fans out one experimenter agent per hypothesis, each in its own git worktree,
   each implementing exactly one change. A change to a prompt, or to what feeds one, records both
   cassette sets again on its branch. The candidate is measured by the same steps as the incumbent.
   One that cannot be measured (stale recordings, a failed run) is recorded in the ledger as
   `unmeasured` with that reason and its worktree is discarded; the hypothesis stays selectable.
4. **Verify** — an adversarial agent checks each candidate: none of the frozen paths changed (the
   harness, the gold extractions, the schema snapshots, the tournament and benchmark scripts, the
   ledger), nothing in the diff is specific to a benchmark document, tests reproduce, the committed
   cassettes replay to every number the gate reads (dev found F1 and typed F1, holdout typed F1,
   the triple corpus's dev strict-F1), one change, and the diff matches the hypothesis.
5. **Decide** — the accept gate (design doc §6) on every verified candidate: benchmark dev found
   F1 improves by > 0.02 with typed F1 not regressing, or typed F1 improves by > 0.02 with found
   F1 dipping at most 0.05; the holdout document's typed F1 does not drop by more than 0.04; the
   triple corpus's dev strict-F1 does not drop by more than 0.02. A missing number fails the
   gate. Of the candidates that pass, the one with the highest dev typed F1 is accepted: merged
   into `experiment/karpathy-loop` with a ledger entry. Others that pass are discarded without a
   ledger entry, so they are drafted again against the new incumbent. Everything else → discard
   the worktree, append a ledger entry with the reason.

Invoke it with the `Workflow` tool by `scriptPath` (`.claude/workflows/karpathy-loop.js`; a
workflow launched by `name` can run a stale cached copy), e.g. `args: {iteration: 1}`. Each call
is one iteration: call it repeatedly (e.g. via `/loop`) and thread state through `args` from the
previous call's return value (`iteration`, `consecutiveNoAccept`, `hypothesisCount`,
`integrationBranch`, `holdoutFloors`, `maxConsecutiveNoAccept`, `cumulativeCostUsd`,
`totalBudgetUsd`). The returned `status` (`"stopped"` / `"accepted"` / `"no_accept"` / `"error"`)
and `stop` field tell the driver whether to keep iterating: halt whenever `stop` is not null.
That is when the holdout document's typed floors are met, after three consecutive no-accept
iterations, when the backlog is exhausted, when the budget in `args` is used up (checked before
an iteration starts, so the last iteration can overrun it), and after every accept. The
incumbent is measured on `main` and experimenter worktrees fork from `main`, so an accepted
change has to be promoted from the integration branch to `main`, by PR, before the next
iteration. Ledger entries are appended in the main checkout's working tree and are not committed
by the loop: commit `experiments/ledger.jsonl` with the promotion.

`node .claude/workflows/karpathy-loop.mechanics.test.mjs` checks the gate, target selection and
the prompts' frozen-path lists without running any agent.

## `ledger.py` / `ledger.jsonl`

Loop C's append-only record of every experiment (accepted and rejected), per
`documentation/karpathy_loop_design.md` §8. `experiments/ledger.py` provides
the read/write helpers (`append_entry`, `read_entries`,
`rejected_hypotheses`, `accepted_hypotheses`) plus a small CLI so a Loop C
sub-agent — which has shell access but no in-process import path into this
package — can record a decision without hand-writing JSON:

```bash
# from local-server/, venv active
python experiments/ledger.py append '{"experiment_id": "12-copular", ...}'
python experiments/ledger.py rejected-hypotheses
python experiments/ledger.py accepted-hypotheses
```

Target selection (§4.3 step 2) excludes both sets: a rejected hypothesis
already failed, and an accepted one is already merged into the incumbent, so
re-drafting either wastes an iteration (an accepted hypothesis re-run against
the incumbent it was merged into can only lose the accept gate).

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

`rejected_hypotheses()` and `accepted_hypotheses()` (and any future ledger
read that feeds a loop decision) are scoped through
`entries_since_last_baseline_reset()`, which excludes every entry recorded
before the most recent checkpoint. This is the mechanism — not a documented
convention — behind the rule that pre-reset dev/holdout scores never judge
post-reset experiments: a hypothesis rejected against a since-retired baseline
is eligible for retry immediately after the reset, with no manual ledger
cleanup required, and an accepted hypothesis whose merged incumbent the reset
retired is likewise selectable again.

```bash
# from local-server/, venv active — recording a reset manually (the DR
# import script does this for you on a spec-version change)
python experiments/ledger.py baseline-reset \
    --ontology-context dr_spec --spec-version 0.8.4 --base-commit "$(git rev-parse HEAD)" \
    'Replaced the placeholder ontology with the imported DR spec.'
```
