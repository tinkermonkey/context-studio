---
date: 2026-11-14
kind: review
implementations: [find_then_type, default, open_v1]
models: []
takes: null
cost_usd: 0
verdict: n/a
reproducible: n/a
---

# Extraction direction review — 2026-11-14

Scope: individual and relationship extraction against the Documentation Robotics (DR) taxonomy, as on
`origin/main` at `4cfc996d` plus open PRs #1597–#1600. Method: read the pipelines, benchmark, scorer, gold,
refinement loop and ledger; re-ran both offline replays; re-scored the recorded outputs with my own scripts
(no LLM calls); compared against current literature and tools. Written to be critical, as asked.

> Written by an independent Claude Opus 5.5 session on 2026-11-14, before the decisions and the
> experiment it recommended. Since then: `find_then_type` became the default implementation (PR #1598),
> and the head-to-head it proposed was run ([2026-11-15-head-to-head.md](2026-11-15-head-to-head.md)).
> The current state is in [../README.md](../README.md).

---

## Verdict

**The work is converging, but on something narrower and more ordinary than it looks, and the evidence
is too thin to say how good it is.**

- **The jump from typed F1 0.11 to 0.47 mostly repaired a broken baseline.** It is not a new method.
  The old two-pass pipeline showed the model only 50 class *names*, retrieved by embedding, with no
  definitions. The right class was missing about half the time, and the prompt told the model to pick the
  "closest" class anyway. No model could do well in that shape, which is why Sonnet and Opus did not help.
  `find_then_type` does what the literature treats as the standard: find mentions, then type each one with
  the catalog and its definitions in context. It is the right shape and should be the default today.
  After PR #1598 the app's default is still the old shape, and with Haiku 5.5, which scored 0.09 there:
  the worst setup measured.
- **0.47 is about what competent zero-shot LLM extraction gets, not a moat.** Strict name matching
  understates it a little: about 0.49 dev and 0.50 holdout once obvious name variants count
  (section 1.4). Frontier models reach entity F1 0.52–0.69 one-shot on a much easier, human-annotated,
  sentence-level ontology benchmark ([Text2KGBench-LettrIA, ISWC 2025](https://ceur-ws.org/Vol-4041/paper3.pdf)).
  Off-the-shelf graph builders score 0.45–0.57 untyped triple F1 on short abstracts
  ([Yamamoto et al., ISWC 2025 companion](https://ceur-ws.org/Vol-4085/paper49.pdf)).
- **In user terms the proposal is still weak.**
  - Recall 0.56 overall is below every positive pre-annotation study found, which sit near 0.86. Core
    recall is 0.81 dev and 0.66 holdout.
  - On one document (Edit check) 62 of 104 counted proposed items match nothing in gold.
  - Relationships are nearly absent: holdout recall is 2 of 56. A reviewer still has to read the whole
    document, and research on reviewing suggestions says reviewers rarely add what was missed.
- **No off-the-shelf extractor is built for this task.**
  - GraphRAG-style tools impose a handful of entity types and merge entities by exact name. None reports
    extraction precision or recall against a gold graph.
  - Schema-guided frameworks (LlamaIndex, LangChain, neo4j-graphrag, LangExtract) are prompt-and-validate
    wrappers with no published accuracy at this scale.
  - The real competitor is a ~150-line script: one strong-model call with the full catalog and structured
    output. We have never run it, and that is the most important missing experiment.
- **The measurement is not yet trustworthy.**
  - Three documents (15k words), 297 gold items, and only 51 of the 193 classes appear in gold.
  - The gold was drafted by Claude Fable 5.2 and adjudicated by model reviewers. The README calls it
    "hand-made", but I found no record of a human pass.
  - Each result is a single recording. 59% of gold items accept more than one class.
  - The one holdout document has been scored during prompt experiments.
  - The 95% interval on typed F1 from item sampling alone is about ±0.05 (dev) and ±0.07 (holdout), before
    run-to-run and document variance. Differences under about 0.08 are not results.
- **The refinement loop has not paid for itself.** Every one of its four accepts optimized the old
  short-passage corpus, where the pipeline scored strict F1 0.94 while scoring 0.11 on real documents. It
  has run zero iterations on the benchmark. The gain that mattered came from a human-directed probe.

**Recommendation: narrow, don't replace.** Keep the ontology tooling, proposals and review queue,
recognition and dedup, provenance, and the benchmark. These are what is different here. Shrink extraction
to one pipeline. Run a paired head-to-head between `find_then_type` and a single-call strong-model
baseline (about $15–25), and adopt whichever wins. Then spend effort on measurement, not pipeline
variants:
- human-confirmed gold on 10 or more documents;
- 3 recordings per arm;
- a reviewer-acceptance and time metric.

Top five actions:
1. Make `find_then_type` the default.
2. Run the single-call baseline head-to-head.
3. Have a human adjudicate the holdout gold and the 128 "spurious" items.
4. Rebuild relationships as one document-level stage.
5. Pause Loop C and delete `open_v1` and the two-pass individual path once the head-to-head is in.

---

## 1. What we have, and what the evidence for it is worth

### 1.1 Pipelines

| Implementation | What it really does | Evidence | Worth of the evidence |
|---|---|---|---|
| `default` (two-pass) | One call per chunk with **50 class refs and titles, no definitions**. They are retrieved by embedding the chunk (`_CATALOG_RETRIEVAL_TOP_K = 50`, `services.py:146`; the catalog is `(class_ref, title)` pairs, `services.py:953`). The prompt says "choose the CLOSEST listed class rather than omitting it" (`prompts.py`). A second call derives relationships per chunk. | Replayed by me: dev found F1 0.411, typed F1 0.114; holdout typed F1 0.156. With Haiku/Sonnet/Opus 5.5: 0.09/0.18/0.15 (scratch, one take each). Old triple corpus: strict F1 0.94. | Solid that it is bad. The 0.94 on the old corpus measured short passages written for the test, not the task. |
| `find_then_type` | Find mentions per chunk, untyped, as "thing" or "statement" with a verbatim quote. Merge by label key across the source. Type each distinct mention **once**, from its first placed occurrence, against all classes with the **first 260 chars** of each definition in a cached system prompt, "none" allowed. Relate per chunk, between individuals typed in that chunk (the old pass-2 prompt, 8,000-token cap). Then recognition and proposal. JSON is parsed by regex; no structured-output constraint, no few-shot examples. | Replayed by me: dev found 0.534, typed 0.465, P 0.521, R 0.560 (core 0.814), type accuracy 0.874 (exact class 0.731), relationship recall 0.180; holdout found 0.513, typed 0.481, relationship recall 0.036. About $0.30 for 3 docs with Haiku 5.5. Scratch prototype logs confirm Opus 5.5: dev 0.552 / holdout 0.527 at $6.87. | One recording. Re-typing alone moves dev ±0.01 and holdout ±0.04. Item-sampling CI ±0.05/±0.07. The gain over `default` is real; the gap to Opus on holdout is within noise. |
| `open_v1` | spaCy subject–verb–object open extraction with optional retrieval typing. | Memory notes: below its floors; `grounded_v1` label accuracy 0.12. Not selectable on the Extract page. | Enough to retire it. |
| Recognition / dedup | Exact label, then a conservative vector match (0.90 plus margin and acronym guard) against existing individuals. | Episode corpus metrics (memory); not re-run by me. | Plausible. It is ordinary, solid work that every tool needs. |
| Decision models (Clef) | Port plus adapters; used in relationship reflection and claim triage. **Not in the individual-extraction path.** | Scratch: Clef 75% typing on gold mentions vs Haiku 80%; as a final chooser it lowered end-to-end typed F1 (Haiku 0.43 to 0.40, Opus 0.55 to 0.51). | Its extraction value is not shown. |

**Code volume.** Lines of Python:
- `domain/extraction/`: about 8.1k
- `domain/pipelines/`: about 16.7k, all pipeline types
- `tests/integration/pipelines/`: about 24.1k
- benchmark, tournament and loop scripts: about 3.6k, plus 864 lines of loop JS

Much of this is general and earns its keep: chunking, failure handling, proposals. But three
individual-extraction implementations, one of them dead, is two too many.

**The product default is the worst measured configuration.** On `main` the individual-extraction default
implementation is `default`. PR #1598 keeps that and moves its model to `claude-haiku-5-5` (contract
point 7). On the benchmark that combination scored dev typed F1 0.092. `find_then_type` is opt-in from the
Extract page only, and MCP `extract_source` still runs `default`.

### 1.2 The benchmark and its gold

What it is (verified in `tests/integration/fixtures/pipelines/extraction_benchmark/`):
- Three wiki-hosted documents:
  - `edit_check`: 5,685 words, 76 individuals, 53 relationships
  - `gitlab_architecture`: 6,228 words, 122 individuals, 83 relationships
  - `wikimedia_enterprise`: 3,246 words, 99 individuals, 56 relationships; the holdout
- In all, 297 individuals (143 core) and 192 relationships.

Weaknesses of the evidence itself:

1. **The gold is model-made, and it favours Claude.** The README section "How they were made" says the
   first extraction was by Claude Fable 5.2, followed by "an independent pass in which a second reviewer
   extracted blind" and an adjudication. The commits are co-authored by Claude Fable 5.2. I found no record
   of a human pass, yet the README and memory call it "hand-made".
   - The literature shows evaluators prefer their own family's outputs
     ([Panickssery et al., NeurIPS 2024](https://arxiv.org/abs/2404.13076)).
   - LLM-assisted gold inflates measured LLM performance
     ([Schroeder et al., ACL Findings 2025](https://arxiv.org/abs/2507.15821)).
   - Consequences: absolute numbers are suspect. Claude vs Clef comparisons favour Claude, as the
     decision-model memory note itself warns. A non-Claude baseline would be scored on Claude's span and
     granularity conventions.
2. **It is small and its structure limits what it can show.**
   - The three documents are the sampling unit, so document-level variance has 2 degrees of freedom.
   - Only **51 of 193 classes** appear in gold. The top 12 cover about 60% of items:
     `technology.systemsoftware` 28, `application.applicationcomponent` 19, `product.feature` 18, and so on.
   - Navigation and testing have zero coverage.
   - "Typing against ~200 classes" has been measured on ~50.
3. **Typing is lenient.** 174 of 297 gold items (59%) list `acceptable_classes`, 71 of them with an
   alternative in a different layer. "Type accuracy 0.87" means one of the allowed classes. Exact-class
   accuracy is 0.73.
4. **Dev and holdout are not meaningfully separate.**
   - The holdout is one document, with a different layer mix from dev (business and motivation 79%). It is
     a single out-of-distribution anecdote, not a held-out sample.
   - It has also been looked at: the 2026-11-14 typing experiments report holdout typed F1 for every take,
     and prompt choices followed.
   - Seven gold aliases were added after the first baseline run. That is defensible, but it is tuning on
     the test set.
5. **Relationship gold is the plainly stated subset.** Gold holds 192 relationships; GitLab's diagrams
   alone have about 100 more edges. Recall-only scoring is honest about that, but the result is that
   relationship *precision* has never been measured.

### 1.3 The scorer

`tests/integration/pipelines/_harness/benchmark.py`:
- A prediction finds a gold item by exact normalized name: lowercase, markdown and brackets stripped, last
  word singular. Statements can also match by passage overlap of at least 0.5.
- Typed correctly means every class given across names is accepted.
- Dev metrics are the mean of the two documents (macro).

What it gets right: it is order-independent, separates duplicates and known distractors from spurious items,
and penalizes hedged multi-class typing. That last rule is the right call, because a hedged item creates
duplicates in the graph.

What it gets wrong for a reviewer:
- **A name variant is counted twice.** "Add an image suggestion type" vs gold "Add an image suggestion",
  "Realtime firehose streaming" vs "Realtime streaming", and "LLC overseeing the project" vs "Wikimedia
  Enterprise LLC" each count as one spurious item *and* one miss. By my reading of the lists, about 17–18 of
  the 128 spurious items across the three documents are the same thing as a missed gold item (method in
  1.4).
- **Spurious does not mean wrong.** It means "not in a model-made gold". The spurious lists mix four kinds
  of item; my reading:
  - Items the gold's own conventions exclude but the pipeline was never told to: prior art in Edit check's
    background table, GitLab log files and directories. About 30, roughly a quarter.
  - Findings the document states, which rule 4 of the README makes individuals but the Edit check gold
    mostly omits: "Reference Check reduces revert rate" and about 16 like it.
  - Name variants: about 17.
  - Paraphrased motivation statements whose passages do not overlap gold's: the rest.
  - Precision is therefore probably understated. By how much is unknown until a human adjudicates.
- **"Typed F1" mixes three failures into one number:** finding, naming and typing. That is fine as a
  headline, but every decision so far has been made on it. A reviewer's cost depends on how many items they
  delete, fix and add, which the scorer could report directly from its lists.

### 1.4 The results, reproduced, and what they mean in user terms

Both replays reproduce the reported numbers exactly (`python scripts/benchmark_replay.py` and
`--implementation find_then_type`).

| `find_then_type`, Haiku 5.5 | edit_check | gitlab | wikimedia (holdout) |
|---|---|---|---|
| predicted / gold | 110 / 76 | 125 / 122 | 90 / 99 |
| matched / typed right | 39 / 35 | 74 / 63 | 48 / 45 |
| spurious / duplicates / known distractors | 62 / 6 / 3 | 31 / 14 / 6 | 35 / 2 / 5 |
| precision / recall (core) | 0.375 / 0.513 (0.738) | 0.667 / 0.607 (0.889) | 0.545 / 0.485 (0.658) |
| typed F1 | 0.389 | 0.541 | 0.481 |
| relationships: gold / predicted / correct | 53 / 28 / 5 | 83 / 54 / 22 | 56 / 28 / 2 |

My own re-scoring, from the recorded outputs, with no LLM calls:

- **Lenient matching.**
  - Method: I paired spurious items with missed gold items by content-word overlap, then judged the pairs by
    hand.
  - Result: about 17 pairs are the same thing. 7 of them were typed correctly.
  - Counting them: dev found F1 0.53 to ~0.60, typed F1 0.465 to ~0.49; holdout found 0.51 to ~0.58, typed
    0.48 to ~0.50.
  - Naming strictness costs about 0.06 found F1 but only about 0.02 typed F1, because most variants were
    also typed differently.
- **Relationships are under-generated, not mis-labelled.**
  - Predicted relationships per document are 28, 54 and 28, against 53, 83 and 56 in gold.
  - In 30 cases a predicted relationship connects a gold pair. In 29 of them it uses the gold predicate.
  - The relate stage sees only individuals typed in the same chunk, so cross-chunk links are impossible. It
    fails on its 8,000-token output cap about every other take on GitLab (memory, scratch).
  - The problem is the stage's design, not predicate choice.
- **Layer gaps.**
  - Found 0 of 9 APM metric instruments: every product measure in Edit check was extracted as a finding or
    missed.
  - Found 0 of 6 API individuals.
  - Business recall is 11%, 29% and 39% on the three documents; product recall 0–53%.
  - Motivation is the strongest layer: 63–76% found.
- **Confidence intervals.** Bootstrapping items within documents, from sampling alone: dev typed F1
  0.415–0.510, holdout 0.404–0.551. The holdout interval contains the whole dev interval, so the holdout
  cannot veto anything at Loop C's `HOLDOUT_SLACK` of 0.04.

**What a reviewer gets.** On GitLab, a proposal of 125 items:
- 63 are fully right; another 11 are found but mistyped.
- 14 are duplicates under another name.
- 31 match nothing in gold; about half are log files and directories gold excluded on purpose.
- 89% of core components are there.
- 22 of 83 stated relationships are there.

That is a useful first draft for an engineering document. On Edit check, a product document, 62 of 104
counted items are unmatched and all 9 named metrics are missed. Precision there is lower than recall,
so the reviewer deletes more than they keep, and still has to read the document for what is missing.

Positive pre-annotation results in the literature sit near recall 0.87 and precision 0.77
([Goel et al., ML4H 2023](https://arxiv.org/html/2312.02296): −58% time per document at equal final
quality). Reviewers shown suggestions add fewer items on their own initiative
([Levy et al., CHI 2021](https://arxiv.org/abs/2103.04725)), so low recall is the expensive failure.
**We have never measured reviewer time or acceptance**, the metric that would settle whether this is
useful.

### 1.5 The refinement loop and tooling

The pieces:
- the variant tournament (`scripts/quality_tournament.py`, 1,641 lines);
- the cassette replay;
- Loop C (`.claude/workflows/karpathy-loop.js`), with gates `EPSILON` 0.02 and `HOLDOUT_SLACK` 0.04;
- the ledger: 37 entries.

What the record shows:
- **Four accepts in total,** all against the old short-passage triple corpus:
  `two_pass_individual_then_relationship`, `llm_label_canonicalization`,
  `default_label_canonicalization`, `default_relationship_object_recall`.
- **Ten baseline resets**, as the corpus and incumbent moved under it.
- **Zero iterations against the benchmark.**
- **Cost is not tracked:** every ledger entry records `cost_usd: 0`, and agent tokens are excluded by
  design (`karpathy_loop_design.md` §5).

The loop's accept gates are below the measured noise. The only large improvement in the project's history
came from a human-designed probe, done in a scratchpad in a day for under $10.

The machinery is well built: cassette staleness detection and offline replay are genuinely good practice.
But its yield does not justify running it on a 3-document benchmark. PR #1597, which extends it to every
implementation, makes it more general before it has shown value.

### 1.6 Claims in the memory notes that overstate

| Claim | What the code and recordings say |
|---|---|
| "default LLM pipeline near-ceiling (strict ~0.92)" (`extraction-refinement-consolidated`) | True only on 6 dev and 2 holdout short passages written for the test. The same pipeline scores 0.11 on real documents. The note's claim that "every apparent pipeline ceiling has been a measurement artifact" was the wrong lesson: the ceiling was real and the corpus hid it. |
| Gold is "hand-made" (`extraction-benchmark`, benchmark README) | It is model-drafted and model-adjudicated (Claude Fable 5.2 plus model reviewers), with no documented human pass. |
| "Typing is measured-feasible" (`decision-model-extraction-design`) | Measured on gold mentions, against model-made gold, with lenient acceptable classes, on 51 classes. Feasible, yes. The 80–89% should not be quoted as accuracy on DR. |
| find_then_type "dev typed F1 0.11 to 0.47" (PR #1595 title) | Correct and reproduced. The framing implies a method gain where most of it is removing a defect: the missing definitions and the forced closest-class choice. |
| Noise "0.006–0.028" (`extraction-benchmark`) | That is run-to-run noise only, measured on the old pipeline. Item-sampling uncertainty is larger, ±0.05 to ±0.07, and the loop's gates ignore it. |

The rest of what I checked holds up: the prototype numbers match the logs in the scratch `clef_probe/`,
the cost figures are consistent, and the replays reproduce exactly. Those notes are careful about what was
measured.

---

## 2. How others do it

Research for this section was done on 2026-11-14 by three research passes plus my own spot checks.
I re-read [Text2KGBench-LettrIA](https://ceur-ws.org/Vol-4041/paper3.pdf) and the
[RAG vs GraphRAG](https://arxiv.org/abs/2502.11371) abstract myself. Versions are from PyPI and GitHub on
that date. Numbers are the authors' own unless marked.

### 2.1 Schema- and ontology-constrained extraction

- **LLM structured outputs.**
  - Anthropic ([docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)) supports
    JSON-schema output on current models with no published enum cap. Changing the schema invalidates the
    prompt cache.
  - OpenAI ([docs](https://developers.openai.com/api/docs/guides/structured-outputs)) allows up to 1,000
    enum values, with a 15,000-character cap on a single enum over 250 values.
  - Gemini has community reports of failures around 100–120 enum values.
  - Evidence on accuracy is mixed. Constraining buys validity, not typing accuracy. In
    [Xu & Bouyarmane, arXiv 2608.12574 (Aug 2026)](https://arxiv.org/abs/2608.12574), constrained decoding
    won 21 of 24 settings, mostly by removing invalid labels, but was neutral or worse for strong models at
    150 labels. The best recipe was to reason freely and then emit a constrained answer.
  - For us: our parser already rejects unknown classes, so the gain would be fewer failed calls, not better
    typing.
- **LlamaIndex `SchemaLLMPathExtractor`** (llama-index-core 0.14.26, MIT):
  [guide](https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/).
  Entity and relation labels become `Literal` enums; there are allowed-triple validation and a strict mode.
  **No type descriptions** for entities or relations, no entity resolution, and no published accuracy.
- **LangChain `LLMGraphTransformer`** (langchain-experimental 0.4.2, MIT):
  [source](https://github.com/langchain-ai/langchain-experimental/blob/main/libs/experimental/langchain_experimental/graph_transformers/llm.py).
  `allowed_nodes` and `allowed_relationships`, no descriptions, dedup within a chunk only. Measured
  independently: triple F1 0.45–0.57 on three CS abstracts, untyped
  ([Yamamoto et al., ISWC 2025 companion](https://ceur-ws.org/Vol-4085/paper49.pdf)).
- **neo4j-graphrag** (1.24.0, 2026-11-10, Apache-2.0):
  [KG builder guide](https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html).
  The only framework that takes a **description per node type**, plus relationship patterns and pruning of
  off-schema output. It has three resolvers (exact name, RapidFuzz, spaCy similarity), all marked
  experimental. No accuracy is published and there is no guidance on schema size. Structurally it is our
  old `default` shape: a schema in the prompt, per chunk.
- **Google LangExtract** (1.7.2, 2026-11-07, Apache-2.0, "not an officially supported Google product"):
  [repo](https://github.com/google/langextract).
  - The schema is defined by **few-shot examples**, not a class catalog. It provides char-offset source
    grounding and multiple extraction passes for recall.
  - No published benchmark. The Thoughtworks Radar rates it "Trial"
    ([Apr 2026](https://www.thoughtworks.com/radar/languages-and-frameworks/langextract)).
  - The closest off-the-shelf analogue to what we do, minus typing against definitions.
- **OntoGPT / SPIRES** (1.2.0, 2026-09-09, BSD-3):
  [repo](https://github.com/monarch-initiative/ontogpt); [paper, Bioinformatics 2024](https://doi.org/10.1093/bioinformatics/btae104).
  LinkML templates and recursive per-class prompting; IDs come from grounding names against ontologies
  (OAK), not from the LLM. Reported: GPT-4 relation F 43.8 (P 0.69, R 0.32) on BC5CDR; entity plus
  grounding F 70–74. It is built for biomedical ontologies with lexical grounding, not for definition-only
  architecture classes.
- **KGGen** ([arXiv 2502.09956](https://arxiv.org/abs/2502.09956), v2 Nov 2025; kg-gen 0.4.0, MIT).
  Open schema. Its MINE benchmark is LLM-judged fact retention, 66% vs GraphRAG 48%, which is not precision
  or recall. Its useful idea is dedup: retrieve similar items, then an LLM groups duplicates.
- **Small open models.** All numbers below are author-reported, on 3–20 coarse types.
  - GLiNER (0.2.30, Apache-2.0): about 61 F1 zero-shot on CrossNER/MIT; its docs cite degradation beyond
    about 30 labels.
  - GLiNER2 ([arXiv 2507.18546](https://arxiv.org/abs/2507.18546); 2.1.0): labels can carry descriptions;
    CrossNER 0.590 vs GPT-4o 0.599.
  - NuExtract3 ([HF](https://huggingface.co/numind/NuExtract3), 4B, Apache-2.0): 0.651 on the vendor's
    unreleased benchmark.
  - UniversalNER: one type per call, non-commercial licence, superseded.
  - None shows evidence for 193 definition-heavy classes. Our own GLiNER2 probe found 77% of
    non-motivation individuals at about 23% precision, with useless typing. That agrees.
- **Recent research directly on point.**
  - [Text2KGBench-LettrIA](https://ceur-ws.org/Vol-4041/paper3.pdf) (Plu et al., Lettria/EURECOM, ISWC 2025
    workshops; I verified this). It re-annotated 4,860 sentences over 19 small DBpedia-derived ontologies
    with four human experts.
    - Closed models, 1-shot, entity F1: 0.52–0.69. Examples: claude-sonnet-4 0.649, gpt-4.1-mini 0.687,
      gemini-2.5-pro 0.660.
    - LoRA-fine-tuned 4–32B open models: **0.83–0.88**. The training data is in-distribution, and the
      authors are a vendor using their own production prompt for the closed models.
  - [Wikontic, arXiv 2512.00590](https://arxiv.org/abs/2512.00590) (AAAI 2026) handles Wikidata's huge type
    set: retrieve the top 10 candidate types, then the LLM picks; relations are filtered by domain and
    range. It reports no gold precision or recall.
  - [DR-FET](https://aclanthology.org/2026.findings-acl.1584/) (ACL Findings 2026) and OntoType: the LLM
    writes a description of the mention, the description retrieves candidate types, and the LLM picks.

### 2.2 Open graph extraction for retrieval

- **Microsoft GraphRAG** (3.3.0, 2026-10-08, MIT): [repo](https://github.com/microsoft/graphrag),
  [dataflow](https://microsoft.github.io/graphrag/index/default_dataflow/).
  - `entity_types` defaults to organization, person, geo and event. Relationships are free text with a
    strength score, not typed predicates.
  - Auto prompt tuning can invent types.
  - Entities merge on **exact (title, type)**, and an LLM summarizes descriptions; "Postgres" and
    "PostgreSQL" stay apart.
  - Evaluated on QA and summarization win rates, never against a gold graph.
- **LazyGraphRAG.** Microsoft claims indexing at 0.1% of GraphRAG's cost
  ([blog, 2024-11-25](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/)),
  a vendor claim. It shipped in hosted Microsoft products. The research pass found no sign of it in the
  open-source repo.
- **LightRAG** (lightrag-hku 1.5.7, MIT), **nano-graphrag**, **fast-graphrag**: same pattern. A short type
  list, merge by name (from memory, not re-read in code), QA-based evaluation.
- **HippoRAG 2** ([arXiv 2502.14802](https://arxiv.org/abs/2502.14802), ICML 2025): open information
  extraction triples with no schema. It does no merging; it links phrases whose embedding similarity
  exceeds 0.8 with synonym edges.
- **Graphiti / Zep** (0.31.2, Apache-2.0): [repo](https://github.com/getzep/graphiti).
  - Entity and edge types can be Pydantic models.
  - It has the most developed resolver found: exact normalized name, then MinHash/LSH at Jaccard ≥ 0.9,
    then an LLM.
  - Evaluated on memory benchmarks only.
- **Independent checks of graph quality are poor.**
  - [Han et al., "RAG vs. GraphRAG"](https://arxiv.org/abs/2502.11371) (v4 2026-11-07): the research pass
    reports that only about 66% of answer entities existed in GraphRAG's graph on HotpotQA and NQ. I could
    not confirm the figure from the abstract; it is in the body.
  - [GraphRAG-Bench, arXiv 2506.05690](https://arxiv.org/abs/2506.05690) measures graph structure, not
    correctness against a gold graph.

**For our task:** none of these takes 193 defined classes or a predicate catalog in a way designed to be
followed, and none measures what we measure. Run as-is, they would most likely score well below our
`default` on typed F1. That is an inference, untested.

### 2.3 Typing against large label sets

- **Retrieve-then-rank beats embed-and-take-nearest.**
  - [IReRa, arXiv 2401.12178](https://ar5iv.labs.arxiv.org/html/2401.12178), about 14k labels, RP@10 on
    HOUSE: nearest-label retrieval 36.8; with an LLM query rewrite first, 52.6; with an LLM rerank on top,
    65.8.
  - In entity linking, [LELA, arXiv 2601.05192](https://arxiv.org/html/2601.05192) falls from 83.1 to 27.2
    without its LLM selection step.
  - This is the same finding as ours: embedding shortlists were the root problem. At 193 classes the full
    catalog fits in context, so skipping retrieval, as `find_then_type` does, is defensible. At thousands of
    classes it would not be.
- **Accuracy at this scale.** With 77–150 short labels, an LLM with retrieved examples reaches 89–98%
  accuracy ([Milios et al., arXiv 2309.10954](https://arxiv.org/html/2309.10954)). Our 80–89% on gold
  mentions, with closely related classes, is plausible, not remarkable.
- **Hierarchy.** On 309 leaves in 3 levels, gpt-4o-mini leaf accuracy, zero-shot / best few-shot
  ([Yoshimura & Kashima, arXiv 2508.04219](https://arxiv.org/html/2508.04219v1)):
  - whole hierarchy in one prompt: 0.491 / 0.532
  - top-down, step by step: 0.436 / 0.490
  - flat list: 0.257 / 0.392

  Few-shot examples helped consistently. This matches our probe, where layer-then-class was worse for Clef
  (65% vs 75%). Present the catalog **grouped by layer** in one prompt; do not gate by layer.
- **Gold quality in entity linking.** In a sample of ChatEL errors, 44% were gold errors
  ([arXiv 2402.14858](https://arxiv.org/html/2402.14858v1)). Our gold is model-made, so expect the same.

### 2.4 Relationships and entity resolution

- **Document-level relation extraction (RE) is hard for zero-shot LLMs.**
  - On DocRED / Re-DocRED with gold entities: GPT-4 zero-shot F1 15.6 / 14.2; supervised SOTA 67.5 / 80.7;
    a pair-filter classifier plus a fine-tuned LLM about 61 / 75
    ([LMRC, arXiv 2408.13889](https://arxiv.org/html/2408.13889v2)).
  - 97% of candidate pairs hold no relation, which is why precision collapses.
  - With entities predicted end to end: about 18–23 F1, e.g. BioRED with o1 23.2
    ([arXiv 2504.04083](https://arxiv.org/html/2504.04083v3)).
  - Our relationship recall of 0.18 (dev) is typical. The 0.04 holdout is below typical, though with 56
    gold triples its interval is about 0.01–0.12.
- **Incomplete gold.** [Re-DocRED](https://ar5iv.labs.arxiv.org/html/2205.12696) estimates 64.6% of true
  triples were missing from DocRED. Our relationship gold is explicitly the plainly stated subset, so any
  precision we compute later would be biased down.
- **Entity resolution.** Production tools mostly merge on exact names. The better ones add fuzzy or
  embedding candidates and then an LLM decision (Graphiti, KGGen, Wikontic, neo4j-graphrag resolvers). Our
  recognition step (exact, then conservative vector with margin and acronym guard) is in line with that, and
  it is tested. No one publishes resolver accuracy on LLM-extracted nodes.

### 2.5 Evaluation practice

- Ontology-constrained benchmarks are sentence-level, have small ontologies and use human gold:
  [Text2KGBench (2023)](https://ar5iv.labs.arxiv.org/html/2308.02357) and LettrIA (2025). The research
  passes found no document-level benchmark with 100+ classes and typed graphs. Our task has no public
  yardstick, so our own benchmark is necessary. That is a point in its favour; it just needs to be bigger
  and human-checked.
- **Sample size.** Clustered standard errors can be about 3× naive ones, and roughly 1,000 independent
  items are needed to detect a 3-point difference
  ([Miller, arXiv 2411.00640](https://arxiv.org/html/2411.00640v1)). The document is our sampling unit; we
  have 3.
- **Human-in-the-loop value is measured as time and edits, not F1.** Goel et al. (above) report −58% time
  per document at R 0.87 / P 0.77. Adding and modifying items cost significant time; deleting did not. So
  favour recall. Suggestions anchor reviewers
  ([Wang et al., CHI 2024](https://megagon.ai/publications/human-llm-collaborative-annotation-through-effective-verification-of-llm-labels/);
  Schroeder et al.). The research found no positive time-saving result at recall near 0.5. Prodigy's "10×"
  is a single vendor case study.

---

## 3. Honest comparison

### What an off-the-shelf approach would most likely deliver here

| Approach | Likely result on our benchmark | Cost to adopt | Basis |
|---|---|---|---|
| GraphRAG / LightRAG / nano-graphrag / HippoRAG | Typed F1 well below 0.3: a few types, exact-name merging, free-text relations | Low to try; high to bend to DR | Design, plus no extraction-quality evaluation exists (inference) |
| LangChain / LlamaIndex schema extractors | Close to our old `default`: enums without definitions, per chunk, so likely 0.1–0.3 typed F1 | Low | Same shape as `default`, which we measured (inference) |
| neo4j-graphrag with 193 described node types | Better than the above, probably below `find_then_type`: per-chunk typing, truncation pressure from 193 descriptions per chunk prompt | Medium; needs a Neo4j instance for the full pipeline | Design (inference) |
| LangExtract with few-shot examples | Good grounding and recall; typing depends on how the catalog is expressed (examples, not definitions) | Low | No published accuracy; worth one arm |
| **A direct strong-model call: full catalog with full definitions, structured output, whole document** | **Unknown, and the most likely to match or beat us.** Opus typed 89% of gold mentions, and the documents fit easily in one context. | **~150 lines, about $1 per document with Opus 5.5** | Our own probes; LettrIA's frontier numbers |
| Fine-tuned small model | LettrIA's +15–20 entity F1 is the one large published gain | Needs thousands of labelled examples we do not have | LettrIA |

There is no product to adopt that is built for "instances of 200 defined classes from long documents,
reviewed by a human". **The realistic alternative to our pipeline is not a framework; it is a
simpler call to a frontier model.**

### What of ours is genuinely different, and what is reinvented

Genuinely ours, and worth keeping:
- **Ontology tooling:** DR import, classes with curated definitions, predicate catalog with domain and
  range, schema bundles.
- **Proposals and the review queue,** with passages as provenance.
- **Recognition against the existing graph,** so a re-extraction does not duplicate.
- **The benchmark itself:** no public benchmark fits this task.
- **Cassette replay and failure handling:** a failed call is never read as "found nothing", and partial
  proposals are explicit. These are better engineered than any framework reviewed.

Reinvented, and fine:
- Chunking, merge-by-label, and the find-then-type decomposition. It is the field's standard
  retrieve-or-catalog-then-select shape.
- Recognition thresholds.

Built without the evidence to justify it:
- three individual-extraction implementations;
- the Clef decision-model path for extraction;
- Loop C, the tournament, and its accept gates set below measurement noise;
- `open_v1` with its spaCy dependency and pinning troubles.

### Is 0.47 good? Was 0.11 broken?

- **0.11 was broken by construction.**
  - The class the gold needs was not in the shortlist for about half the items.
  - Classes had no definitions.
  - The prompt forced a closest choice.
  - Each chunk typed independently, giving one individual several classes.
  - A stronger model cannot overcome a missing option, which is exactly what Sonnet and Opus showed. That
    result says nothing about model strength. It says the shape capped quality.
- **0.47 is "competent zero-shot".**
  - LettrIA frontier models one-shot reach 0.52–0.69 entity F1 on a far easier task: sentence-level, small
    ontologies, typing scored only where the entity is right. Our 0.47 strict, about 0.49 lenient, on long
    documents and 193 classes is in that neighbourhood.
  - It is not evidence of an advantage over a direct strong-model call, which has not been tried.
  - Nor is it good enough to save reviewer time on product-style documents, though it may on architecture
    documents (GitLab: 0.54, 89% core recall).

### What others treat as basic and we lack

1. **A single-pass strong-model baseline with structured output.** Never run.
2. **Few-shot examples.** LangExtract's whole design and the hierarchy study both show examples help. Our
   prompts have none. Gold conventions such as prior art out, log files out, and product measures as
   `apm.metricinstrument` are taught nowhere, and roughly a quarter of "spurious" items are those
   conventions.
3. **Catalog grouped by layer in one prompt.** Ours is sorted by reference, which groups by layer only
   implicitly through the prefix.
4. **Multiple takes / self-consistency.**
   - Re-typing changes 16.5% of answers, and the variance is measured but unused.
   - Agreement between two takes or two models was measured: 63–70% of mentions at 90–93% accuracy.
   - That is a free confidence signal for ordering the review queue. It is not used.
5. **A human-acceptance metric:** accept, edit and reject counts plus minutes per document. Never collected.
6. **Human-confirmed gold,** at least for the holdout.
7. **Relationship precision,** even on a sample.

---

## 4. Recommendations

Confidence: **H** high, **M** medium, **L** low.

### 4.1 Pipelines

1. **Make `find_then_type` the default individual-extraction implementation, including MCP
   `extract_source`. (H)**
   - Evidence: dev 0.465 vs 0.092 for the configuration #1598 makes default; holdout 0.481 vs 0.156.
   - Cost per run is similar: about $0.10 per document with Haiku 5.5.
   - Would prove it wrong: a reviewer finding its proposals worse in use than the two-pass ones. Unlikely
     given recall.
2. **Rebuild relationships as one document-level stage. (M)**
   - Shape:
     - Input: all typed individuals of the source, each with its passages.
     - Prompt: the predicate catalog filtered by the domain and range of each pair of classes.
     - Calls: batched by source individual, so no single answer hits an output cap.
   - Evidence: relationships are under-generated (28–54 proposed vs 53–83 stated), the predicate is right
     29 of 30 times when the pair is found, and per-chunk scoping makes cross-chunk links impossible.
   - Would prove it wrong: relationship recall not rising by more than 0.10 on dev in 3 takes.
3. **Teach conventions with examples, not rules. (M)**
   - Add 3–6 short worked examples to the find and type prompts, drawn from a document **outside** the
     benchmark: prior art and link lists are not elements; logs and paths are not elements; a named measure
     is `apm.metricinstrument`; a stated finding is `motivation.assessment`.
   - Type a mention from all its occurrences, not the first (an untried lever noted in memory).
   - Evidence: the composition of the spurious lists, and the 0 of 9 metrics.
   - Would prove it wrong: precision not rising on held-out documents.
4. **Do not pursue:** whole definitions (tried, no gain); layer gating (literature and our probe say worse);
   Clef as typer (lowered F1); embedding shortlists at 193 classes (they cover the right class 49–63% of the
   time).
   - Revisit description-based retrieval (DR-FET style) only if a taxonomy grows past what one cached prompt
     holds.
5. **After the head-to-head (4.2), delete the losing extraction core.**
   - Delete `open_v1` regardless. (H)
   - If the single-call baseline wins, `find_then_type` becomes a thin adapter around it, keeping chunk
     handling only for documents beyond one context.

### 4.2 Experiments

**E0. Fix the measurement first. About 1 day of human time, $0.** (H)
- A human (Austin) adjudicates:
  - the holdout gold: confirm, retype or remove each item, and add misses;
  - all 128 "spurious" `find_then_type` items: accept or reject.
- Record a lenient alias table from the adjudication.
- Report strict and adjudicated scores side by side from then on.
- This alone tells us the true precision, and how much the model-made gold flatters or punishes Claude.

**E1. Head-to-head on the benchmark. About $15–25, 1–2 days.** (H that it should be run; no prior on the
winner)

| Arm | What | Est. cost (3 docs × 3 takes) |
|---|---|---|
| A | `find_then_type`, Haiku 5.5, as merged (2 new takes plus the recorded one) | ~$0.60 |
| B | Single call per document to `claude-opus-5-5`, details below | ~$9 |
| B′ | Arm B with `claude-sonnet-5-5` | ~$5 |
| C | LangExtract 1.7.2 with 6–10 few-shot examples from a non-benchmark document; class refs plus one-line glosses in the prompt description; model per what LangExtract supports (verify Claude support before choosing) | ~$2–5 |

Arm B in detail:
- Input: the whole `source.md` (3–6k words), plus the full DR catalog **with full definitions**, grouped by
  layer, as a cached system block of about 64k tokens.
- Output: structured output listing individuals (`name`, `class` enum or `none`, `kind`, verbatim `quote`)
  and relationships (`source`, `predicate` enum, `target`, `quote`).
- Settings: adaptive thinking at effort `high`, no few-shot.
- Cost basis: about 75k input tokens per document (catalog cached after the first), about 30k output tokens
  at $4/$20 per million tokens.

Harness, about 200 lines in `scripts/benchmark_external.py`:
- Each arm writes `{individuals:[{title, class, quote}], relationships:[{source, predicate, target}]}` per
  document, saved as fixtures so it replays free.
- An adapter builds `Predicted` and `PredictedRelationship` objects and calls `benchmark.score()`
  unchanged.
- Report per document, per take, **paired** deltas (A vs B on the same document), strict and adjudicated.

Decision rule, on adjudicated typed F1 averaged over 3 takes and all three documents, plus relationship
recall:
- **B within ±0.05 of A:** adopt B's simplicity. One call, no merge, far less code. Keep A's failure
  handling and recognition around it.
- **B ahead by more than 0.08:** replace the core with B. Our decomposition is not earning its keep.
- **A ahead by more than 0.08:** the decomposition earns its keep. Continue on A and stop asking.
- **C ahead of both:** adopt LangExtract's few-shot and grounding approach. It is unlikely to type well
  against definitions.

**E2. Grow the benchmark. 7–10 more documents, human-confirmed gold, a few hours each.** (H)
- Draw from the documents DR clients actually model, including at least two engineering and two product
  documents, and one with API, data-model and APM content.
- Draft gold with a non-Claude model to break the family link, then human-adjudicate.
- Use documents as the unit; keep 3–4 as a real holdout nobody prompts against.
- Until this exists, treat any difference under 0.08 as noise.

**E3. Reviewer acceptance study. About 2 hours per document.** (M)
- For 3 documents, time Austin modelling one from scratch in the app versus reviewing an arm-A or arm-B
  proposal.
- Log accept, edit, reject and added counts per operation.
- This is the metric that should decide the direction. F1 is a proxy for it.

**E4. Confidence from agreement. About $1.** (M)
- Type each mention twice (two takes, or Haiku plus Sonnet); flag disagreements in the review queue.
- The probes measured agreement covering 63–70% of mentions at 90–93% accuracy. Check whether reviewing
  disagreements first cuts review time.

### 4.3 Direction

**Narrow, don't replace. (M)**
- Extraction is a commodity step done by a frontier model. Context Studio's value is everything around it:
  - the ontology and its definitions;
  - proposals and review;
  - recognition and dedup against an existing graph;
  - provenance;
  - client round-trips with DR and House;
  - an honest benchmark for a task with no public one.
- Shrink extraction to one pipeline. Choose it by E1, and judge it by E3.
- Would change this:
  - **Arm B clearly wins:** extraction becomes a single call and the pipeline framework for individual
    extraction can be cut back.
  - **E3 shows review takes as long as modelling from scratch even with the best arm:** pause extraction
    work and make review efficient (bulk accept by layer, disagreement-first ordering) before any more
    pipeline work.
  - **E2 gold supports it:** fine-tuning becomes worth costing. It is the only lever with a large published
    gain, and it needs far more labelled data than exists. The review queue is how that data would
    accumulate: every accepted or edited proposal is a training example.

### 4.4 What we should stop doing

1. **Stop running and extending Loop C** (including #1597's generalization) until there are at least 10
   documents with human-confirmed gold. Its accepts optimized a corpus that turned out unrepresentative; its
   gates sit below noise; its cost is not tracked.
2. **Stop drawing conclusions from single recordings and from deltas under about 0.08.** Record 3 takes per
   arm; report intervals.
3. **Stop scoring prompt experiments on the holdout.** Treat `wikimedia_enterprise` as contaminated and
   replace it in E2.
4. **Stop calling the gold "hand-made".** Say "model-drafted, model-adjudicated" until a human has gone
   through it.
5. **Stop shipping the two-pass `default` as the product default** (see 4.1.1), and stop maintaining
   `open_v1`.
6. **Stop investing in the decision-model (Clef) path for extraction typing.** It lowered end-to-end F1 as
   a chooser, and its gating value is unmeasured against cost. Keep it where it serves triage and
   reflection.
7. **Stop building selection and tournament infrastructure for more implementations.** The goal is fewer
   implementations.
8. **Stop explaining poor scores as measurement artifacts case by case.** Do the one systematic
   adjudication (E0) and live with what it says.

---

## 5. What I could not verify

- **Scratch probe figures.** The typing-accuracy probes (Clef 75%, Haiku 80%, Opus 89%), re-typing noise
  (16.5%), the GLiNER2 numbers and the whole-definition experiment come from memory notes and scratch files
  of other sessions. I checked only the end-to-end prototype logs (`clef_probe/e2e_*.log`), which match.
- **My lenient re-scoring and spurious categories.** They are my own reading of the lists, not an
  adjudication; the counts are approximate.
- **Third-party figures.**
  - The figure of about 66% answer-entity coverage in GraphRAG graphs is from the research pass; I saw only
    the abstract.
  - LightRAG and nano-graphrag merge behaviour is from documentation and memory, not code.
  - The structured-output enum-limit study (arXiv 2608.12574) and DR-FET numbers were not read by me.
- **What off-the-shelf tools would score.** Their likely results on our benchmark (section 3 table) are
  inferences from design. None was run, as the brief allowed no paid calls.
- **Cost estimates.** Arm costs use Anthropic list prices as cached in the claude-api reference
  (2026-11-03): Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50 per million tokens. Token counts
  are estimates.

---

## Sources

Code and data (this repository, `origin/main` `4cfc996d`):
- `local-server/domain/extraction/find_then_type.py`, `prompts.py`, `services.py`
- `local-server/domain/pipelines/individual_extraction/`
- `local-server/tests/integration/pipelines/_harness/benchmark.py`
- `local-server/tests/integration/fixtures/pipelines/extraction_benchmark/`
- `local-server/scripts/benchmark_replay.py`
- `local-server/experiments/ledger.jsonl`
- `.claude/workflows/karpathy-loop.js`
- `documentation/karpathy_loop_design.md`
- PRs #1595–#1600

Literature and tools (publication or release date; accessed 2026-11-14):
- Plu et al., Text2KGBench-LettrIA, ISWC 2025 workshops (2025-11) — https://ceur-ws.org/Vol-4041/paper3.pdf
- Yamamoto et al., LLM KG extraction from abstracts, ISWC 2025 companion — https://ceur-ws.org/Vol-4085/paper49.pdf
- Mihindukulasooriya et al., Text2KGBench (2023-08) — https://ar5iv.labs.arxiv.org/html/2308.02357
- Caufield et al., SPIRES/OntoGPT, Bioinformatics (2024) — https://doi.org/10.1093/bioinformatics/btae104 ; https://github.com/monarch-initiative/ontogpt (1.2.0, 2026-09-09)
- Google LangExtract (1.7.2, 2026-11-07) — https://github.com/google/langextract ; Thoughtworks Radar (2026-04) — https://www.thoughtworks.com/radar/languages-and-frameworks/langextract
- neo4j-graphrag (1.24.0, 2026-11-10) — https://neo4j.com/docs/neo4j-graphrag-python/current/user_guide_kg_builder.html
- LlamaIndex property graph guide (llama-index-core 0.14.26, 2026-11-13) — https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/
- LangChain LLMGraphTransformer (langchain-experimental 0.4.2, 2026-05-22) — https://github.com/langchain-ai/langchain-experimental
- KGGen (v2 2025-11) — https://arxiv.org/abs/2502.09956
- GLiNER (NAACL 2024) — https://arxiv.org/abs/2311.08526 ; GLiNER2 (2025) — https://arxiv.org/abs/2507.18546 ; NuExtract3 (2026) — https://huggingface.co/numind/NuExtract3
- Anthropic structured outputs — https://platform.claude.com/docs/en/build-with-claude/structured-outputs ; OpenAI structured outputs — https://developers.openai.com/api/docs/guides/structured-outputs
- Xu & Bouyarmane, constrained decoding over large label sets (2026-08) — https://arxiv.org/abs/2608.12574
- Wikontic (v2 2026-01) — https://arxiv.org/abs/2512.00590 ; DR-FET, ACL Findings 2026 — https://aclanthology.org/2026.findings-acl.1584/
- Microsoft GraphRAG (3.3.0, 2026-10-08) — https://github.com/microsoft/graphrag ; LazyGraphRAG blog (2024-11-25) — https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
- LightRAG — https://github.com/HKUDS/LightRAG ; HippoRAG 2 (2025-02) — https://arxiv.org/abs/2502.14802 ; Graphiti — https://github.com/getzep/graphiti ; Zep paper (2025-01) — https://arxiv.org/abs/2501.13956
- Han et al., RAG vs. GraphRAG (v4 2026-11-07) — https://arxiv.org/abs/2502.11371 ; GraphRAG-Bench (2025-06) — https://arxiv.org/abs/2506.05690
- IReRa (2024-01) — https://ar5iv.labs.arxiv.org/html/2401.12178 ; Milios et al. (2023-12) — https://arxiv.org/html/2309.10954 ; LELA (2026) — https://arxiv.org/html/2601.05192 ; ChatEL (2024-02) — https://arxiv.org/html/2402.14858v1
- Yoshimura & Kashima, hierarchical classification with LLMs (2025-08) — https://arxiv.org/html/2508.04219v1
- CASENT / UFET (2023-11) — https://arxiv.org/html/2311.00835
- LMRC, DocRED/Re-DocRED LLM results (2024-12) — https://arxiv.org/html/2408.13889v2 ; Re-DocRED (EMNLP 2022) — https://ar5iv.labs.arxiv.org/html/2205.12696 ; zero-shot biomedical RE (v3 2026-01) — https://arxiv.org/html/2504.04083v3
- Goel et al., LLM pre-annotation for medical IE (2023-12) — https://arxiv.org/html/2312.02296
- Levy et al., CHI 2021 — https://arxiv.org/abs/2103.04725 ; Wang et al., CHI 2024 — https://megagon.ai/publications/human-llm-collaborative-annotation-through-effective-verification-of-llm-labels/ ; Schroeder et al., ACL Findings 2025 — https://arxiv.org/abs/2507.15821
- Panickssery et al., self-preference, NeurIPS 2024 — https://arxiv.org/abs/2404.13076
- Miller, error bars for evals (2024-11) — https://arxiv.org/html/2411.00640v1 ; Card et al., EMNLP 2020 — https://aclanthology.org/2020.emnlp-main.745
