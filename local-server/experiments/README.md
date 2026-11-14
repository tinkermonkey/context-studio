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
python scripts/benchmark_replay.py                                   # offline: replay the cassettes, score
python scripts/benchmark_replay.py --implementation find_then_type   # another implementation
python scripts/benchmark_replay.py --all                             # every target that has recordings
python scripts/benchmark_replay.py --record --spend --implementation find_then_type \
    --configuration extraction-find-then-type                        # record with the live LLM

# against a running server (./dev.sh)
python scripts/extraction_benchmark.py validate
python scripts/extraction_benchmark.py load                              # gold -> datasets bench-*
python scripts/extraction_benchmark.py run --document edit_check --spend # extract with a configuration, score
python scripts/extraction_benchmark.py score --document edit_check --proposal <id>
```

**What it runs is chosen like any run:** an implementation of individual extraction and one of its
configurations (`--implementation`, `--configuration`), selected through the pipeline resolver
(`domain/pipelines/selection.py`). The orchestrator comes from the pipeline implementation registry
and the model, temperature, output-token limit and stage prompts from the configuration, as
`domain/pipelines/individual_extraction/bootstrap.py` registers them; the script names no model.
A configuration's stage prompts are the ones sent, so a prompt-only variant is a configuration.

**`default` is a name.** Since PR #1598 the type's default implementation is `find_then_type`; the
two-pass implementation keeps the id `default`, which says nothing about being the default. With
no flags the target is the type's default implementation, with the configuration its recordings
were made with, so `python scripts/benchmark_replay.py` replays `find_then_type` and prints
`dev typed F1 0.465, found F1 0.534`. To replay two-pass, name it: `--implementation default`
(prints `dev typed F1 0.114, found F1 0.411`).

| target | recordings | recorded with |
|---|---|---|
| `default` + `extraction-openrouter-default` | `cassettes/extraction_benchmark/` | `google/gemini-3-flash-preview`, 2026-11-12 |
| `find_then_type` + `extraction-find-then-type` | `cassettes/extraction_benchmark_find_then_type/` | `claude-haiku-5-5`, 2026-11-13 |

Each recorded implementation's benchmark is pinned by name to the configuration it was recorded
with (`RECORDED_WITH` in the script), not to the implementation's default configuration. For
two-pass the two differ: its default is `extraction-default`, which moved from Claude Opus to
Claude Haiku 5.5 on 2026-11-14 (PR #1598), and the cassette key includes the model. Measuring
two-pass with `extraction-default` is another target
(`--implementation default --configuration extraction-default`) with a folder of its own
(`extraction_benchmark__extraction-default/`), and needs its own recording. In general a target's
folder is `extraction_benchmark` (two-pass) or `extraction_benchmark_<implementation>`, plus
`__<configuration>` for a configuration other than the one the implementation's benchmark runs
with. The defaults are the registry's own (`default_implementation`, `default_configuration` of
the registries; the script asks the resolver), so nothing here spells one.

The run's input is the resolver's (`PipelineSelection.run_input`): the configuration's model,
temperature and output-token limit. The output-token limit comes from the configuration since
PR #1598 (two-pass `extraction-default` 20,000, `extraction-openrouter-default` 8,000,
`find_then_type` 16,000 on every stage; 20,000 at most anywhere). It is not part of a cassette's
key, so the committed recordings replay unchanged; a change of limit is still a change of what a
live recording would get back.

`benchmark_replay.py` runs the target in process, each document as a source (chunked,
merged, planned), against the pinned DR spec the gold files were made for, with real embeddings
and a schema index so the class catalog offered is the one the app would offer. It prints the
target it resolved (`target: implementation …, configuration …, model …`), and its `--json`
summary carries the same three fields. It
reports `not_recorded` or `stale` instead of numbers when the cassettes are missing or no longer
answer the prompts, and `failed` when the extraction itself failed with every prompt answered (a
run with a failed chunk is not scored), and exits 2. A run over some of the documents
(`--document`) is `partial` and prints each document's score without a dev or holdout mean.
With `--json`, standard output is the JSON and nothing else (the lines for people go to standard
error). There is no `--model`: a run uses its configuration's model, so another model is another
configuration, with a cassette folder of its own. Building the ontology takes about a minute.

`extraction_benchmark.py run` measures what a user gets: the server's own code, a pipeline
configuration's model and stage prompts, and a real proposal left in the review queue.

## Prerequisites to a full run

The recordings the chosen target reads must answer the current prompts: its benchmark cassettes,
and, for `default`, the triple corpus's (the guard). The cassette key hashes the whole prompt and
the model, so any change to a prompt, to what feeds it (the class catalog, the predicate list,
chunking, the DR spec snapshot) or to the model of the configuration invalidates them; the
tournament then exits 3 and Loop C stops at Evaluate until they are recorded again:

```bash
python scripts/benchmark_replay.py --record --spend --implementation <id> --configuration <ref>
python scripts/record_default_cassettes.py --record      # the triple corpus (default variants)
python scripts/validate_tournament_setup.py --implementation <id>   # offline: are the files there?
```

A change to a part the implementations share makes every implementation's recordings stale. The
relationship stage is one: `FIND_THEN_TYPE_STAGES` reuses the two-pass shape's
`derive_relationships` stage (`domain/extraction/prompts.py`), and chunking, merging and planning
are common code. `python scripts/benchmark_replay.py --all` replays every recorded target and
exits non-zero if any is stale; `tests/integration/pipelines/test_extraction_benchmark_replay.py`
replays both committed sets in CI.

The `default` sets were recorded on 2026-11-12 with `google/gemini-3-flash-preview` (34 calls
each, about 150k tokens per set). Either recorder refuses to save a response the provider cut
short or errored on part-way: the pipeline reads such a response as "found nothing", and a
cassette would replay that one-off failure as the pipeline's answer from then on.

Stale on `main` as of 2026-11-14: the `open_v1` variant's canonicalization cassettes (70 of 104
calls have no recording). No benchmark target and no guard reads them, so the tournament flags
them and exits 0, and Loop C names them to its agents as stale before the change; record them with
`python scripts/record_individual_canonicalization_cassettes.py` if `open_v1`'s numbers matter.

### The baseline (recorded 2026-11-12, `default` with `extraction-openrouter-default`, scored on main at c55e3494)

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
part that says which class to use instead is cut from nearly all of them. Offering whole
definitions was tried on 2026-11-14 (a scratch run, find answers held fixed) and gained nothing:
dev typed F1 0.446.

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

**What is known of its noise, and what is not.** The figures in this list, the whole-definitions
result above and the model's quoted reasons come from scratch runs made on 2026-11-14 by the
session that commissioned the loop's `find_then_type` support (one take each, the find answers
held fixed so only typing varied). They were reported to it: no artefact of those runs is
committed, and the committed typing answers carry no reason text, so none of this can be looked up
in the repository.

- Typing the same 570 mentions again with the unchanged prompt changed 16.5% of the answers. Dev
  typed F1 came out 0.476 against the committed 0.465, the holdout document's 0.442 against 0.481.
- Typing answers "none" for about a quarter of the mentions whose name matches a gold individual
  (45 of 180), the same ones each time. Its reasons are that the mention is "only a heading or
  table label here" or "only cited in passing": a mention is typed from its first placed occurrence
  only (`_Candidate.typed_in`). Loosening the "none" rule by wording alone lost (13 more right, 24
  more wrong, 78 more mentions recorded that gold does not hold; dev typed F1 0.41). Typing a
  mention from all of its occurrences is untried, and heads the backlog.
- The relate stage hit its output-token limit, then 8,000 (fixed in code), on the GitLab document
  in two of four takes (a failed chunk, so that take is not scored), and relationship recall on the
  Edit check document came out between 0.00 and 0.09. Since PR #1598 every `find_then_type` stage
  runs with its configuration's limit, 16,000; whether that is enough for the GitLab document has
  not been measured.
- Not measured: how much a full re-recording (find, type and relate) moves the scores. The find
  stage's noise is unknown.

Loop C can refine this implementation (`args: {implementation: "find_then_type"}`, below), with
gate margins that are **provisional**: epsilon 0.03 and holdout slack 0.06, set from the typing
figures above, not from re-recordings. Before its verdicts on `find_then_type` can be trusted,
three recordings of the unchanged implementation are needed (about $0.30 each), as were made for
two-pass, to replace those margins with measured ones; and the relate stage has to stay within its
output limit (16,000 now; the cuts were seen at 8,000), or recordings of the GitLab document will
fail and their experiments end `unmeasured`. The triple-corpus guard does not apply to it: that corpus has no
recordings of this implementation.

`tests/integration/pipelines/test_extraction_benchmark_replay.py` replays these cassettes and the
`default` ones, so a change that makes either set stale fails that test until they are recorded
again. It also pins each target's dev typed F1 and found F1 to the committed values (within
0.0005): a change after the LLM calls (merging, planning, recognition, scoring) makes nothing stale
and can still move a score. When one legitimately moves, update the pinned values there, the
tables here and in the design doc, and record the new baseline in the ledger.

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
tournament (§4.2): every registered variant (`open_v1`, `default`,
`default+grounding`; see `build_registry()` in that script) is Loop-A-tuned on
dev, then scored on the full corpus. Each variant says what it runs: an
implementation, a configuration and the model that configuration names, read
from the pipeline registry. The `default` variants run the `default`
implementation with `extraction-openrouter-default`, the configuration the
triple corpus was recorded with. Output:

- a per-variant error report pair in `reports/tournament_<variant>_<run_id>.{json,md}`
  (same shape as above — produced by the same `_harness/error_report.py` code);
- a scoreboard digest in `reports/tournament_<run_id>.md`, ranking variants by
  mean dev soft-F1 with strict-F1 and the §3.1 diagnostics alongside;
- a scoreboard telemetry row per variant in
  `tests/integration/fixtures/pipelines/_metrics/quality_tournament_individual_extraction.jsonl`
  (gitignored, same JSONL schema `quality_loop.py` uses). A row's `model` is
  the model that ran and its `config_ref` the configuration; `implementation`
  and `variant` name the rest.

The run ends with the benchmark pass (above) for one target, chosen with `--implementation` and
`--configuration` (the same defaults as `benchmark_replay.py`):

```bash
python scripts/quality_tournament.py --implementation find_then_type --passes 1 --restarts 1
```

It adds a "Benchmark" section to the digest, headed by the implementation, configuration and model
that ran; `reports/tournament_<run_id>_benchmark.json` with those three fields, each document's
score and the lists behind it, and a `guard` object; and `benchmark_dev` / `benchmark_holdout` rows
in the telemetry file. `guard` is the triple corpus's measure for the target: the dev strict-F1 and
soft-F1 of the `default` variant when the target is the one the corpus was recorded with (`default`
with `extraction-openrouter-default`), or `{"applies": false, "reason": …}` for any other target
(`find_then_type`, or `default` with another configuration). For those the corpus's measure is
listed under its own name in `other_guards`: it still says whether a change made for the target
damaged the implementation the corpus was recorded with. Loop C reads both from there, never from
a row of the scoreboard.

A variant whose cassettes no longer answer its prompts is flagged in a "STALE CASSETTES" section
at the top of the digest. The run exits 3 when the stale recordings are the chosen target's: its
benchmark cassettes, or a variant that runs its implementation. Any other stale variant is
flagged only. It exits 4 when the target's benchmark has no score for another reason (not
recorded, a document missing, the extraction failed); the report's `status` says which. It exits 0
only when the target's numbers can be read. The extraction service turns a missing recording into "no triples", so before this
check a stale cassette set read as a pipeline scoring 0.

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

The iteration refines one implementation, measured with one of its configurations:
`args.implementation` and `args.configuration`, each defaulting through the pipeline registry as
in `benchmark_replay.py`. With neither, the workflow passes no flag to the scripts and reads what
they resolved from the benchmark report: since PR #1598 that is `find_then_type` with
`extraction-find-then-type`. To refine two-pass, name it: `args: {implementation: "default"}`
(`default` is its id, not the registry's default). An implementation needs two things in the
workflow script: a backlog (`BACKLOGS`) and gate margins (`GATE_MARGINS`). Two-pass and
`find_then_type` have both; for any other the iteration stops with an error instead of borrowing
another's. What a change could move (`RECORDED_TARGETS`, `TRIPLE_CORPUS_TARGET`) is listed in the
script too, checked by its mechanics test against what the Python scripts pin, so an incumbent
measurement that leaves one out of its baseline stops the iteration.

1. **Evaluate** — runs Loop B for the target and reads the incumbent's benchmark measures (dev:
   `edit_check`, `gitlab_architecture`; holdout: `wikimedia_enterprise`), its failure counts, and
   the triple corpus's guard measure from the benchmark report's `guard` object. It also takes the
   baseline of everything else a change could move: every other recorded benchmark target
   (`benchmark_replay.py --all`) and the triple corpus's measure when it is not the target's guard
   (`other_guards`). A stale or missing recording of the target, or of one of those, ends the
   iteration with `status: "error"` before anything is spent, as does a guard that disagrees with
   the target's margins; recordings nothing here reads that are stale on `main` are noted
   (`staleElsewhere`).
2. **Select** — reads `ledger.jsonl` for the hypotheses already rejected for this implementation
   and configuration, and already accepted (merged) for this implementation, ranks the benchmark's failure kinds (`missed_core`,
   `missed_supporting`, `mistyped`, `spurious`, `excluded_extracted`, `relationship_missed`) by
   count and maps the top ones to the implementation's backlog (design doc §7). Hypotheses marked
   `blocked` are never selected: the gate reads the individuals' found F1 and typed F1 only, so a
   change that moves nothing but relationships or confidences cannot pass it, and one the harness
   cannot record (`typing_majority_vote`: three identical calls are one recording) cannot be
   measured.
3. **Experiment** — fans out one experimenter agent per hypothesis, each in its own git worktree,
   each implementing exactly one change. A change to a prompt, or to what feeds one, records again,
   on its branch, every cassette set it made stale: the target's benchmark, any other
   implementation's benchmark (the change touched a shared part), and the triple corpus. The
   candidate is measured by the same steps as the incumbent, and reports the implementation,
   configuration and model its measurement ran. One that cannot be measured (stale recordings, a
   failed run) is recorded in the ledger as `unmeasured` with that reason and its worktree is
   discarded; the hypothesis stays selectable.
4. **Verify** — an adversarial agent checks each candidate: none of the frozen paths changed (the
   harness, the gold extractions, the schema snapshots, the tournament and benchmark scripts, the
   ledger, and what says which orchestrator and model a target runs: `configs/`, the registry, the
   bootstrap and `configurations/`), nothing in the diff is specific to a benchmark document, tests
   reproduce, the target's committed cassettes replay to every number the gate reads (dev found F1
   and typed F1, holdout typed F1, and the guard as the benchmark report states it), nothing is
   stale that was not stale on `main`, no cassette file was deleted (a recording is made again,
   never removed), one change, and the diff matches the hypothesis. It also replays every other
   recorded target and reports what it sees, with the model its own replay ran.
5. **Decide** — the script, not the verifier's verdict alone, decides where each candidate stands:
   - `unmeasured` when nothing can be said about the hypothesis: no verdict; another recorded
     target not replayed or left stale; a measurement made with a model other than the
     incumbent's (a change of model is not an experiment);
   - `rejected` when a check failed, or when the change damages another recorded target: its dev
     typed F1 lower by more than that target's own epsilon, or the triple corpus's strict-F1 lower
     by more than its guard slack;
   - otherwise the accept gate (design doc §6), with the target's margins: benchmark dev found F1
     improves by more than epsilon with typed F1 not regressing, or typed F1 improves by more than
     epsilon with found F1 dipping at most 0.05; the holdout document's typed F1 does not drop by
     more than the holdout slack; where the guard applies, the triple corpus's dev strict-F1 does
     not drop by more than 0.02. A missing number fails the gate. Scores are compared in whole
     ten-thousandths, so a gain of exactly epsilon never counts.

   Of the candidates that pass, the one with the highest dev typed F1 is accepted: merged into
   `experiment/karpathy-loop` with a ledger entry. Others that pass are discarded without a ledger
   entry, so they are drafted again against the new incumbent. Everything else → discard the
   worktree, append a ledger entry with the reason. Every entry records the implementation, the
   configuration, the model the candidate ran beside the incumbent's, the margins used and whether
   they were provisional, the guard (or that it did not apply), and every other recorded target's
   measure before and after the change.

The margins are measured with one configuration each. A target with another configuration of the
same implementation (`{"implementation": "default", "configuration": "extraction-default"}`) is
judged by the same figures as provisional ones, with no guard, and has its own hypothesis history.

| implementation | measured with | epsilon | holdout slack | guard | from |
|---|---|---|---|---|---|
| `default` | `extraction-openrouter-default` | 0.02 | 0.04 | dev strict-F1, slack 0.02 | three recordings of the unchanged implementation (above) |
| `find_then_type` | `extraction-find-then-type` | 0.03 (provisional) | 0.06 (provisional) | not applicable | typing noise only, two takes (scratch runs, not in the repository); full re-recording noise not measured |

To run one iteration against `find_then_type` (the registry's default, so `args: {iteration: 1}`
does the same):

```
Workflow  scriptPath: .claude/workflows/karpathy-loop.js
          args: {"implementation": "find_then_type", "iteration": 1}
