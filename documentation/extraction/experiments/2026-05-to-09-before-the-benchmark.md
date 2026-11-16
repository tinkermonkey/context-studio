# Before the benchmark: the triple-corpus era (2026-05 to 2026-09)

Individual extraction was first measured on a corpus of short passages written for the test and scored as subject-predicate-object triples (`local-server/tests/integration/fixtures/pipelines/individual_extraction/`). Everything on this page was measured on that corpus, or earlier on a public one, not on the extraction benchmark of real documents. Its numbers are not comparable with the benchmark's, and the main lesson of the period is that they were flattering.

## 2026-05: first baseline on Text2KGBench

The pipeline was scored on samples of TekGen and WebNLG (Text2KGBench). At the time the extraction endpoint was a stub returning no triples, so the recorded baseline is zero everywhere: a measurement of the harness, not of extraction.

Source: `local-server/documentation/graph-extraction-benchmarks.md`, `local-server/logs/extraction-iteration-log.md`.

## 2026-06: `open_v1`, a spaCy-based alternative

An "open" implementation for schema and individual extraction built on spaCy parses, clustering and a brute-force vector index (`domain/extraction/open_extraction.py`, `domain/pipelines/*/open_orchestrator.py`), with an offline closed loop over its configuration knobs (`scripts/quality_loop.py`).

- Rule mode, offline: individual F1 about 0.07, schema class Jaccard about 0.37; the loop's best tuning raised schema Jaccard to 0.47.
- It never met the production floors (individual precision 0.60, recall 0.50, F1 0.50).
- Verdict at the time: a high-recall research alternative, not a replacement.

It is still registered as implementation `open_v1` for both pipeline types. On the 2026-11 benchmark its recordings are stale and it is not scored. The direction review recommends deleting it.

## 2026-07: the refinement loop on the triple corpus

The two-pass LLM pipeline (pass 1 finds and types individuals against a class shortlist retrieved by embedding; pass 2 derives relationships) was refined by an agent-driven loop (Loop C, `documentation/karpathy_loop_design.md`). Its four accepted changes were: retrieval grounding in the class catalog, the two-pass split, label canonicalization, and relationship-object recall.

Final scores on the SME-written scenarios: dev strict F1 0.941, soft F1 0.952, candidate recall 0.992, label accuracy 0.982; holdout strict F1 0.841 on two scenarios.

Two corrections came out of that work, both measurement problems:

- About 44% of the scored split had been placeholder scenarios graded against a three-class throwaway ontology; they scored about 0 and halved the average. They were removed.
- Most of the remaining "missed candidates" were in three relabeled arXiv scenarios with retrofitted gold, which were moved to a non-gating tier.

Source: `documentation/individual_extraction_refinement_learnings.md`.

**What it turned out to mean.** The same two-pass pipeline scored typed F1 0.114 on real documents in November ([2026-11-13 baseline](2026-11-13-two-pass-baseline-and-stronger-models.md)). Short passages written for the test, mostly naming one thing per sentence, did not represent the task. The loop's four accepts optimised that corpus.

## 2026-09: `grounded_v1`, retrieval for typing

A variant that found candidates with spaCy noun chunks, retrieved candidate classes by vector similarity and asked an LLM to confirm one (`ExtractionService` in `extraction_mode="nlp_grounded"`).

| | `grounded_v1` | two-pass `default` |
|---|---|---|
| dev strict F1 | 0.027 | 0.917 |
| dev soft F1 | 0.317 | 0.928 |
| candidate recall | 0.863 | 0.992 |
| label accuracy | 0.120 | 0.982 |

Verdict: it finds candidates but picks the wrong class about 88% of the time; vector retrieval could not choose among the ontology's generic class definitions. The variant was later removed from the tournament (PR #1597); the `nlp_grounded` code path is still in `ExtractionService`. The [parse-shortlist-pick experiment](2026-11-14-parse-shortlist-pick.md) revisited the idea on real documents with the same result.

Source: project notes of 2026-09-15; recordings were committed at the time.
