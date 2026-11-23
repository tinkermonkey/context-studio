---
date: 2026-11-22
kind: experiment
implementations: [single_call]
models: [claude-opus-5-5, claude-haiku-5-5]
takes: 3
cost_usd: 10.02
verdict: inconclusive
reproducible: yes
---

# A pre-review stage before the person: splits and retypes (2026-11-22)

**Status: inconclusive by the rule set in advance (2026-11-23); the stage stays an optional configuration, off by default.** Phases 0-2 ran; Phase 3 did not, since it can only veto an adoption. The design is the DR changeset `extraction-pre-review-stage`. The user approved the design and the run, with a $40 cap, on 2026-11-23, and $10.02 was spent. The decision rule below was set before any paid run, and the stage's prompt was frozen in commit 0025ca74 before the first paid call.

**In short:** the stage catches errors that were planted (Phase 1) and almost none of the errors `single_call` makes (Phase 2). On real output it proposes 0-3 changes a document. The errors that matter on the human-checked document are risks typed as assessment, and the stage reads the definitions the same way the extractor does, so it leaves them alone. A second pass by a model of the same family does not catch a shared misreading.

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

### Phase 0 (2026-11-23, free, no model calls)

**The split witness marks all four of Gate D's splits**, so Phase 0's condition holds. It also marks many titles that are one item:

| document | gold titles marked | single_call's recorded titles marked |
|---|---|---|
| `edit_check` | 16 of 73 | 17 of 105 |
| `gitlab_architecture` | 6 of 122 | 12 of 124 |
| `wikimedia_enterprise` | 10 of 99 | 10 of 93 |

- Every marked gold title is one item by the gold, so on DR text the split question is asked mostly of traps: 32 of the 294 gold individuals.
- In the recordings, the split question would be asked of 39 of 322 extracted items, about one in eight.

**The seeds, as built** (`seeded`, same for any stage), per take:

| document | items | merges | realistic retypes | same-layer retypes | controls | split traps |
|---|---|---|---|---|---|---|
| `edit_check` | 70 | 3 | 6 | 6 | 41-44 | 11-14 |
| `gitlab_architecture` | 114 | 8 | 6 | 6 | 88-89 | 5-6 |

- **Fewer merges than planned.** `edit_check` has only three pairs of named, same-class individuals in one paragraph whose titles do not already read as lists, against the rule's 8. Over three takes Phase 1 has 33 merges, not 48. The split gate's 60% then rests on 33 trials, Wilson ±0.16 at 0.6. This is a fact about the gold, found before the prompt was frozen; the rule is unchanged.
- **Realistic retypes have plenty of candidates.** Every one of the 193 DR class definitions has a "Use X instead" sentence, and single_call's recordings add mistypes matched by name: 6 on `edit_check`, 2 on `gitlab_architecture` and 3 on the holdout. The holdout's are not used: Phase 1 seeds dev only.
- **The untouched items:** 447 controls and split traps over the three takes. A stage that harms none has a Wilson upper bound of 0.009, well inside the 6% bound.

**The scorer, checked with fake stages:**

| fake stage | outcome |
|---|---|
| keeps everything | recovers nothing, harms nothing, fails both gates |
| knows every seed | recovers all, harms nothing, passes both gates |

The unit tests cover fixes, harms, neutral changes, misses, splits whose parts miss a gold name, unsure answers and the Wilson interval (`tests/unit/test_harness_pre_review_seeded.py`, `tests/unit/domain/extraction/test_pre_review.py`).

**Input size, for the cost estimate.** single_call's recorded find call read 69,000-80,000 input tokens per document (most of it the cached catalog) and wrote 8,500-12,600 output tokens. The stage reads about as much, plus its numbered list of items, and should write less.


### Phase 1 (2026-11-23): seeded errors, two arms, three takes

**Both arms pass both questions' gates.** Spend: $1.37 of the $40 cap (12 calls: Haiku $0.05, Opus $1.32).

| arm | retype recovery (realistic) | split recovery | harms on 447 untouched items | Wilson upper | stage precision | gate |
|---|---|---|---|---|---|---|
| Haiku 5.5 | 0.86 (31 of 36) | 0.94 (31 of 33) | 4 retype, 0 split | 0.023 / 0.009 | 0.96 | pass, pass |
| Opus 5.5, effort medium | 0.83 (30 of 36) | 0.91 (30 of 33) | 4 retype, 1 split | 0.023 / 0.013 | 0.95 | pass, pass |