```

Its result carries `provisionalMargins: true`: an accept or a reject under provisional margins is
not yet a trusted verdict (see "The find-then-type implementation" above for what is missing).

Invoke it with the `Workflow` tool by `scriptPath` (`.claude/workflows/karpathy-loop.js`; a
workflow launched by `name` can run a stale cached copy), e.g. `args: {iteration: 1}`. Each call
is one iteration: call it repeatedly (e.g. via `/loop`) and thread state through `args` from the
previous call's return value (`implementation`, `configuration`, `iteration`,
`consecutiveNoAccept`, `hypothesisCount`,
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

`node .claude/workflows/karpathy-loop.mechanics.test.mjs` checks the gate, the margins and
backlogs of each implementation, target selection, the decisions the script makes from the
verifier's report, and that the prompts measure, record and verify the chosen target; it also runs
the whole script against stub agents. It runs no real agent.

## `ledger.py` / `ledger.jsonl`

Loop C's append-only record of every experiment (accepted and rejected), per
`documentation/karpathy_loop_design.md` §8. `experiments/ledger.py` provides
the read/write helpers (`append_entry`, `read_entries`,
`rejected_hypotheses`, `accepted_hypotheses`) plus a small CLI so a Loop C
sub-agent — which has shell access but no in-process import path into this
package — can record a decision without hand-writing JSON:

```bash
# from local-server/, venv active
python experiments/ledger.py append '{"experiment_id": "12-default-copular", ...}'
python experiments/ledger.py rejected-hypotheses --implementation find_then_type \
    --configuration extraction-find-then-type
