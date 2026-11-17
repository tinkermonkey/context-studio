---
date: 2026-11-17
kind: experiment
implementations: [find_then_type]
models: [claude-haiku-5-5, claude-opus-5-5]
takes: 3
cost_usd: null
verdict: running
reproducible: yes
---

# Relationship extraction, measured with the allowed relationship types (2026-11-17)

Paths below are under `local-server/`. Harness: `scripts/benchmark_relationships.py` (arms, report), on top of `scripts/benchmark_external.py` (the single call, the saved takes, the scorer adapter). Saved takes: `tests/integration/fixtures/pipelines/extraction_benchmark_external/<arm>/`.

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
- Budget: $20.00, its own ledger (`ledger-relationships.jsonl`), at most two requests in flight. Actual cost: pending.
- Offline checks before any paid call: gold relationships over gold individuals, as an R2 take, score relationship recall and precision 1.0 with nothing dropped; R0's path with a stub provider gives the same individuals as arm B (typed F1 equal); every existing `benchmark_external.py replay` and `benchmark_replay.py --all` number is unchanged by the scorer change.

## Results

Pending.

## Limits

- The gold is model-made (drafted by Claude Fable 5.2, model-reviewed) and has not been checked by a person. Gold relationships are the ones the document states most plainly, so relationship precision is a lower bound.
- Three documents; per-document results differ a lot.
- R0 places the Opus individuals in chunks by quote and by title; `single_call` may place them differently.

## Verdict

Pending.

## Reproduce

```bash
# from local-server/, offline and free
python scripts/benchmark_relationships.py selftest
python scripts/benchmark_relationships.py report
python scripts/benchmark_external.py replay
```

## Links

- Pull requests: pending
- Ledger entries: `tests/integration/fixtures/pipelines/extraction_benchmark_external/ledger-relationships.jsonl`
