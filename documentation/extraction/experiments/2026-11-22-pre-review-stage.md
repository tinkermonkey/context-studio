---
date: 2026-11-22
kind: experiment
implementations: [single_call]
models: [claude-opus-5-5, claude-haiku-5-5]
takes: 3
cost_usd: null
verdict: open
reproducible: yes
---

# A pre-review stage before the person: splits and retypes (2026-11-22)

**Status: planned, not run.** The design is the DR changeset `extraction-pre-review-stage` (13 elements, staged on branch `claude/llm-review-stage-design-639ead`). Nothing is built and nothing has been spent. This page holds the decision rule before any paid run, as [the rules](README.md#recording-an-experiment) require. The user approves it, or changes it, before the first paid call.

## Question

Can an optional stage, run after `single_call` finds its individuals and before it relates them, cut the changes a person makes in review without losing quality? The stage asks two questions of each extracted element:

1. **Split:** is it one item or several?
2. **Retype:** is its class the best fit, compared with the classes it could be?

Why now: in [Gate D](2026-11-21-gate-d-real-documents.md) these two questions covered 15 of the person's 29 rejections and retypes (4 splits, 11 retypes).

What the evidence already says, before any run:

- **The split question has no DR evidence yet.** All 4 of Gate D's splits were House nodes, and House will never hold individuals from manuals. The DR document had no splits.
- **DR text is full of split traps.** In the benchmark gold, 36 of 294 individuals have titles that look compound but are one item: "Newcomers and Junior Contributors", "Chief Product and Technology Officer", goals such as "Make existing norms legible and actionable while editing". `edit_check` alone has 19 of 73.
- **The retype question is the one DR needs:** 5 of the 11 Gate D retypes were DR.
- **DR typing is often a judgment call.** 172 of the 294 gold individuals have acceptable other classes, so a retype between acceptable classes moves no score and still costs the person a look.

## Decision rule (set in advance)

Written before any paid run. The stage's prompt is written and frozen before Phase 1. A prompt changed after any result is a new arm, with its own three takes.

### Arms

- **Off:** `single_call` as shipped, the incumbent.
- **Opus:** the stage on Claude Opus 5.5, effort medium.
- **Haiku:** the stage on Claude Haiku 5.5.

Every stage arm reviews the same `find_individuals` output as the Off take with the same index (paired takes), and is then related by the same relate step.

### Counting

- **Fix:** a matched individual moves from an unacceptable class to the gold class or an acceptable one, or a merged element is split into parts that each match a gold individual.
- **Harm:** a matched individual moves from the gold class or an acceptable one to an unacceptable class, or a single item is split.
- **Neutral:** a move between acceptable classes. It is reported, and counted as neither a fix nor a harm.
- **Stage precision:** fixes / (fixes + harms).
- **Targeted edits needed:** the retypes and splits a person would still have to make to reach gold.

### Phase 0: free, no model calls

The prompt is not frozen until all of these hold:

- the split witness fires on all 4 of Gate D's splits;
- its fire rate on single_call's recorded titles and on the gold's compound single items is reported;
- the seed builder and the scorer pass their unit tests against a fake stage.

### Phase 1: seeded errors

**Input.** The dev gold (`edit_check` and `gitlab_architecture`) is given to the stage as if it were a perfect extraction: each gold title, its gold class, and its first evidence quote. Three takes, with a different random seed each. Per document and take:

- **8 merges:** two gold individuals of the same class whose evidence sits in one paragraph, joined as "A and B" or "A, B", with A's quote.
- **12 retypes:**
  - 6 realistic: a class `single_call` actually gave that item in a recording, or a class whose definition says to use the gold class instead;
  - 6 from the same layer, at random.
- **Controls:** every other gold individual, untouched, including the compound-looking single items.

**Gate to Phase 2, per question and per arm.** A question that fails its gate is removed from that arm's stage. An arm left with no question stops.

- **Retype:** it recovers at least 50% of the realistic retypes (to the gold class or an acceptable one).
- **Split:** it recovers at least 60% of the merges (each part matches its gold individual).
- **For both:** harms on the controls are at most 3%, with the Wilson 95% upper bound at most 6%.

### Phase 2: the benchmark

**Runs.** Three Off takes of `single_call` on all three documents. They also measure single_call's whole-take noise, which is [next step](../README.md#recommended-next-steps) 3. Each take is fed to each surviving arm. Measured against the gold, with `edit_check`'s human-checked gold deciding.

**Adopt an arm if all of these hold:**

- (a) On `edit_check`, targeted edits needed fall by at least 30% in the mean over the three takes, and fall in every take. `gitlab_architecture` (model-made gold) must not move the other way.
- (b) Typed F1, paired, falls by no more than 0.02 in the mean on dev and on the holdout, with no take below −0.04.
- (c) Relationship recall, paired, falls by no more than 0.03 in the mean on dev.
- (d) Stage precision is at least 0.7, pooled over the dev takes.
- (e) The Phase 3 veto does not fire.

**Reject if any of these hold:**

- stage precision is below 0.5;
- typed F1 falls by more than 0.04 in the mean;
- the veto fires.

**Otherwise inconclusive:** the stage stays an optional configuration, and the default is unchanged.

**If both arms pass:** Haiku is chosen if its cut in targeted edits is within 10 points of Opus's. The cheapest source of the same fixes wins.

The 0.08 noise threshold in [the current state](../README.md#how-quality-is-measured) applies to unpaired claims of a gain. This rule claims no typed-F1 gain. Its gain is in edits, and its typed-F1 terms are paired guards against loss.

### Phase 3: Gate D's reviewed runs, the real-world check

**Input.** The two Gate D proposals' individuals as proposed (title, class, quote) with their source text, read from the workspace database. Three takes per arm.

**Labels.** The user's own decisions:

- 222 accepted as proposed;
- 11 retyped, with the user's class;
- 4 split, by their rejection notes;
- the other rejections, reported only.

**Measures.**

- How many of the 11 retypes the stage proposes with the user's class.
- How many of the 4 splits it splits.
- **Veto:** the stage changes more than 5% of the 222 accepted-as-proposed items, in the mean over the takes.

DR (79 items) and House are reported apart, and only DR's numbers decide the veto. What the person changed that the stage did not touch is listed by kind: 5 of the 29 were "not an element". Each such kind is a candidate next question, not a change during this round.

### Never

- The holdout (`wikimedia_enterprise`) is never used to write or choose a prompt. It appears only in Phase 2's guard (b).
- No example from the benchmark or from Gate D is quoted in the prompt.

## Method

- **Implementation, configuration, model:** `single_call` with a new built-in configuration, `extraction-single-call-reviewed`. It is `extraction-single-call` plus `pre_review {enabled, model, effort, max_tokens, questions}`. Find and relate stay on Opus 5.5.
- **The stage:** one call per section (most documents are one section), against the same class catalog with whole definitions in a cached system prompt, given the text and the numbered individuals (title, class, quote). It answers per element:
  - keep;
  - split: the parts, each with a title, class and quote;
  - retype: the class, the class it was compared with, and the reasoning;
  - unsure: a question for the reviewer.

  The split question is asked only of elements the split witness marks. The retype question names the strongest other class, compares the two definitions, and changes the class only when the other is clearly better, citing the sentence that decides it.
- **Where verdicts go:** see the changeset.
  - A retype keeps the extracted class as a `class` alternative.
  - A split's parts name the original.
  - Both carry `pre_review` with the reasoning, shown in the Review inspector with a one-key restore for a retype.
  - Unreviewed elements are counted, never dropped.
- **Documents:** dev `edit_check` (human-checked gold) and `gitlab_architecture` (model-made gold); holdout `wikimedia_enterprise`; Gate D's two reviewed runs.
- **Takes per arm:** three, paired.
- **Budget:** a cap of $40, the user's to change. These estimates are scaled from measured one-call costs: one Opus call per document cost $0.64-0.90, one Haiku call about $0.02, and `single_call` with its relate step $0.7-1.5.

  | Phase | Estimate |
  |---|---|
  | 1 | about $3 |
  | 2 | about $19-26, of which the Off takes are $6-13 and double as next step 3 |
  | 3 | about $3-4 |

  A stage call on Opus is estimated at $0.3-0.6 a document, and on Haiku $0.02-0.05. Because runs do not record their cost (#1573), the harness records each call's input, cache and output tokens itself.

### What was taken from Documentation Robotics' assessment pass

From DR's assessment pass (tinkermonkey/documentation_robotics#1248: `docs/analyzers/SELF_ASSESSMENT_DESIGN.md`, `SELF_ASSESSMENT_RESULTS.md`, `cli/scripts/assess-eval/`; and the roadmap on branch `claude/assessment-roadmap`).

**Carried over:**

- **Questions kept as data.** Each question has a precondition (DR's "applies when" and "witnesses") and a fixed set of answers. The split witness is the free, deterministic precondition. As DR found with its review checks, it shows where to ask and never gives the answer.
- **One finding contract with a fixed verdict set.** keep, split, retype or unsure, with evidence (the quote and the sentence that decides) and cost. DR's `unsure` becomes a question to the person.
- **DR's budget rule:** an item the stage could not reach is reported as not reviewed, never dropped silently. The share reviewed is the stage's completion number.
- **Seeded-error scoring with strata and recovery levels.** DR ablates holes from a curated model; here gold individuals are merged and retyped. The number DR said to watch, false alarms on correct absences, becomes the harm rate on untouched controls.
- **Keep and drop rules per question, set in advance.** Keep at precision 0.7 or more, drop below 0.5, the cheapest source wins, Wilson bounds, three takes.
- **DR's step A and step B.** What the person still changed after the stage becomes the list of candidate questions.
- **In-sample caution.** No prompt is written against the holdout or quotes a benchmark or Gate D example.

**Not carried over:**

- The gap ledger and every free finder that reads the code graph (edge, path and frontier probes, name joins, peer patterns, fleet prior). Context Studio has unstructured text only.
- DR's question, completeness: missing elements and links. This stage changes what was found. It does not look for what was missed.
- The layer-pair triage call, and running questions through a coding agent with tools. Here the stage is one call in the pipeline.
- **Free seeded runs.** DR's seeded scoring cost nothing because its finders are deterministic. Here building and scoring the seeds is free (Phase 0), but each seeded run calls the stage, so Phase 1 is a small paid run.
- **A second model's agreement as a gate.** DR measured it useless for Tier 1 on 2026-11-16, so it is not used here.

**A shared limit:** seeded errors measure agreement with the reference. DR's caution that holes cut in an agent-shaped model test agreement with what the agent wrote applies to model-made gold. That is why `edit_check` (human-checked) and Gate D (the user's own decisions) decide, and `gitlab_architecture` only must not disagree.

## Results

None yet.

## Limits

- **The decision rests on thin evidence:**
  - one human-checked benchmark document of 73 individuals, about 15 of which `single_call` mistypes against it (type accuracy 0.791, one take);
  - two Gate D documents reviewed by one person.

  The seeded phase gives volume. Only the real sets give validity.
- **Gold dilutes retype claims.** 172 of the 294 gold individuals have acceptable other classes.
- **The split question may have nothing to fix on DR.** If so, its gate is mostly a test of not over-splitting.
- **Gate D is not a blind test.** Its items motivated the questions, though the prompt quotes none of them.
- **The stage may only agree with itself.** On Opus it shares a model and a catalog with the extraction it reviews.

## Verdict

Open: the user decides whether to run it.

## Reproduce

Planned: `python scripts/benchmark_pre_review.py seeded|benchmark|gate-d` from `local-server/`. Saved takes go under `tests/integration/fixtures/pipelines/extraction_benchmark_pre_review/`. Gate D's inputs come from the workspace database and are scratch; not reproducible from the repository.

## Links

- Design: DR changeset `extraction-pre-review-stage`
- Evidence: [Gate D](2026-11-21-gate-d-real-documents.md), [#1453](https://github.com/tinkermonkey/context-studio/issues/1453)
- Review page limits it works around: [#1673](https://github.com/tinkermonkey/context-studio/issues/1673)
- DR's assessment pass: tinkermonkey/documentation_robotics#1248
