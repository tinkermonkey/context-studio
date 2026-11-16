# Two-pass baseline on the benchmark, and stronger models (2026-11-13)

**Question.** How does the two-pass pipeline (then the default) do on real documents, and does a stronger model fix it?

**Method.** The extraction benchmark (three documents with gold extractions; see [../README.md](../README.md#how-quality-is-measured)) run through the real pipeline, as a user's source runs: chunking, merge, proposal planning. One take per model.

## Baseline (Gemini 3 Flash, configuration `extraction-openrouter-default`)

| | found F1 | typed F1 | recall (core) | precision | type accuracy | relationship recall |
|---|---|---|---|---|---|---|
| dev mean | 0.411 | 0.114 | 0.342 (0.564) | 0.535 | 0.273 | 0.018 |
| holdout | 0.326 | 0.156 | 0.232 (0.289) | 0.548 | 0.478 | 0.000 |

Three re-recordings with nothing changed (temperature 0) gave dev found F1 0.405 to 0.411 and typed F1 0.109 to 0.117. These are the committed `default` benchmark recordings; `python scripts/benchmark_replay.py --implementation default` replays them.

Where it loses on dev: 126 gold individuals not found (41 core), 52 found but not typed correctly, 57 predictions matching nothing, 133 of 136 stated relationships missing. Statements are the largest gap: 2 of 41 motivation-layer individuals found.

## Stronger models in the same pipeline

| model | dev found F1 | dev typed F1 |
|---|---|---|
| Gemini 3 Flash | 0.411 | 0.114 |
| Claude Haiku 5.5 | 0.414 | 0.092 |
| Claude Sonnet 5.5 | 0.457 | 0.176 |
| Claude Opus 5.5 | 0.434 | 0.147 |

Running Claude 5.5 models needed two fixes: the Anthropic provider failed on a response that opens with a thinking block (fixed in PR #1594), and the pass-1 output cap of 8,000 tokens was too small for a model that thinks first (raised for the run; since PR #1598 the limit comes from the configuration).

## Verdict

A stronger model does not help this pipeline. The cause is its shape: pass 1 offers a shortlist of 50 class names retrieved by embedding similarity, with no definitions, and the right class is in a top-30 shortlist for only about half of gold individuals ([probes](2026-11-13-typing-and-decision-model-probes.md)). One call both finds and types, and the chunk merge keeps every class any chunk gave an individual. The direction review later called this a broken baseline rather than a weak method.

The pipeline is still registered as implementation `default` (now only a name), with configuration `extraction-default` on Claude Haiku 5.5, which is the setup that scored 0.092 here.
