---
date: 2026-11-17
kind: experiment
implementations: [find_then_type]
models: [claude-haiku-5-5, claude-opus-5-5]
takes: 3
cost_usd: 7.43
verdict: open
reproducible: yes
---

# Relationship extraction, measured with the allowed relationship types (2026-11-17)

Paths below are under `local-server/`. Harness: `scripts/benchmark_relationships.py` (arms, report), on top of `scripts/benchmark_external.py` (the single call, the saved takes, the scorer adapter). Saved takes: `tests/integration/fixtures/pipelines/extraction_benchmark_external/<arm>/`. The decision rule was committed before the first paid call. Total spend $7.43 of a $20 cap (Anthropic only).

**In short:** given the allowed relationship types, one Opus 5.5 call that extracts individuals and relationships together (R1) keeps to them completely (0 of 466 relationships invalid) and nearly doubles dev relationship recall over the planned default's per-chunk relate stage (R0): 0.315 against 0.159, every take ahead, precision no worse. By the rule set in advance R1 is recommended. On the holdout neither R1 nor a whole-document relate call beats R0 (0.113 and 0.131 against 0.149), so the gain is shown on dev only.

## Question

The planned default for individuals is one Opus 5.5 call (`single_call`), followed by `find_then_type`'s per-chunk relate stage, which offers each subject class only the predicates the schema allows from it. The [head-to-head](2026-11-15-head-to-head.md) left relationships open: every approach was near zero on the holdout, and the single call related the right pairs more often but used relationship types the schema does not allow, because it was not given them. The user decided (2026-11-17) that the pipeline keeps a step that limits relationships to the allowed relationship types. This experiment asks which way of producing those constrained relationships is best: the per-chunk relate stage over the Opus individuals, one Opus call that finds individuals and relationships given the allowed types, or one relationship call that reads the whole document.

## Decision rule (set in advance)

Written and committed before any paid run.

**Measure.** Relationship recall against gold (predicate and direction must match), after dropping every relationship that is not an allowed type for the classes of its ends. Secondary: relationship precision against gold (`relationship_precision`, added to the scorer by this experiment; a lower bound, because gold holds the plainly stated relationships, not every correct one). For R1, which also finds the individuals, typed F1 as a guard. Per take, a split's value is the mean over its documents; paired deltas compare the same take index.

**Splits.** Dev (`edit_check`, `gitlab_architecture`) decides; the holdout (`wikimedia_enterprise`) can only veto. No prompt in this experiment is changed after a result is seen.

**For each challenger X (R1, R2-haiku, R2-opus) against R0:**

