# Typing and decision-model probes (2026-11-13)

**Question.** Could a decision model (Cloudflare's Clef, behind the `domain/decision` port) rate candidate classes for a chunk's individuals, with a stronger LLM adjudicating weak ones? More generally: where does typing fail, and what fixes it?

**Method.** Scratch scripts outside the repository, one run each, on the extraction benchmark. Most probes give the gold mention (title and passage) and measure only typing; the end-to-end prototype measures the whole shape. The scripts and their outputs were not committed; these are the results.

## Typing with the gold mention given (297 gold individuals)

| setup | accepted class |
|---|---|
| Clef, one choice among all 193 classes (220-character definitions) | 75.1% (top-3 93%, top-5 96%) |
| Clef Flash, same | 62.6% |
| Clef, layer first then class | 65% |
| Claude Haiku 5.5, full catalog (cached) | about 80% |
| Claude Sonnet 5.5, full catalog | 80% |
| Claude Opus 5.5, full catalog | 89% (top-3 98%) |
| Clef top-5, then Haiku picks | 86.2% |

- **Cues** (per-class conventions the definitions do not state) lifted Clef from 75% to 80% (product metrics 0 of 9 to 9 of 9) and Haiku from 80% to 82.5%. The cues were written from the gold's own rules, so this shows models obey cues, not that cues generalise.
- **Agreement as an auto-accept gate:** Clef and Haiku agree on 63-64% of mentions and are about 90% right when they do; Opus and Haiku agree on 70% at 93%; Clef's own confidence of 0.3 or more covers 38% at 93%.
- **Cost:** Clef with the full catalog cost about $0.004 per mention (no caching), roughly nine times Haiku with the catalog cached.

## Retrieval and mention finding

- **Embedding shortlists:** the gold class is in the top 30 by embedding similarity for only 49% of gold individuals with `all-MiniLM-L12-v2` (the app's model) and 63% with `all-mpnet-base-v2`. A vector shortlist in front of typing caps accuracy.
- **Find-only pass** (names and quotes, no typing), recall per document in one pass: Haiku 0.60-0.72, Sonnet 0.57-0.71, Opus 0.68-0.87, against 0.23-0.43 for the two-pass baseline. Haiku found 59 of 84 motivation statements (baseline 3). A second pass added about 5 points of recall and cost about 4 of precision.
- **GLiNER2** as a local mention finder (`gliner2.5-base-v1`, CPU): found 77% of non-motivation individuals (91% of core ones) but proposed 330-400 items per document with about 23% matching gold, almost no statements, and typed by layer no better than 27%.

## End-to-end prototype: find, then type each mention

One find-only pass per chunk; each distinct mention typed alone against the full catalog with definitions, "none" allowed.

| model | dev found F1 | dev typed F1 | holdout typed F1 | cost, three documents |
|---|---|---|---|---|
| Claude Haiku 5.5 | 0.535 | 0.429 | 0.413 | about $0.40 |
| Claude Opus 5.5 | 0.629 | 0.552 | 0.527 | about $6.90 |
| Haiku, with Clef choosing among Haiku's top three | | 0.396 | | |
| Opus, with Clef choosing among Opus's top three | | 0.510 | | |

## Verdict

- The shape, not the model, was the problem: find-then-type with the full catalog took typed F1 from 0.11 to 0.43 with Haiku. It was built as the `find_then_type` implementation ([next page](2026-11-13-find-then-type-implementation.md)).
- Clef did not improve typing as the final chooser. Its remaining possible role is gating by agreement, which has not been built.
- Do not put an embedding shortlist in front of typing.
