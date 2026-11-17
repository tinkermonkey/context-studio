# Extraction pipelines: current state

**As of 2026-11-17.** This is the single place that says what the extraction pipelines are, how good they are, and what is undecided. Experiments and their results are in [experiments/](experiments/README.md). When something here changes, update this page in the same pull request.

## The task

Context Studio extracts **individuals** (instances of a taxonomy's classes) and **relationships** between them from documents, and turns them into a proposal that a person reviews before anything is applied. The taxonomy in use is Documentation Robotics (DR): 193 classes in 12 layers, each with a curated definition, and a predicate catalog whose relationship types say which class pairs each predicate may connect. Schema extraction (proposing new classes) is a separate pipeline type and is not covered in depth here.

## What runs today

Individual extraction has four registered implementations (`local-server/domain/pipelines/individual_extraction/bootstrap.py`):

| implementation | what it does | default configuration | status |
|---|---|---|---|
| **`single_call`** | One call reads the whole document (a document too long for one call: the fewest runs of chunks of at most 60,000 characters, one call each) and lists every individual with its class and a quote, against the whole class catalog with full definitions by layer (cached); then `find_then_type`'s relate step: relationships per chunk with the predicates each subject class allows | `extraction-single-call`: Claude Opus 5.5, effort high and 64,000 output tokens for the individuals call; relate calls at the model's default effort and 16,000 output tokens | **The default** (since 2026-11-17, [the user's decision](experiments/2026-11-17-single-call-implementation.md) on the head-to-head's evidence) |
| `find_then_type` | Find mentions per chunk (no typing); merge them over the source; type each distinct mention once against the whole class catalog (first 260 characters of each definition, cached) with "none" allowed; derive relationships per chunk with the predicates each subject class allows | `extraction-find-then-type`: Claude Haiku 5.5, 16,000 output tokens per call | Kept selectable; the default from PR #1598 (2026-11-14) to 2026-11-17; about a tenth of `single_call`'s cost |
| `default` | The older two-pass shape: pass 1 finds and types individuals against a shortlist of 50 class names retrieved by embedding similarity; pass 2 derives relationships. The id is only a name: it is not the default | `extraction-default`: Claude Haiku 5.5, 20,000 output tokens. Also `extraction-openrouter-default`: Gemini 3 Flash (the configuration its benchmark recordings were made with) | Kept selectable; scores far below `find_then_type` |
| `open_v1` | spaCy parses, clustering and vector retrieval, with optional LLM synthesis | `extraction-open-v1`: Gemini 3 Flash | Research stage, below floors, recordings stale; recommended for deletion |

All implementations share what follows extraction: recognition of extracted individuals against existing ones (exact label, then a conservative vector match; when a preview or apply finds several existing individuals about equally close, a tie-break call asks the model the run's configuration names as `recognition_model`, Gemini 3 Flash in every configuration that ships), the chunk merge, and the source proposer. A run on a source with failed chunks produces a partial proposal that supersedes no other; a whole run supersedes only earlier open proposals of the same implementation (decision 3).

A run on a source counts its progress in chunks (`items_done` of `items_total`). A `single_call` or `find_then_type` run counts a chunk as done only once its relationships are read, so it also reports the stage it is in and how far through it, as `stage`, `stage_done` and `stage_total` on the run: `single_call` is in `find_individuals` (sections of the text read, one for most documents), then `derive_relationships` (chunks read); `find_then_type` in `find_mentions` (chunks searched), `type_mention` (distinct mentions typed), then `derive_relationships`. The Extract page, the sources list and the MCP `get_run` tool show it. The two-pass shape reports chunks only.

Schema extraction has `default` (Gemini 3 Flash, configuration `schema-extraction-default`) and `open_v1`.

## How a pipeline is selected

One method everywhere (PRs #1596 to #1599, #1597):

- A run is selected by **(pipeline type, implementation, configuration)**. The configuration carries the model, temperature, output-token limit and stage prompts.
- **Defaults are registry facts**: each pipeline type has one default implementation, each implementation one default configuration. One resolver, `local-server/domain/pipelines/selection.py`, serves every entry point (run API, batch route, source extraction, chat and MCP tools, `scripts/run_pipeline.py`). A `model`, `temperature` or `max_tokens` named in a run's input overrides the configuration's. The output limit is capped at 64,000 tokens (20,000 until 2026-11-17, when the Anthropic provider began streaming any request for more than 20,000; its client refuses larger requests that do not stream).
- User-created configurations inherit any temperature or output limit they leave unset from their implementation's default configuration. A queued run whose configuration is edited or deleted before a server restart fails, saying so.
- The API states the defaults (`is_default`, `default_configuration`, `extracts_sources` on implementations; `is_default` on configurations), and the UI uses one shared implementation-and-configuration picker on every surface that starts a run.
- The benchmark scripts and the refinement loop select the same way, with `--implementation` and `--configuration`.

## How quality is measured

**The extraction benchmark** (`local-server/tests/integration/fixtures/pipelines/extraction_benchmark/`): three real documents of 3,000 to 6,000 words with gold extractions. `edit_check` and `gitlab_architecture` are dev, `wikimedia_enterprise` is the holdout. A run goes through the path a user's source takes and is scored on what would reach the review queue (`local-server/tests/integration/pipelines/_harness/benchmark.py`): found F1 (individual found, any class), typed F1 (found with an accepted class), core recall, precision, type accuracy, relationship recall, and (since 2026-11-17) relationship precision, a lower bound because gold holds only the plainly stated relationships. The external harness also counts relationships that are not an allowed relationship type for the classes of their ends.

```bash
# from local-server/, offline and free: replay recorded LLM calls
python scripts/benchmark_replay.py                                   # the default, single_call
python scripts/benchmark_replay.py --implementation find_then_type
python scripts/benchmark_replay.py --implementation default      # two-pass, Gemini recordings
python scripts/benchmark_replay.py --all
python scripts/benchmark_external.py replay                      # the head-to-head's saved takes
python scripts/benchmark_relationships.py report                 # the relationship experiment's
```

How much to trust it:

- **The gold is model-made.** It was drafted by Claude Fable 5.2 from the DR definitions, re-extracted blind by a second model pass and adjudicated by a model; no person has checked it. It may favour approaches that, like the drafting, read whole documents with full definitions.
- **It is small:** three documents, 297 gold individuals, 51 of the 193 classes represented. The holdout document has been used in earlier prompt work.
- **Noise threshold: 0.08 typed F1.** A smaller difference between two approaches is not a result. `find_then_type` typed F1 ranges 0.426-0.465 on dev and 0.393-0.481 on the holdout over three takes, and the independent review put the threshold for a real difference at about 0.08. This is the one place the threshold is stated; the [rules for recording an experiment](experiments/README.md#recording-an-experiment) refer to it.

To have a person check a gold file and write the verdicts back (`extraction_benchmark.py check`, review, `write-gold`, re-score), see "Checking the gold" in the [benchmark README](../../local-server/tests/integration/fixtures/pipelines/extraction_benchmark/README.md).

An older corpus of short test passages (`fixtures/pipelines/individual_extraction/`) is still used as a guard for the two-pass implementation; it does not represent real documents (see [Before the benchmark](experiments/2026-05-to-09-before-the-benchmark.md)).

## Best current numbers

Three takes per arm, mean typed F1, from the [head-to-head](experiments/2026-11-15-head-to-head.md) unless noted.

| approach | typed F1 dev | typed F1 holdout | relationship recall dev / holdout | cost per document |
|---|---|---|---|---|
| `single_call`, Opus 5.5, then the relate step (the app's default; **one take**, [its page](experiments/2026-11-17-single-call-implementation.md)) | 0.576 | 0.625 | 0.321 / 0.161 | $0.7-1.5 |
| `find_then_type`, Haiku 5.5 | 0.452 | 0.442 | 0.164 / 0.018 | $0.08-0.12 |
| One Claude Opus 5.5 call per document, full catalog and definitions | 0.624 | 0.659 | 0.038 / 0.012 | $0.64-0.90 |
| One Claude Sonnet 5.5 call | 0.371 | 0.445 | 0.008 / 0.006 | $0.21-0.27 |
| One Claude Haiku 5.5 call | 0.450 | 0.439 | 0.011 / 0.018 | about $0.02 |
| Two-pass `default`, Gemini 3 Flash (one take, [baseline](experiments/2026-11-13-two-pass-baseline-and-stronger-models.md)) | 0.114 | 0.156 | 0.018 / 0.000 | |

In user terms, in its one take `single_call` finds about 65% of what the gold holds (88% of core items on dev), about 40% of what it proposes on dev matches nothing in gold, and it finds about a third of the gold relationships on dev and a sixth on the holdout. `find_then_type` finds about 56-58% (81-84% of core items on dev), about half of what it proposes matches nothing in gold, and it proposes almost no correct relationships on the holdout.

**Relationships**, from the [relationship experiment](experiments/2026-11-17-relationships.md) (three takes, every arm limited to the allowed relationship types; precision against gold is a lower bound):

| approach | rel. recall dev / holdout | rel. precision dev / holdout | invalid types listed | cost per document |
|---|---|---|---|---|
| `find_then_type` as shipped (relate per chunk over its own individuals) | 0.164 / 0.018 | 0.31 / 0.05 | 0% | $0.08-0.12 |
| Opus single call for individuals, then the per-chunk relate stage on Haiku 5.5 (R0; `single_call` ships it on Opus, one take above) | 0.159 / **0.149** | 0.33 / 0.30 | 0% | $0.33-0.60 |
| One Opus call for individuals and relationships, given the allowed types (R1) | **0.315** / 0.113 | 0.37 / 0.20 | 0% (0 of 466) | $0.29-0.60 |
| Opus single call for individuals, then one Opus relate call over the whole document (R2-opus) | 0.300 / 0.131 | 0.28 / 0.28 | 0% | $0.48-0.90 |
| The same with Haiku as the relate call (R2-haiku) | 0.045 / 0.107 | 0.31 / 0.34 | 0% | $0.33-0.59 |
| One Opus call given the predicates only ([head-to-head](experiments/2026-11-15-head-to-head.md) arm B) | 0.038 / 0.012 | 0.03 / 0.01 | 92-95% | $0.32-0.58 |

## What we know

- **The pipeline's shape mattered more than the model.** A stronger model in the two-pass shape did not help (typed F1 0.09-0.18); finding first and then typing against the whole catalog did (0.47). Embedding shortlists hold the right class for only about half of gold individuals.
- **For individuals, one strong-model call beats our pipeline.** Opus 5.5 in one call leads `find_then_type` by +0.17 (dev) and +0.22 (holdout) typed F1, every take ahead by at least 0.155, at 5-8 times the cost. Sonnet and Haiku in one call do not beat it; decomposition is what gives Haiku its recall.
- **As an implementation, the single call holds up** (one take): through the app's path it scored within noise of the head-to-head's single call and above every `find_then_type` take. It listed more individuals than the head-to-head's call did, trading precision for recall; why is not established.
- **Relationships are unsolved, but the relate step after the single call is the best yet.** A single call proposes 92% schema-invalid relationships when it is not told which class pairs each predicate allows, though it links the right pairs more often than the pipeline. The schema-constrained relate step on Opus after the single call reached relationship recall 0.32 dev and 0.16 holdout in one take, against near zero for every approach before; how much of that is Opus in the relate step is not separated. The [relationship experiment](experiments/2026-11-17-relationships.md) separates part of it: the same per-chunk step on Haiku over Opus's individuals scored 0.159 dev (three takes), so Opus in the relate step roughly doubles dev recall.
- **Relationships follow the individuals, and a model given the allowed types keeps to them.** The per-chunk relate stage scores holdout recall 0.018 over `find_then_type`'s individuals and 0.149 over Opus's. A single call given only the predicates proposes 92% invalid relationships; given the allowed (source class, predicate, target class) types it proposed none in 466, and dev recall rose from 0.04 to 0.32. Given the gold individuals, a whole-document Opus call recovers 0.65-0.77 of gold relationships, the per-chunk Haiku stage 0.31-0.61: what limits relationships now is mostly the individuals.
- **Typing says "none" too often** for about a quarter of gold-named mentions, partly because each mention is typed from its first occurrence only. Rewording the rule trades misses for mistypes. Whole definitions did not help.
- **Decision models (Clef)** type worse than Haiku against the full catalog and did not help as a final chooser. Agreement between two models identifies a subset (63-70% of mentions) that is about 90% right; this gating has not been built.
- **Local NLP mention finding** (spaCy, GLiNER2) finds many candidates at low precision and cannot type; [parse, shortlist, pick](experiments/2026-11-14-parse-shortlist-pick.md) scored 0.13.

## The refinement loop

The agent-driven refinement loop (Loop C, `.claude/workflows/karpathy-loop.js`, `documentation/karpathy_loop_design.md`, `local-server/experiments/README.md`) can now target any implementation and configuration (PR #1597) that it has a backlog and gate margins for: `find_then_type` and two-pass, not `single_call`, so it must be told which. It has never run an iteration on the extraction benchmark. Its four past accepts optimised the short-passage corpus. Its accept margins for `find_then_type` are provisional until three paid re-recordings measure whole-take noise. The direction review recommends keeping it paused until the gold is human-checked. When it runs, each campaign records itself: one page under [experiments/](experiments/README.md) with its iterations generated from the ledger, and, on an accept, a line under the leads below. Its decision rule is its accept gate, fixed in code before a campaign starts.

## Leads from the refinement loop

A loop accept is one take judged by a margin below the noise threshold: a lead, not a result. It is listed here, and no number on this page moves, until a three-take experiment confirms it; then that experiment's page updates the numbers above and removes the line. The loop writes the lines between the markers (`local-server/experiments/campaign.py`).

<!-- loop:leads:start -->
None yet.
<!-- loop:leads:end -->

## Open decisions

1. **Decided 2026-11-17: one Opus 5.5 call finds and types individuals.** The user adopted it as the default (`single_call`) on the head-to-head's evidence (it won by the rule set in advance), at about $0.7-1.5 a document with its relate step against about $0.10 for `find_then_type`. The review's caution stands as a check on the decision, not a block: the gold is model-made and may favour single calls, and human-checked gold (next step 1) is what would confirm it.
2. **Relationships:** decided by the user (2026-11-17): the pipeline keeps a step that limits relationships to the allowed relationship types, and `single_call` runs it on Opus 5.5 (cost accepted), because a Haiku relate step roughly halved relationship recall in the [relationship experiment](experiments/2026-11-17-relationships.md). That experiment also found that one Opus call extracting individuals and relationships together, given the allowed types (R1), keeps to them completely and doubles dev recall over the Haiku relate step (0.315 against 0.159, every take), but does not beat it on the holdout (0.113 against 0.149). Still open: whether R1 beats the Opus relate step that `single_call` ships with; `single_call`'s one take (0.321 / 0.161) is close to R1 on dev and above it on the holdout.
3. **Proposals across implementations:** decided 2026-11-17, each implementation is its own pipeline. Every proposal a pipeline run makes (source extraction, schema extraction and refinement runs alike) records its origin: pipeline type, implementation, configuration, configuration version, and a digest of what that version made the run do (settings, the stage prompts the implementation resolved, defaults included, and the model, temperature and output limit it ran with). The digest exists because a built-in configuration stays at version 1 when its JSON file or a default prompt changes in code. It does not cover the implementation's own code, prompts that live in code included (all of the refinements' prompts). The origin is kept in the proposal's `client_metadata.origin`, returned as `origin` by the proposals API, and shown as a chip in the review queue, on the proposal page and on the source's Extract page. A whole run on a source supersedes only the open proposals of the same implementation, so proposals of different implementations stay open side by side for comparison. A proposal from before this change is treated as its run's implementation, and is left alone when its run is gone. Code: `PipelineSelection.origin` (`selection.py`), recorded for every implementation by `create_selected_run` through `ProposalService.recording`; the supersession rule is in `source_proposals.py`.

## Recommended next steps

From the [direction review](experiments/2026-11-14-direction-review.md), the [head-to-head](experiments/2026-11-15-head-to-head.md) and the [relationship experiment](experiments/2026-11-17-relationships.md), in order. The core's adoption (step 3, in part) and a first relationship measurement are done.

1. **Human-check the gold:** a person adjudicates the holdout gold and the "spurious" items, then the benchmark grows to 10 or more documents with human-confirmed gold and a real holdout nobody prompts against. Relationship gold needs it most: the measured gain is on dev only.
2. **Relationships in `single_call`:** measure R1 (one call given the allowed types, its relationships validated) against `single_call`'s Opus relate step, three takes each; R1 has only beaten a Haiku relate step. Switch only if R1 wins by the noise threshold, since it would also save the relate step's cost. A whole-document Opus relate call (R2-opus) is the other candidate; a whole-document Haiku call is not.
3. **The extraction core:** `single_call` was adopted on 2026-11-17 (decision 1). Still to do: confirm it on human-checked gold, measure its whole-take noise (three takes), and delete what loses, including `open_v1`.
4. **Measure value to a reviewer**, not only F1: time and acceptance when reviewing a proposal against modelling from scratch.

Stop doing: drawing conclusions from single recordings or differences under the noise threshold; scoring prompt experiments on the holdout; building more variants and tournament machinery before the measurement is trustworthy.

## Known gaps

None known.

## Where things live

| what | where |
|---|---|
| Implementations | `local-server/domain/pipelines/individual_extraction/` (`orchestrator.py` two-pass, `find_then_type.py`, `single_call.py`, `open_orchestrator.py`), `local-server/domain/extraction/` (`services.py`, `find_then_type.py`, `single_call.py`, `prompts.py`) |
| Configurations | `local-server/configs/*.json`, `local-server/domain/pipelines/*/configurations/` |
| Selection | `local-server/domain/pipelines/selection.py`, `registry.py` |
| Benchmark and scorer | `local-server/tests/integration/fixtures/pipelines/extraction_benchmark/`, `local-server/tests/integration/pipelines/_harness/benchmark.py` |
| Recordings | `local-server/tests/integration/fixtures/cassettes/extraction_benchmark*/`, `local-server/tests/integration/fixtures/pipelines/extraction_benchmark_external/` |
| Benchmark scripts | `local-server/scripts/benchmark_replay.py`, `benchmark_external.py`, `benchmark_relationships.py`, `quality_tournament.py` |
| Refinement loop | `.claude/workflows/karpathy-loop.js`, `documentation/karpathy_loop_design.md`, `local-server/experiments/` |
| Experiments | [experiments/](experiments/README.md) |

## Keeping this page current

How experiments are recorded, and when this page changes with them, is in [Recording an experiment](experiments/README.md#recording-an-experiment). In short: a verdict that changes anything stated here updates this page and its "As of" date in the same pull request as the experiment's page. The refinement loop changes only its leads and the date: its accepts are one take each, so they never move the numbers on this page.
