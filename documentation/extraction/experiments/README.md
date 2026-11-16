# Extraction experiments

One page per experiment or review, oldest first. The current state they led to is in [../README.md](../README.md).

Read the numbers with these limits in mind: since 2026-11 everything is measured on a three-document benchmark whose gold was drafted and checked by models, not people; on that benchmark a difference under about 0.08 typed F1 is noise. Results before 2026-11 were measured on a different corpus and are not comparable.

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

## Adding a page

Name it `YYYY-MM-DD-short-name.md`. Say the question, the method (documents, model, takes, cost), the numbers, the limits, and a verdict, and add a row above. Then update [../README.md](../README.md) if the verdict changes the current state.
