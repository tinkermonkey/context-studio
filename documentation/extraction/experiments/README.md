# Extraction experiments

One page per experiment or review, oldest first. The current state they led to is in [../README.md](../README.md).

Read the numbers with these limits in mind: since 2026-11 everything is measured on a three-document benchmark whose gold was drafted and checked by models, not people; on that benchmark a difference under the noise threshold stated in [the current state](../README.md#how-quality-is-measured) is noise. Results before 2026-11 were measured on a different corpus and are not comparable. How to add a page: [Recording an experiment](#recording-an-experiment).

| date | page | question | result | verdict |
|---|---|---|---|---|
| 2026-05 to 09 | [Before the benchmark](2026-05-to-09-before-the-benchmark.md) | How do the pipelines do on short test passages? (Text2KGBench stub, `open_v1`, Loop C, `grounded_v1`) | Two-pass reached strict F1 0.94 on the short-passage corpus; `open_v1` about 0.07; `grounded_v1` 0.03 | The corpus flattered the pipeline: the same pipeline scored 0.11 on real documents |
| 2026-11-13 | [Two-pass baseline and stronger models](2026-11-13-two-pass-baseline-and-stronger-models.md) | How does the two-pass pipeline do on real documents, and does a stronger model help? | Typed F1 0.114 dev (Gemini Flash); Haiku 0.09, Sonnet 0.18, Opus 0.15 | A stronger model does not help; the shape does not work |
| 2026-11-13 | [Typing and decision-model probes](2026-11-13-typing-and-decision-model-probes.md) | Can Clef rate candidate classes with an LLM backstop? Where does typing fail? | Typing with the full catalog: Clef 75%, Haiku 80%, Opus 89%; embedding shortlists hold the right class for only about half; find-then-type prototype 0.43 (Haiku) / 0.55 (Opus) | Find first, then type against the whole catalog; Clef adds nothing as the final typer |
| 2026-11-13 | [`find_then_type` implementation](2026-11-13-find-then-type-implementation.md) | Does the prototype hold up as a real implementation? | Typed F1 0.465 dev, 0.481 holdout, about $0.10 a document | Adopted as the default implementation (2026-11-14) |
| 2026-11-14 | [Typing-catalog experiments](2026-11-14-typing-catalog-experiments.md) | Do whole class definitions help typing? How noisy is typing? | Whole definitions 0.446 vs 0.465; 16.5% of typing answers change between takes; rewording the "none" rule trades misses for mistypes | No change adopted |
| 2026-11-14 | [Parse, shortlist, pick](2026-11-14-parse-shortlist-pick.md) | spaCy units, top-5 classes by embedding, then Clef or Haiku picks with the chunk as context | Typed F1 0.13 (Haiku), 0.10 (Clef) vs 0.54 on the same document | Not worth pursuing; the shortlist and the parse lose most of the answers |
| 2026-11-14 | [Direction review](2026-11-14-direction-review.md) | An independent, deliberately critical review against the literature and off-the-shelf tools | "Narrow, don't replace": 0.11 to 0.47 repaired a broken baseline; the measurement is thin; the real competitor is one strong-model call | Recommendations listed in [../README.md](../README.md#recommended-next-steps) |
| 2026-11-15 | [Head-to-head](2026-11-15-head-to-head.md) | `find_then_type` against one call per document to Claude, three takes per arm | One Opus 5.5 call: typed F1 0.62 / 0.66 vs 0.45 / 0.44, but worse on relationships and 5-8 times the cost; one Sonnet or Haiku call does not win | Opus single call wins on individuals by the rule set in advance; not adopted yet (decision open) |

## Recording an experiment

These rules apply to people and agents alike.

**What needs a page.** Any run that spends money to measure extraction; any measured change to an extraction pipeline's stages, prompts or configurations; every refinement-loop campaign; any review of the direction. A free replay of existing recordings does not.

**The page.** Name it `YYYY-MM-DD-short-name.md` and start from [`_template.md`](_template.md), keeping its sections: question, decision rule, method, results, limits, verdict, reproduce, links.

**The decision rule comes first.** Write it on the page before the first paid run: the measure, the splits, and which difference adopts, rejects or is inconclusive.

**Evidence.**

- At least three takes for any claimed gain, with paired deltas against the incumbent (same document, same take index).
- A difference under the noise threshold stated in [the current state](../README.md#how-quality-is-measured) is not a result.
- The holdout document is never used for tuning: no prompt or rule is written or chosen by its score.
- A single take is labelled as one wherever its number appears.

**Data.** Commit what must replay, and put the command that replays it on the page. Anything else is named on the page with "scratch; not reproducible from the repository."

**Same pull request.** The page, its row in the table above, and, when the verdict changes anything [the current state](../README.md) says, that page and its "As of" date go in the same pull request.

**Nowhere else.** Extraction results do not go in `claudes_thoughts` reports, and not only in PR descriptions, scratch folders or session notes: link to the page from those instead.

**The refinement loop follows these rules by itself.** Each campaign (consecutive iterations against one implementation and configuration, from one driver) gets one page, `YYYY-MM-DD-loop-<implementation>[-<configuration>].md` (the configuration only when it is not the implementation's default; `-2`, `-3` for a second campaign the same day). The loop's record step (`local-server/experiments/campaign.py`) creates it on the campaign's first recorded iteration, regenerates its results table and verdict from the ledger at every iteration and when the loop stops, and keeps its row above current. These edits are committed with the ledger entries on the loop's integration branch and reach `main` with its promotion. An experimenter may not write under `documentation/extraction/`: only the record step does.

**A loop accept is a lead, not a result.** The loop's decision rule is its accept gate, fixed in code before the campaign starts. An accept is one take judged by a margin below the noise threshold, so it does not meet the evidence rules above: the record step lists it under "Leads from the refinement loop" on [the current state](../README.md#leads-from-the-refinement-loop) and updates its "As of" date, and no number there moves until a three-take experiment, with its own page, confirms it. A candidate that passed the gate but could not be merged is recorded as `accept_unmerged`, and is not a lead.