- **Recommend X over R0** when all of these hold: the mean paired Δ relationship recall on dev is at least +0.08 (the noise threshold stated in [the current state](../README.md#how-quality-is-measured)) and every one of the three dev paired deltas is positive; the mean paired Δ relationship precision on dev is not below −0.05 (no buying recall with a flood); the holdout mean Δ relationship recall is not below −0.08. For R1 also: its mean typed F1 is not more than 0.08 below arm B's (the Opus single call without the types) on either split.
- **Keep R0** when R0 is ahead on dev relationship recall by 0.08 or more, or when X misses the bar.
- **Inconclusive** (keep R0, which is what is being built) for anything else, including X clearing the recall bar but failing a guard.

**Among challengers that pass:** prefer R1 (one call, no separate stage) unless an R2 arm beats it on dev relationship recall by 0.08 or more; prefer R2-haiku over R2-opus unless R2-opus beats it by 0.08 or more (cost). Cost per document is reported beside every result and named in the verdict.

**Diagnostics** (one take each, labelled as such, not part of the rule): R0 and R2 given the gold individuals, to separate errors in relating from errors in the individuals.

## Method

| arm | what runs | model |
|---|---|---|
| R0 (baseline) | `find_then_type`'s relate stage, through the real pipeline (chunking, relate per chunk with the predicates each subject class allows and their target classes as hints, recognition, merge, planning), over the individuals of arm B's take of the same index. The find and type stages are not called: they are answered from that take (`GivenIndividualsService`). An individual is mentioned in each chunk its quote overlaps and in each chunk where its title appears as words. Planning drops relationships that are not an allowed type | configuration `extraction-find-then-type`, Claude Haiku 5.5 |
| R1 | arm B's one call per document (the whole source, the class catalog with full definitions, the predicates, structured output, adaptive thinking at effort high), with all 987 allowed relationship types added to the cached system text, grouped by source class as `predicate -> target classes`, and the rule that every relationship must be one of them | `claude-opus-5-5` |
| R2-haiku, R2-opus | one call per document over the whole source, given the individuals of arm B's take of the same index (title and class), the definitions of the predicates in play, and only the allowed types whose two classes are among those individuals; structured output with the titles and predicates as enums; adaptive thinking at effort high | `claude-haiku-5-5`, `claude-opus-5-5` |
| R0-gold, R2-haiku-gold, R2-opus-gold | diagnostics: R0 and R2 given the gold individuals; one take | as above |

R1 and R2 restrict their output to the allowed types by validation: a relationship whose (source class, predicate, target class) is not a relationship type of the schema is dropped when scored, and counted. R0 and R2 are paired by take with the same Opus individuals, so they differ only in how relationships are produced. Reference rows, free from the saved takes: arm A (`find_then_type` as shipped), arm B as recorded, and arm B with its invalid relationships dropped.

- Documents: `edit_check`, `gitlab_architecture` (dev), `wikimedia_enterprise` (holdout).
- Takes per arm: three (diagnostics one).
- Budget: $20.00, its own ledger (`ledger-relationships.jsonl`), at most two requests in flight. Actual cost: $7.43 (R1 $4.17, R2-opus $2.16, R2-opus-gold $0.81, R0 $0.13, R2-haiku $0.08, R0-gold $0.05, R2-haiku-gold $0.03).
- Offline checks before any paid call: gold relationships over gold individuals, as an R2 take, score relationship recall and precision 1.0 with nothing dropped; R0's path with a stub provider gives the same individuals as arm B (typed F1 equal); every existing `benchmark_external.py replay` and `benchmark_replay.py --all` number is unchanged by the scorer change.

## Results

Mean over takes [min-max across takes]; a take's split value is the mean over the split's documents. "Kept" is relationships scored per document after validation; "invalid" is how many the arm listed that are not an allowed type (all dropped for R1 and R2). Relationship precision is against gold, so a lower bound; "resolved" counts only relationships whose two ends are found gold individuals. The `-gold` rows are diagnostics, one take each.

| arm | split | rel. recall | rel. precision | precision (resolved) | pair recall | typed F1 | kept | invalid | $ per doc |
|---|---|---|---|---|---|---|---|---|---|
| R0 (baseline) | dev | 0.159 [0.114-0.186] | 0.326 [0.226-0.415] | 0.426 [0.250-0.566] | 0.170 | 0.623 | 34 | 0 | 0.017 (+ B's call) |
| R0 | holdout | **0.149** [0.125-0.161] | 0.303 [0.189-0.360] | 0.390 [0.292-0.450] | 0.167 | 0.659 | 29 | 0 | 0.010 (+ B's call) |
| R1 | dev | **0.315** [0.263-0.353] | **0.374** [0.336-0.418] | 0.617 [0.580-0.667] | 0.340 | 0.660 | 61 | 0 of 61 | 0.551 |
| R1 | holdout | 0.113 [0.071-0.179] | 0.200 [0.098-0.286] | 0.383 [0.267-0.526] | 0.125 | 0.628 | 33 | 0 of 33 | 0.287 |
| R2-haiku | dev | 0.045 [0.021-0.068] | 0.314 [0.274-0.350] | 0.532 [0.433-0.600] | 0.051 | 0.624 | 12 | 0 | 0.010 (+ B's call) |
| R2-haiku | holdout | 0.107 [0.089-0.125] | 0.336 [0.250-0.455] | 0.475 [0.286-0.583] | 0.107 | 0.659 | 19 | 0 | 0.008 (+ B's call) |
| R2-opus | dev | 0.300 [0.234-0.349] | 0.282 [0.248-0.302] | 0.546 [0.513-0.601] | 0.333 | 0.624 | 72 | 0 | 0.283 (+ B's call) |
| R2-opus | holdout | 0.131 [0.071-0.161] | 0.277 [0.103-0.429] | 0.471 [0.222-0.692] | 0.143 | 0.659 | 30 | 0 | 0.155 (+ B's call) |
| *R0-gold (one take)* | dev | 0.307 | 0.731 | 0.731 | 0.338 | 1.000 | 30 | 0 | 0.018 |
| *R0-gold (one take)* | holdout | 0.607 | 0.694 | 0.694 | 0.607 | 1.000 | 49 | 0 | 0.015 |
| *R2-haiku-gold (one take)* | dev | 0.189 | 0.958 | 0.958 | 0.189 | 1.000 | 12 | 0 | 0.010 |
| *R2-haiku-gold (one take)* | holdout | 0.500 | 0.875 | 0.875 | 0.500 | 1.000 | 32 | 0 | 0.008 |
| *R2-opus-gold (one take)* | dev | 0.653 | 0.731 | 0.731 | 0.678 | 1.000 | 65 | 0 | 0.282 |
| *R2-opus-gold (one take)* | holdout | 0.768 | 0.860 | 0.860 | 0.768 | 1.000 | 50 | 0 | 0.242 |

Reference rows, free from the head-to-head's saved takes:

| arm | split | rel. recall | rel. precision | pair recall | typed F1 | kept | invalid | $ per doc |
|---|---|---|---|---|---|---|---|---|
| A (`find_then_type` as shipped) | dev | 0.164 [0.127-0.186] | 0.322 | 0.176 | 0.452 | 38 | 0 | 0.110-0.124 |
| A | holdout | 0.018 [0.000-0.036] | 0.048 | 0.018 | 0.442 | 22 | 0 | 0.078 |
| B (Opus single call, predicates only) | dev | 0.038 [0.034-0.040] | 0.026 | 0.296 | 0.624 | 98 | 90 of 98 (92%) | 0.573 |
| B | holdout | 0.012 [0.000-0.018] | 0.010 | 0.066 | 0.659 | 61 | 58 of 61 (95%) | 0.321 |
| B with invalid types dropped | dev | 0.026 [0.018-0.034] | 0.223 | 0.032 | 0.624 | 8 | dropped | 0.573 |
| B with invalid types dropped | holdout | 0.012 [0.000-0.018] | 0.167 | 0.012 | 0.659 | 3 | dropped | 0.321 |

Per document, relationship recall [min-max over takes]: R0 `edit_check` 0.00-0.09, `gitlab_architecture` 0.23-0.28, `wikimedia_enterprise` 0.12-0.16; R1 0.19-0.28, 0.34-0.52, 0.07-0.18; R2-opus 0.09-0.26, 0.37-0.43, 0.07-0.16.

### Paired deltas (same take index) and the decision rule

| pair | split | Δ rel. recall [by take] | Δ rel. precision [by take] | Δ typed F1 [by take] |
|---|---|---|---|---|
| R1 − R0 | dev | **+0.156** [+0.142, +0.177, +0.149] | +0.049 [+0.003, +0.033, +0.110] | +0.037 |
| R1 − R0 | holdout | −0.036 [−0.036, +0.018, −0.089] | −0.103 [+0.028, −0.074, −0.262] | −0.031 |
| R2-opus − R0 | dev | **+0.141** [+0.132, +0.173, +0.119] | −0.043 [−0.113, −0.040, +0.022] | 0 (same individuals) |
| R2-opus − R0 | holdout | −0.018 [−0.054, 0.000, 0.000] | −0.026 [−0.087, +0.069, −0.060] | 0 |
| R2-haiku − R0 | dev | −0.114 [−0.139, −0.108, −0.093] | −0.012 [−0.098, +0.014, +0.048] | 0 |
| R2-haiku − R0 | holdout | −0.042 [0.000, −0.071, −0.054] | +0.033 [+0.115, +0.095, −0.110] | 0 |
| R1 − B (R1's typed F1 guard) | dev | +0.277 | +0.349 | +0.036 [+0.050, +0.047, +0.011] |
| R1 − B | holdout | +0.101 | +0.190 | −0.031 [−0.017, −0.048, −0.029] |
| R2-opus − R2-haiku | dev | +0.255 [+0.272, +0.281, +0.212] | −0.031 | 0 |

Applying the rule:

| challenger | dev Δ recall ≥ +0.08, all takes positive | dev Δ precision ≥ −0.05 | holdout Δ recall ≥ −0.08 | typed F1 within 0.08 of B | outcome |
|---|---|---|---|---|---|
| R1 | +0.156, yes | +0.049, yes | −0.036, yes | +0.036 / −0.031, yes | **passes** |
| R2-opus | +0.141, yes | −0.043, yes | −0.018, yes | (same individuals) | passes |
| R2-haiku | −0.114: R0 ahead by more than 0.08 | | | | keep R0 over it |

Among those that pass, R1 is preferred unless an R2 arm beats it on dev relationship recall by 0.08 or more: R2-opus is 0.015 behind it. **R1 is the arm the rule recommends.**

### What the numbers say beyond the rule

- **Given the allowed types, Opus keeps to them.** R1 listed 466 relationships and R2-opus 519; none was invalid, so validation dropped nothing. Arm B, given only the predicates, listed 92% invalid. Pair recall and recall are now close (R1 0.340 / 0.315), so the predicate is no longer what loses relationships: arm B related the right pairs (pair recall 0.296) but with predicates the schema does not allow.
- **The individuals were the holdout's problem.** The same per-chunk relate stage scores holdout recall 0.018 over `find_then_type`'s individuals (A) and 0.149 over Opus's (R0).
- **Relating is limited by the individuals, and by the relate model.** Given the gold individuals, a whole-document Opus call recovers 0.65 (dev) and 0.77 (holdout) of gold relationships at precision 0.73-0.86; the per-chunk Haiku stage 0.31 and 0.61; with Opus's own individuals both fall to 0.13-0.30. A relationship counts only when both its ends match gold individuals, so better individuals lift every arm.
- **Haiku over the whole document is too cautious:** precise (0.96 resolved with gold individuals) but it lists few relationships (12 per dev document), even fewer than the per-chunk Haiku stage.
- **Cost:** R1 is one call, $0.29-0.60 a document as measured (its 79K-token system text read from the cache; about $0.39 more for a cold cache), about the cost of arm B alone; R0 adds $0.01-0.02 to arm B's call; R2-opus adds $0.16-0.32.

## Limits

- The gold is model-made (drafted by Claude Fable 5.2, model-reviewed) and has not been checked by a person. Gold relationships are the ones the document states most plainly, so relationship precision is a lower bound, and the drafting (whole document, full definitions) resembles R1 and R2 more than the per-chunk stage.
- Three documents; per-document results differ a lot (R1's `gitlab_architecture` recall ranges 0.34-0.52).
- The gain is on dev only. On the holdout no challenger beats R0, and R1's holdout precision is 0.10 below R0's; the rule lets the holdout veto only a loss of more than 0.08 in recall. One holdout document with 56 gold relationships cannot carry more.
- The 0.08 threshold is borrowed from typed F1; the take-to-take range of relationship recall here is up to 0.09 (R1 dev 0.263-0.353), close to it. Every paired dev take agreeing in sign is what makes R1's and R2-opus's gains more than noise.
- R0 places the Opus individuals in chunks by quote and by title; `single_call` may place them differently.
- R1 changes the individuals call too (its typed F1 differs from B's by +0.036 dev and −0.031 holdout, both under the noise threshold); R0 and R2 relate arm B's individuals unchanged.
- The relationship prompts were written once before any result and not tuned.

## What went wrong

- Nothing failed: all 33 call takes ended normally with valid JSON on the first attempt, and every R0 chunk's relationships were read. Runs were kept to two requests in flight by running arms one after another.
- R2-haiku's few relationships were seen after its first take; the prompt was not changed, as the rule requires.
- The credentials were read through `CONFIG_PATH` only: the worktree guard refused to source the main checkout's `.env` into the command, and the key resolved from the configuration.
- The scorer change adds metrics and counts; every existing number of `benchmark_external.py replay` and `benchmark_replay.py --all` was checked identical before and after.

## Verdict

**Open, with a recommendation: R1.** By the rule set in advance, one Opus 5.5 call given the allowed relationship types, extracting individuals and relationships together, beats the per-chunk relate stage over the same model's individuals by +0.156 dev relationship recall (every take), at no loss of precision, with typed F1 unchanged within noise and at about the cost of the individuals call alone. The constrained step the user decided to keep stays: the call is given the allowed types and its output is validated against them (nothing needed dropping here). For the planned `single_call` implementation this means: give its call the allowed relationship types and take its relationships, validated, instead of running the per-chunk relate stage. Not adopted in code here; the holdout does not confirm the gain, so confirm it on human-checked gold and more documents before relying on it. A whole-document Opus relate stage (R2-opus) is the fallback if individuals and relationships must stay separate calls; whole-document Haiku is not.

## Reproduce

```bash
# from local-server/, offline and free
python scripts/benchmark_relationships.py selftest
python scripts/benchmark_relationships.py report
python scripts/benchmark_external.py replay
```

Re-recording (paid; `--spend` required): `run --arm <R1|R2-haiku|R2-opus|R2-*-gold> --take N`, `record-r0 [--gold] --take N --cassettes <scratch folder>`. R0's relate recordings were kept in a scratch folder (scratch; not reproducible from the repository); its saved takes are committed, so the numbers replay.

## Links

- Pull requests: pending
- Ledger entries: `tests/integration/fixtures/pipelines/extraction_benchmark_external/ledger-relationships.jsonl`