python experiments/ledger.py accepted-hypotheses --implementation find_then_type
```

An experiment entry must name the `implementation` and `configuration` it refined and measured
(`append` refuses one that does not). **Rejections are scoped by both**, because a rejection was
judged with one configuration's model: `cross_chunk_relationships` rejected for two-pass is still
open for `find_then_type`, and a hypothesis rejected for two-pass with
`extraction-openrouter-default` is still open for two-pass with `extraction-default`.
**Acceptances are scoped by the implementation alone**, because an accepted change is merged into
the implementation's code, which every configuration of it runs: it is not drafted and paid for
again under another configuration. Without the flags the commands list everyone's.
Where the triple-corpus guard does not apply, the entry's `guard` is `{"applies": false,
"reason": …}`, not another implementation's number.

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

A reset that names an `implementation` (`--implementation`, and with it
`--configuration`) resets only the history of what it names: use it when one
target's recordings are made again or its margins re-measured. One that names
none resets every history: the gold files, the scorer or the ontology
changed.

The 2026-11-14 reset records the change that made the measurement scripts
select what they run by implementation and configuration
(`scripts/quality_tournament.py` and `scripts/benchmark_replay.py` are frozen
paths, changed by a reviewed PR outside the loop). No score moved: its
`baseline` field holds `default`'s unchanged baseline and `find_then_type`'s
first one, each under its implementation, with the configuration it was
measured with and the margins it is judged by.

`rejected_hypotheses()` and `accepted_hypotheses()` (and any future ledger
read that feeds a loop decision) are scoped through
`entries_since_last_baseline_reset()`, which excludes every entry recorded
before the most recent checkpoint that applies. This is the mechanism — not a documented
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