| arm | same-layer retype recovery | neutral changes (acceptable to acceptable) | unsure |
|---|---|---|---|
| Haiku | 0.81 (29 of 36) | 7 | 3 |
| Opus | 0.94 (34 of 36) | 4 | 0 |

**Harms come in bursts, one judgment applied to a group in one take.**

- **Haiku, `edit_check` take 1:** four rates moved from `apm.metricinstrument` to `motivation.assessment`, as "an experimental measurement reported as a finding".
- **Opus, `edit_check` take 3:** four risks moved from `motivation.driver` to `motivation.assessment`. These are the same items the person retyped from assessment to driver when checking this gold on 2026-11-18. In that take the stage reintroduced the model-made gold's reading, the one the person had rejected.
- Opus also split one split trap ("Link check and Reference reliability"). Haiku split none of the 54.
- Every other take had no harms.

**The human-checked document is the harder one.**

- Every harm, and most misses, are on `edit_check`.
- Realistic retype recovery on `edit_check`, per take:
  - Haiku: 0.50, 1.00 and 1.00;
  - Opus: 0.50, 0.83 and 0.67.
- On `gitlab_architecture` (model-made gold) both arms recover 0.83-1.00.
- Merges on `edit_check` (3 per take) were split in 2 or 3 of 3 by both arms, and all 8 per take on `gitlab_architecture`.

**Neutral changes are reviewer churn.** Both arms moved `editcheck/init.js` from application component to artifact in most takes, and Haiku moved the two persona groups to stakeholder. These count against no score, but the person sees each one.

**Cost per document pass, measured:**

| arm | first call, writing the catalog cache | later calls, reading it |
|---|---|---|
| Opus | $0.45 | $0.14-0.21 |
| Haiku | $0.014 | $0.006-0.009 |

- The catalog system prompt is 62,573 tokens, read from cache after the first call.
- The text and list are 15,700-23,500 tokens.
- Output was 3,200-5,100 tokens on Opus and 6,800-11,800 on Haiku.

**Limits of this phase:**
- The input is gold, so every item has a quote and a sensible title. Real extractions are noisier.
- The seeds are planted errors, not the errors single_call makes. Realistic retypes come from its recordings and from the definitions' "Use X instead" sentences.
- Six takes per arm, with seeds that differ by take, cannot separate the stage's noise from the seeds'.

**What it means for Phase 2.** Both arms go on with both questions.
- By the cheapest-source rule, Haiku is the likely pick unless Phase 2 separates the two by more than 10 points.
- The bursts of harms are the risk to watch: on `edit_check`, one take's group retype is enough to move typed F1 by about 0.05 on its own.


### Phase 2 (2026-11-23): the stage inside single_call, three paired takes

**Inconclusive for both arms.** Neither cut the reviewer's targeted edits. Neither lost typed F1 or relationship recall beyond the rule's guards.

**Spend:** $8.65 of the cap.
- $5.48 for the incumbent's takes 2 and 3. Take 1 is the committed recording.
- $1.27 for the Haiku arm and $1.95 for the Opus arm. Most of each arm's spend is the relate calls its changes made new.

**Targeted edits needed on `edit_check`** (retypes plus merged items, incumbent → arm, per take):

| arm | take 1 | take 2 | take 3 | cut |
|---|---|---|---|---|
| Haiku | 9 → 9 | 6 → 6 | 8 → 8 | 0% |
| Opus | 9 → 9 | 6 → 6 | 8 → 8 | 0% |

**Paired deltas against the incumbent, per take:**

| arm | typed F1, dev | typed F1, holdout | relationship recall, dev |
|---|---|---|---|
| Haiku | 0, 0, 0 | −0.006, 0, +0.010 | −0.028, 0, 0 |
| Opus | +0.007, 0, 0 | 0, 0, +0.004 | 0, 0, 0 |

**Fixes and harms on matched dev individuals:** 0 and 0 for both arms, so stage precision is undefined.

Check by check against the rule:

| check | Haiku | Opus |
|---|---|---|
| (a) edits cut by 30% in every take | fails | fails |
| (b) typed F1 guard | passes | passes |
| (c) relationship recall guard | passes | passes |
| (d) stage precision | undefined | undefined |
| reject condition | not met | not met |

**What the stage did on real output.**

