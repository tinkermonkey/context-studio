---
date: 2026-11-15
kind: experiment
implementations: [find_then_type]
models: [claude-haiku-5-5, claude-opus-5-5, claude-sonnet-5-5]
takes: 3
cost_usd: 6.01
verdict: adopted
reproducible: yes
---

# Extraction head-to-head: find_then_type vs one call to Claude (2026-11-15)

Question: keep the multi-stage individual-extraction pipeline (`find_then_type`, the app's default) or replace it with one call per document? Measured on the extraction benchmark (`edit_check` and `gitlab_architecture` dev, `wikimedia_enterprise` holdout), three takes per arm per document, scored by `tests/integration/pipelines/_harness/benchmark.py` unchanged, judged by a decision rule fixed before any run. Paths below are under `local-server/`. Merged as PR #1601. Harness: `scripts/benchmark_external.py`; saved takes: `tests/integration/fixtures/pipelines/extraction_benchmark_external/` (`python scripts/benchmark_external.py replay` re-scores them free). Total spend $6.01 (Anthropic only).

## Verdict

**Decided 2026-11-17:** the user adopted one Opus 5.5 call for finding and typing individuals as the default implementation (`single_call`), on this evidence, keeping the pipeline's schema-constrained relate step for relationships. See [the single-call implementation](2026-11-17-single-call-implementation.md). The gold is still model-made, not human-checked.

- **Individuals: one Opus 5.5 call beats the pipeline by more than the 0.08 bar on both splits.** Paired typed F1 +0.17 dev and +0.22 holdout; every one of six paired takes ahead by at least +0.155. It wins on precision (dev 0.70 vs 0.50), recall (0.63 vs 0.58) and type accuracy (0.94 vs 0.86) at once. By the rule: replace the pipeline core for finding and typing individuals.
- **Relationships: do not replace.** The single call's relationship recall is lower (dev 0.038 vs 0.164; both near zero on the holdout) and 92% of its relationships are not valid relationship types for the classes of their ends, because it was given the predicate list but not the allowed (domain, predicate, range) types that the pipeline's relate stage gets. It does relate the right pairs more often (pair recall 0.30 vs 0.18 dev), so a single call given the allowed types, or a constrained relate step after it, needs its own measurement.
- **Sonnet 5.5 and Haiku 5.5 in one call do not beat the pipeline.** Sonnet under-extracts (19-42 individuals per document against 76-122 in gold). Haiku ties on typed F1 by trading a third of recall for precision; decomposition is what gives Haiku its recall.
- **Cost:** Opus single call $0.64-0.90 per document with a cold cache (one call, 75-200 s) against $0.08-0.12 for the pipeline (160-240 calls, 2.5-4.5 min).

## Arms

| arm | what runs | model |
|---|---|---|
| A | `find_then_type` through the real pipeline: find per chunk, merge, type each distinct mention against the whole catalog (first 260 chars of each definition), relate per chunk with the predicates each subject class allows | configuration `extraction-find-then-type`, Claude Haiku 5.5 (default effort) |
| B | one call per document: whole `source.md`; cached system block (66,242 tokens) with all 193 classes and full definitions by layer, the 50 predicates with definitions, extraction rules carried over from A's prompts; structured output (class enum of 193, predicate enum of 50); adaptive thinking, effort high; streamed | `claude-opus-5-5` |
| B-sonnet | same call | `claude-sonnet-5-5` |
| B-haiku | same call | `claude-haiku-5-5` |

A take 1 is the committed recording; takes 2-3 were recorded live into a scratch folder through the same code path. The B prompt was written once before any B result and not changed; no few-shot examples, nothing from gold. Offline checks before any paid call: gold fed as predictions scores 1.0000 on every metric; A's recorded take through the adapter reproduces `benchmark_replay.py --implementation find_then_type` exactly.

## Results: mean over takes [min-max across takes]

| arm | split | found F1 | typed F1 | recall | core recall | precision | type acc. | rel. recall | rel. pair recall |
|---|---|---|---|---|---|---|---|---|---|
| A | dev | 0.529 [0.509-0.542] | 0.452 [0.426-0.465] | 0.579 | 0.835 | 0.498 | 0.859 | 0.164 | 0.176 |
| A | holdout | 0.488 [0.459-0.513] | 0.442 [0.393-0.481] | 0.461 | 0.623 | 0.519 | 0.903 | 0.018 | 0.018 |
| B | dev | 0.658 [0.648-0.667] | 0.624 [0.611-0.642] | 0.632 | 0.837 | 0.702 | 0.943 | 0.038 | 0.296 |
| B | holdout | 0.689 [0.674-0.707] | 0.659 [0.640-0.674] | 0.633 | 0.781 | 0.758 | 0.957 | 0.012 | 0.066 |
| B-sonnet | dev | 0.404 [0.370-0.421] | 0.371 [0.357-0.395] | 0.262 | 0.475 | 0.884 | 0.918 | 0.008 | 0.083 |
| B-sonnet | holdout | 0.460 [0.424-0.496] | 0.445 [0.409-0.482] | 0.316 | 0.544 | 0.848 | 0.968 | 0.006 | 0.006 |
| B-haiku | dev | 0.491 [0.482-0.504] | 0.450 [0.440-0.466] | 0.361 | 0.608 | 0.808 | 0.914 | 0.011 | 0.152 |
| B-haiku | holdout | 0.457 [0.412-0.541] | 0.439 [0.403-0.503] | 0.333 | 0.535 | 0.758 | 0.965 | 0.018 | 0.030 |

Per document, Opus typed F1: `edit_check` 0.49-0.50, `gitlab_architecture` 0.73-0.79, `wikimedia_enterprise` 0.64-0.67. Arm A's whole-take noise, measured here for the first time: dev 0.426-0.465, holdout 0.393-0.481.

## Paired deltas against A (same split, same take index) and the decision rule

| arm | typed F1 Δ dev [range] | typed F1 Δ holdout [range] | rel. recall Δ dev / holdout | outcome |
|---|---|---|---|---|
| B (Opus) | +0.172 [+0.155 to +0.186] | +0.217 [+0.182 to +0.247] | −0.127 / −0.006 | B ahead by more than 0.08 on both: replace the core |
| B-sonnet | −0.081 [−0.105 to −0.068] | +0.004 [−0.006 to +0.016] | −0.156 / −0.012 | splits disagree: inconclusive, leaning to the pipeline |
| B-haiku | −0.002 [−0.025 to +0.040] | −0.002 [−0.070 to +0.110] | −0.153 / 0.000 | tie by the letter of the rule; not advised (recall 0.36 vs 0.58 dev) |

Rule (fixed in advance, typed F1, dev and holdout): within ±0.05 prefer the single call for simplicity; single call ahead by more than 0.08 replace the core; pipeline ahead by more than 0.08 keep it; 0.05-0.08 inconclusive.

## Relationships

| arm | rel. recall dev / holdout | pair recall dev / holdout | relationships scored | schema-invalid |
|---|---|---|---|---|
| A | 0.164 / 0.018 | 0.176 / 0.018 | 290 | 0 (0%) |
| B (Opus) | 0.038 / 0.012 | 0.296 / 0.066 | 774 | 714 (92%) |
| B-sonnet | 0.008 / 0.006 | 0.083 / 0.006 | 113 | 105 (93%) |
| B-haiku | 0.011 / 0.018 | 0.152 / 0.030 | 241 | 213 (88%) |

Examples of Opus relating the right pair with the wrong predicate: "NGINX flows-to GitLab Workhorse" (gold `serves`), "Sidekiq uses Redis" (gold `depends-on`), "Gitaly serves GitLab Shell" (gold the reverse `uses`). On the holdout every arm is near zero: relationship extraction is unsolved on this benchmark whichever way it is done.

## Cost per document

| arm | edit_check | gitlab_architecture | wikimedia_enterprise | mean latency s |
|---|---|---|---|---|
| A | $0.110 | $0.124 | $0.078 | 244 / 260 / 147 |
| B (Opus), measured / cold cache | $0.565 / $0.78 | $0.580 / $0.90 | $0.321 / $0.64 | 146 / 172 / 99 |
| B-sonnet, measured / cold | $0.101 / $0.21 | $0.107 / $0.27 | $0.054 / $0.21 | 12 / 39 / 19 |
| B-haiku, measured / cold | $0.014 / $0.02 | $0.012 / $0.02 | $0.011 / $0.02 | 68 / 62 / 63 |

A user extracting one document usually pays the cache write (the 66K-token catalog: $0.33 to write with Opus). A 100-document corpus: about $65-90 with Opus single calls against about $10 with the pipeline. The longest document (46K characters) used 28.7K Opus output tokens including thinking; a document several times longer could approach the 64K output limit and would need chunking again (untested).

Prices used (per MTok input / 5-minute cache write / cache read / output, from the claude-api reference): Opus 5.5 $4 / $5 / $0.20 / $20; Sonnet 5.5 $2 / $2.50 / $0.10 / $10; Haiku 5.5 $0.10 / $0.125 / $0.01 / $0.50.

## Limits

- Three documents; per-document results differ a lot.
- Model-made gold: drafted by Claude Fable 5.2 reading whole documents with full DR definitions, then model-reviewed. The single-call arms work the same way (whole document, full definitions), which may favour them over a chunked pipeline with 260-character definitions; this benchmark cannot say how much of Opus's lead that explains. Human-checked gold is needed before committing to the higher cost.
- The holdout was used in earlier prompt work on A, which favours A, not B.
- Three takes per arm.
- The comparison is "the pipeline as shipped" (Haiku, default effort, 260-character definitions) against "one call" (full definitions, effort high), not decomposition with the model held equal; B-haiku is the nearest to that.
- No relationship precision is scored.

## What went wrong

- Running all arms at once hit the organisation's concurrent-request limit: four Sonnet/Haiku requests were refused before starting (not billed) and re-run; arm A take 3 aborted on `edit_check` (about $0.10 wasted) and was recorded again on its own.
- All 27 single-call takes ended normally with valid JSON on the first attempt.
- Arm A take 1 predates per-call metering, so its cost is an estimate and its latency unknown.
- The in-app predicates carry no definitions; the single-call prompt took them from the DR spec bundle.
