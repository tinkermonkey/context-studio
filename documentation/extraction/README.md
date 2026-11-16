# Extraction pipelines: current state

**As of 2026-11-16.** This is the single place that says what the extraction pipelines are, how good they are, and what is undecided. Experiments and their results are in [experiments/](experiments/README.md). When something here changes, update this page in the same pull request.

## The task

Context Studio extracts **individuals** (instances of a taxonomy's classes) and **relationships** between them from documents, and turns them into a proposal that a person reviews before anything is applied. The taxonomy in use is Documentation Robotics (DR): 193 classes in 12 layers, each with a curated definition, and a predicate catalog whose relationship types say which class pairs each predicate may connect. Schema extraction (proposing new classes) is a separate pipeline type and is not covered in depth here.

## What runs today

Individual extraction has three registered implementations (`local-server/domain/pipelines/individual_extraction/bootstrap.py`):

| implementation | what it does | default configuration | status |
|---|---|---|---|
| **`find_then_type`** | Find mentions per chunk (no typing); merge them over the source; type each distinct mention once against the whole class catalog (first 260 characters of each definition, cached) with "none" allowed; derive relationships per chunk with the predicates each subject class allows | `extraction-find-then-type`: Claude Haiku 5.5, 16,000 output tokens per call | **The default** (since PR #1598, 2026-11-14) |
| `default` | The older two-pass shape: pass 1 finds and types individuals against a shortlist of 50 class names retrieved by embedding similarity; pass 2 derives relationships. The id is only a name: it is not the default | `extraction-default`: Claude Haiku 5.5, 20,000 output tokens. Also `extraction-openrouter-default`: Gemini 3 Flash (the configuration its benchmark recordings were made with) | Kept selectable; scores far below `find_then_type` |
| `open_v1` | spaCy parses, clustering and vector retrieval, with optional LLM synthesis | `extraction-open-v1`: Gemini 3 Flash | Research stage, below floors, recordings stale; recommended for deletion |

All implementations share what follows extraction: recognition of extracted individuals against existing ones (exact label, then a conservative vector match; its tie-break call is hard-coded to Gemini 3 Flash), the chunk merge, and the source proposer. A run on a source with failed chunks produces a partial proposal that supersedes no other.

Schema extraction has `default` (Gemini 3 Flash, configuration `schema-extraction-default`) and `open_v1`.

## How a pipeline is selected

One method everywhere (PRs #1596 to #1599, #1597):

- A run is selected by **(pipeline type, implementation, configuration)**. The configuration carries the model, temperature, output-token limit and stage prompts.
- **Defaults are registry facts**: each pipeline type has one default implementation, each implementation one default configuration. One resolver, `local-server/domain/pipelines/selection.py`, serves every entry point (run API, batch route, source extraction, chat and MCP tools, `scripts/run_pipeline.py`). A `model`, `temperature` or `max_tokens` named in a run's input overrides the configuration's. The output limit is capped at 20,000 tokens.
- User-created configurations inherit any temperature or output limit they leave unset from their implementation's default configuration. A queued run whose configuration is edited or deleted before a server restart fails, saying so.
- The API states the defaults (`is_default`, `default_configuration`, `extracts_sources` on implementations; `is_default` on configurations), and the UI uses one shared implementation-and-configuration picker on every surface that starts a run.
- The benchmark scripts and the refinement loop select the same way, with `--implementation` and `--configuration`.

## How quality is measured

**The extraction benchmark** (`local-server/tests/integration/fixtures/pipelines/extraction_benchmark/`): three real documents of 3,000 to 6,000 words with gold extractions. `edit_check` and `gitlab_architecture` are dev, `wikimedia_enterprise` is the holdout. A run goes through the path a user's source takes and is scored on what would reach the review queue (`local-server/tests/integration/pipelines/_harness/benchmark.py`): found F1 (individual found, any class), typed F1 (found with an accepted class), core recall, precision, type accuracy, relationship recall.

```bash
# from local-server/, offline and free: replay recorded LLM calls
python scripts/benchmark_replay.py --implementation find_then_type
python scripts/benchmark_replay.py --implementation default      # two-pass, Gemini recordings
python scripts/benchmark_replay.py --all
python scripts/benchmark_external.py replay                      # the head-to-head's saved takes
```

How much to trust it:

- **The gold is model-made.** It was drafted by Claude Fable 5.2 from the DR definitions, re-extracted blind by a second model pass and adjudicated by a model; no person has checked it. It may favour approaches that, like the drafting, read whole documents with full definitions.
- **It is small:** three documents, 297 gold individuals, 51 of the 193 classes represented. The holdout document has been used in earlier prompt work.
- **Noise threshold: 0.08 typed F1.** A smaller difference between two approaches is not a result. `find_then_type` typed F1 ranges 0.426-0.465 on dev and 0.393-0.481 on the holdout over three takes, and the independent review put the threshold for a real difference at about 0.08. This is the one place the threshold is stated; the [rules for recording an experiment](experiments/README.md#recording-an-experiment) refer to it.

An older corpus of short test passages (`fixtures/pipelines/individual_extraction/`) is still used as a guard for the two-pass implementation; it does not represent real documents (see [Before the benchmark](experiments/2026-05-to-09-before-the-benchmark.md)).

## Best current numbers

Three takes per arm, mean typed F1, from the [head-to-head](experiments/2026-11-15-head-to-head.md) unless noted.

| approach | typed F1 dev | typed F1 holdout | relationship recall dev / holdout | cost per document |
|---|---|---|---|---|
| `find_then_type`, Haiku 5.5 (the app's default) | 0.452 | 0.442 | 0.164 / 0.018 | $0.08-0.12 |
| One Claude Opus 5.5 call per document, full catalog and definitions | 0.624 | 0.659 | 0.038 / 0.012 | $0.64-0.90 |
| One Claude Sonnet 5.5 call | 0.371 | 0.445 | 0.008 / 0.006 | $0.21-0.27 |
| One Claude Haiku 5.5 call | 0.450 | 0.439 | 0.011 / 0.018 | about $0.02 |
| Two-pass `default`, Gemini 3 Flash (one take, [baseline](experiments/2026-11-13-two-pass-baseline-and-stronger-models.md)) | 0.114 | 0.156 | 0.018 / 0.000 | |

In user terms, `find_then_type` finds about 56-58% of what the gold holds (81-84% of core items on dev), about half of what it proposes matches nothing in gold, and it proposes almost no correct relationships on the holdout.

## What we know

- **The pipeline's shape mattered more than the model.** A stronger model in the two-pass shape did not help (typed F1 0.09-0.18); finding first and then typing against the whole catalog did (0.47). Embedding shortlists hold the right class for only about half of gold individuals.
- **For individuals, one strong-model call beats our pipeline.** Opus 5.5 in one call leads `find_then_type` by +0.17 (dev) and +0.22 (holdout) typed F1, every take ahead by at least 0.155, at 5-8 times the cost. Sonnet and Haiku in one call do not beat it; decomposition is what gives Haiku its recall.
- **Relationships are unsolved.** Every approach is near zero on the holdout. A single call proposes 92% schema-invalid relationships when it is not told which class pairs each predicate allows, though it links the right pairs more often than the pipeline.
- **Typing says "none" too often** for about a quarter of gold-named mentions, partly because each mention is typed from its first occurrence only. Rewording the rule trades misses for mistypes. Whole definitions did not help.
- **Decision models (Clef)** type worse than Haiku against the full catalog and did not help as a final chooser. Agreement between two models identifies a subset (63-70% of mentions) that is about 90% right; this gating has not been built.
- **Local NLP mention finding** (spaCy, GLiNER2) finds many candidates at low precision and cannot type; [parse, shortlist, pick](experiments/2026-11-14-parse-shortlist-pick.md) scored 0.13.

## The refinement loop

The agent-driven refinement loop (Loop C, `.claude/workflows/karpathy-loop.js`, `documentation/karpathy_loop_design.md`, `local-server/experiments/README.md`) can now target any implementation and configuration (PR #1597). It has never run an iteration on the extraction benchmark. Its four past accepts optimised the short-passage corpus. Its accept margins for `find_then_type` are provisional until three paid re-recordings measure whole-take noise. The direction review recommends keeping it paused until the gold is human-checked. When it runs, each campaign records itself: one page under [experiments/](experiments/README.md) with its iterations generated from the ledger, and, on an accept, a line under the leads below. Its decision rule is its accept gate, fixed in code before a campaign starts.

## Leads from the refinement loop

A loop accept is one take judged by a margin below the noise threshold: a lead, not a result. It is listed here, and no number on this page moves, until a three-take experiment confirms it; then that experiment's page updates the numbers above and removes the line. The loop writes the lines between the markers (`local-server/experiments/campaign.py`).

<!-- loop:leads:start -->
None yet.
<!-- loop:leads:end -->

## Open decisions

1. **Adopt one Opus 5.5 call for finding and typing individuals?** It wins by the rule set in advance, at $0.64-0.90 a document against about $0.10. The review advised confirming on human-checked gold first, because the gold may favour single calls.
2. **Relationships:** keep the pipeline's schema-constrained relate step, or measure a single call that is given the allowed class pairs per predicate, or a relationship stage over the whole document.
3. **Proposals across implementations:** a whole `find_then_type` run on a source supersedes an earlier two-pass proposal of the same source, and a proposal does not record which implementation produced it.

## Recommended next steps

From the [direction review](experiments/2026-11-14-direction-review.md) and the [head-to-head](experiments/2026-11-15-head-to-head.md), in order. None is started.

1. **Human-check the gold:** a person adjudicates the holdout gold and the "spurious" items, then the benchmark grows to 10 or more documents with human-confirmed gold and a real holdout nobody prompts against.
2. **Measure relationships properly:** a single call given the allowed (domain, predicate, range) types, and a document-level relationship stage.
3. **Then decide the extraction core** (decision 1) and delete what loses, including `open_v1`.
4. **Measure value to a reviewer**, not only F1: time and acceptance when reviewing a proposal against modelling from scratch.

Stop doing: drawing conclusions from single recordings or differences under the noise threshold; scoring prompt experiments on the holdout; building more variants and tournament machinery before the measurement is trustworthy.

## Known gaps

- The recognition tie-break inside every extraction run is hard-coded to Gemini 3 Flash, outside any configuration.
- `scripts/run_pipeline.py` cannot run `open_v1`, relationship reflection, claim triage or notes-to-claims (it lacks their services).
- A Playwright test (`ux/e2e/tests/pipelines/extraction-review.spec.ts`, line 533) expects old wording and fails on main.

## Where things live

| what | where |
|---|---|
| Implementations | `local-server/domain/pipelines/individual_extraction/` (`orchestrator.py` two-pass, `find_then_type.py`, `open_orchestrator.py`), `local-server/domain/extraction/` (`services.py`, `find_then_type.py`, `prompts.py`) |
| Configurations | `local-server/configs/*.json`, `local-server/domain/pipelines/*/configurations/` |
| Selection | `local-server/domain/pipelines/selection.py`, `registry.py` |
| Benchmark and scorer | `local-server/tests/integration/fixtures/pipelines/extraction_benchmark/`, `local-server/tests/integration/pipelines/_harness/benchmark.py` |
| Recordings | `local-server/tests/integration/fixtures/cassettes/extraction_benchmark*/`, `local-server/tests/integration/fixtures/pipelines/extraction_benchmark_external/` |
| Benchmark scripts | `local-server/scripts/benchmark_replay.py`, `benchmark_external.py`, `quality_tournament.py` |
| Refinement loop | `.claude/workflows/karpathy-loop.js`, `documentation/karpathy_loop_design.md`, `local-server/experiments/` |
| Experiments | [experiments/](experiments/README.md) |

## Keeping this page current

How experiments are recorded, and when this page changes with them, is in [Recording an experiment](experiments/README.md#recording-an-experiment). In short: a verdict that changes anything stated here updates this page and its "As of" date in the same pull request as the experiment's page. The refinement loop changes only its leads and the date: its accepts are one take each, so they never move the numbers on this page.