- **Very few changes.** 0-3 per document per take on Haiku, 0-3 on Opus, mostly 0-1. In Phase 1 it gave 15-21 verdicts per seeded document.
- **What it changed:**
  - persona groups retyped to stakeholder;
  - two product editions retyped to artifact;
  - a launch retyped to business event;
  - "Systems administrators and GitLab Support Engineers" split. This is the one change that found a gold individual, worth +0.013 typed F1 on `gitlab_architecture` take 1;
  - "Link check and Reference reliability" split in two takes. That is one item in the gold;
  - a few multi-recommendation statements split on the holdout.
- **What the person would fix on `edit_check`, and the stage never touched:**
  - the six risks, typed as `motivation.assessment` in every take where the checked gold says `motivation.driver`;
  - a phase-1 analysis typed as `business.businessprocess`;
  - `Special:EditChecks`, typed as a feature, which the gold has as a view.

  The DR definition of Assessment, which the stage is given, names "an identified ... risk" as an example. Phase 1's Opus moved the same risks back to assessment. The extractor and the stage share the reading the person rejected when checking the gold.

**The incumbent's own spread, a by-product** (next step 3 of the current state):

| | take 1 | take 2 | take 3 |
|---|---|---|---|
| dev typed F1 | 0.535 | 0.557 | 0.587 |
| holdout typed F1 | 0.625 | 0.642 | 0.577 |
| `edit_check` relationship recall | 0.222 | 0.133 | 0.022 |

- Typed F1 spreads about 0.05 on dev and 0.065 on the holdout across takes.
- `edit_check`'s relationship recall swings widely between takes.

**Why Phase 3 was not run.** Phase 2 is inconclusive, and Phase 3 can only veto an adoption. Run for information, it would show whether the stage recovers your own 11 Gate D retypes. Five of them are DR retypes the extractor made, and on this evidence the stage is unlikely to catch them for the same reason.

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

**Inconclusive, by the rule set in advance.**

- Phase 1 passed for both arms and both questions.
- In Phase 2 neither arm cut the targeted edits, and neither arm was harmful.
- The stage stays an optional configuration, off by default. `SingleCallOrchestrator` runs it when a configuration has a `pre_review` setting; no built-in configuration has one.
- The changeset's parts that carry verdicts into a proposal (the `pre_review` field, the class alternative, the inspector note) are not built.

**What the evidence points to instead.** The reviewer's typing changes on DR text come from definitions the model reads differently from the person, not from a slip a second look would catch. Two places to act:

- **The class definitions themselves**, for example where Assessment and Driver draw their line on risks. These are DR spec matters, so they go to Context Studio as proposals.
- **Examples of the person's own decisions offered to the extractor.** The gold check's decisions are exactly these.

Splitting merged items found one real case on DR text in nine takes.

## Reproduce

Phase 0, from `local-server/`, free:

```bash
python scripts/benchmark_pre_review.py witness
python scripts/benchmark_pre_review.py seeded --fake keep
python scripts/benchmark_pre_review.py seeded --fake oracle
```

Phase 1, replayed free from the committed cassettes (`tests/integration/fixtures/cassettes/pre_review_seeded/`), with reports and the spend ledger under `tests/integration/fixtures/pipelines/extraction_benchmark_pre_review/`:

```bash
python scripts/benchmark_pre_review.py seeded --arm haiku
python scripts/benchmark_pre_review.py seeded --arm opus
```

Recording a missing take adds `--spend`, and needs a working Anthropic key in the configuration file. A worktree reads `local-server/.env`, whose `ANTHROPIC_API_KEY` was rejected on 2026-11-23, so these takes were recorded with `CONFIG_PATH` naming the main checkout's `config.json`.

Phase 2, replayed free from the committed cassettes (`tests/integration/fixtures/cassettes/pre_review_benchmark/` and single_call's committed recording as take 1), scored and judged by the rule:

```bash
python scripts/benchmark_pre_review.py benchmark
```

Recording the takes used `benchmark --arm off|haiku|opus --spend`, under the same `CONFIG_PATH`. Phase 3 has no subcommand: it was not run. Saved takes go under `tests/integration/fixtures/pipelines/extraction_benchmark_pre_review/`. Gate D's inputs come from the workspace database and are scratch; not reproducible from the repository.

## Links

- Design: DR changeset `extraction-pre-review-stage`
- Evidence: [Gate D](2026-11-21-gate-d-real-documents.md) (in [#1675](https://github.com/tinkermonkey/context-studio/pull/1675) until it merges), [#1453](https://github.com/tinkermonkey/context-studio/issues/1453)
- Review page limits it works around: [#1673](https://github.com/tinkermonkey/context-studio/issues/1673)
- DR's assessment pass: tinkermonkey/documentation_robotics#1248
