# Individual Extraction — Design Analysis & Karpathy-Loop Proposal

**Date:** 2026-07-05
**Scope:** Compare the current individual-extraction pipelines (`default` LLM and `open_v1` spaCy) in `local-server/` against the legacy POC under `legacy/legacy-server/`, and design an automated experimentation loop to reach "good enough for a POC" quality.

---

## 1. Headline findings

1. **The legacy POC never implemented its own stated design goal.** The goal — extract *all* nouns, verbs, and adjectives and match them to the ontology for reliable individual + relationship extraction — exists in legacy only as (a) a read-only full-token NLP analysis endpoint (`nlp/processors.py:22`, keeps every token with lemma/dep/WordNet/ConceptNet) that feeds nothing downstream, and (b) an unwired clean-architecture stub (`legacy-server/domain/extraction/` — its `relationships` field is never populated). The *running* legacy RAG pipeline extracts only **noun chunks + named entities**; verbs are captured only as unused context hints (`web_search.py:244` — "not currently used") and **relationship extraction between individuals does not exist in legacy at all**.

2. **The new `open_v1` pipeline is the first code in the project's history that actually derives relationships from verbs** (dependency-based SVO triples, `domain/extraction/open_extraction.py:437`). But its coverage is *narrower* than the design goal in a different way: it emits triples only for verbs that have an `nsubj`/`nsubjpass`, with objects reachable as `dobj`/`attr`/`dative`/`pobj`-via-`prep`. Standalone nouns, adjectives, copular sentences ("X is a Y"), clausal complements, appositives, and subject-less verbs produce nothing. Legacy covered nouns without relationships; open_v1 covers relationships without noun coverage. **Neither system covers what the design goal asks for — the two halves have never been combined.**

3. **The current `default` (LLM-only) individual pipeline is weaker than it looks.** It makes one LLM call whose prompt includes only the **ontology title** — not the class/property inventory (`domain/extraction/services.py:516`) — and trusts LLM-returned entity/property IDs verbatim with no existence check (`services.py:558-625`). The last recorded live run scored **0.0 precision/recall/F1 on all 10 scenarios**, which suggests a broken contract, not just poor quality. Legacy did this part *better*: it injected the top-20 vector-matched KG nodes into the LLM prompt (RAG proper), and verified matches by title.

4. **The existing closed loop can't climb because the metric has no gradient and the knobs aren't the levers.** Rule-mode individual F1 is 0.066 and the loop found zero improvement — expected, because (a) the eval is exact `(subject, predicate, object)` string-tuple match with no partial credit, so nearly every plausibly-correct extraction scores 0 and small knob changes move nothing; and (b) the swept space is just `predicate_form × relation_confidence` (2×3 grid, `scripts/quality_loop.py:89-92`) while the actual failures are algorithmic: coverage gaps, phrase-boundary/label-normalization mismatches, and no canonicalization step.

---

## 2. The three designs at a glance

| Dimension | Legacy RAG pipeline (POC) | Current `default` (LLM) | Current `open_v1` (spaCy) |
|---|---|---|---|
| Candidate extraction | Noun chunks + NER per sentence (L0), gap noun-chunks (L2) | None — LLM free-forms from raw text | SVO skeletons of subject-bearing verbs only |
| Verb usage | Context hint only (unused) | Implicit in LLM | **Predicate source** (verb lemma/surface) |
| Adjective usage | Inside noun chunks; "contextual" gap tier | Implicit in LLM | Inside chunk lemmas only |
| Ontology matching | sqlite-vec cosine (title+definition max), thr 0.6, top-k 50, layered fallback + phrase-reuse (0.85) + web search | LLM asserts IDs; **no verification** | Brute-force numpy cosine behind `SchemaVectorIndex`, top-k 1, thr 0.45 — **off by default** |
| Ontology context to LLM | Top-20 matched KG nodes formatted into prompt | **Ontology title only** | No LLM call at all (knobs exist, unwired) |
| Relationships | **None** (placeholder field) | LLM asserts triples | Dependency SVO triples |
| Individual vs class | Not distinguished | LLM asserts `kind` | Everything is `individual`; optional `rdf:type` grounding |
| Coverage enforcement | Implicit: L2 finds noun-chunks the LLM/KG missed | None | None — non-SVO text silently dropped |
| Confidence | Per-source calibrated bands (LLM 0.9–1.0, cached-KG 0.7–0.8, full-KG 0.6–0.75, web 0.5–0.6) | LLM-asserted, clamped | Single constant (`relation_confidence`) |
| Experiment harness | `rag_experiments` API: annotated paragraphs, **parallel named pipeline variants**, span-overlap F1 (0.8 overlap = match) | — | quality harness: 10 fixtures, **exact-tuple** F1, coordinate ascent over 2 knobs |

## 3. What's worth salvaging from legacy

- **Layered gap-filling as a coverage mechanism.** Legacy's L2 "find noun-chunks nobody accounted for, prioritized by dependency role (CRITICAL={nsubj,nsubjpass}, IMPORTANT={dobj,pobj,attr,dative}, CONTEXTUAL={conj,appos,compound,amod})" is the closest legacy got to the coverage goal, and it maps directly onto open_v1's existing `_CRITICAL_DEPS` tiers. The idea to port: *after* SVO extraction, enumerate every noun chunk not consumed by a triple and emit it as a candidate individual (grounded by vector search) — that's the "cover the rest of the sentence" half that open_v1 is missing. Note `build_concept_candidates` (NOUN/PROPN/ADJ + TF-IDF) already exists in the new codebase but is only wired to *schema* extraction.
- **RAG-proper prompting.** Inject the top-k vector-matched ontology nodes into the LLM prompt (legacy `llm_extraction.py:132-163`) instead of just the ontology title. This is the single most obvious fix to the `default` pipeline.
- **Span-overlap scoring with partial credit.** Legacy's scoring counted a hit at ≥0.8 span overlap (`rag/test_scoring.py`). The new harness's exact-tuple match is the strictest possible metric and is starving the optimizer of signal.
- **Per-source confidence bands** instead of one constant — needed for a meaningful Brier score and for apply-time thresholding.
- **The pipeline-variant registry pattern** (`rag/pipeline_registry.py` + parallel comparison API): run N named variants against the same annotated corpus and rank by F1. The new loop tunes one config; the legacy harness compared *algorithms*. The Karpathy loop needs the latter.

## 4. Why F1 is 0.066 — failure decomposition

The observed failures stack multiplicatively; a triple must survive all four stages:

1. **Relation not derived (coverage).** GT triples like `replication --improves--> availability` only surface if the sentence's verb has an explicit nsubj and the object is in {dobj, attr, dative, pobj}. Copular ("Replication is a technique that improves…"), nominalized ("the improvement of availability through replication"), passive-with-agent, and clausal constructions all miss.
2. **Phrase-boundary mismatch.** GT labels are hand-chosen chunk reductions (`state_agreement`); the pipeline emits `snake_label` of chunk content-lemmas, which may add or drop modifiers (`agreement`, `distributed_state_agreement`).
3. **Predicate form mismatch.** GT predicates are 3rd-person surface forms (`ensures`, `improves`); the pipeline's `lemma` mode emits `ensure`. The `surface` mode fixes this specific case but breaks others — exactly the kind of thing a loop should discover, except the metric scores both ~0 so it can't.
4. **Exact-tuple metric.** All of the above become total misses instead of partial credit. The spike script's fuzzy-stem recall estimator suggests lexical coverage is far higher than 0.07 — the metric is measuring string-canonicalization agreement, not extraction quality.

Separately: **the live LLM path scoring 0.0 across all scenarios** (telemetry `individual_extraction.jsonl`, 2026-06-14) should be treated as a bug to diagnose first — likely an output-contract mismatch between the prompt's JSON schema and `extract_triple_key`. There is no point looping until the strongest mode is even on the board.

## 5. The Karpathy loop — design

Goal: an automated look-at-errors → change → re-evaluate → keep-if-better loop that can perform brute-force refinement without a human in each iteration, and that measures progress on a metric that actually moves.

### 5.1 Principle: separate the *training signal* from the *acceptance gate*

Keep the strict exact-tuple F1 as the **floor gate** (it is the POC bar), but add a **soft F1** as the hill-climbing signal, plus **per-stage diagnostics** so the loop (and any agent driving it) knows *which* stage failed for each missed GT triple:

- `soft F1`: tiered triple match — exact tuple = 1.0; lemma/stem-normalized label match = 0.9; embedding-cosine label match ≥ 0.85 on subject & object with lemma-matched predicate = 0.7. Report strict and soft side by side.
- `candidate_recall`: fraction of GT subjects/objects that appear as *any* extracted candidate (before matching). Isolates coverage failures.
- `predicate_recall`: fraction of GT (subject, object) pairs for which *some* relation was derived, regardless of predicate label. Isolates relation-derivation failures.
- `label_accuracy`: given the pair was derived, did the labels match (strict / soft)? Isolates normalization failures.

These are cheap to compute in the existing harness (`tests/integration/pipelines/_harness/metrics.py`) and turn one opaque 0.066 into a diagnosable vector.

### 5.2 Loop architecture — three nested loops, increasing cost

**Loop A — knob sweep (exists, needs widening).** Deterministic, offline, seconds-per-eval. Keep `scripts/quality_loop.py` coordinate ascent but:
- optimize soft-F1, gate on strict-F1 never regressing;
- widen `_INDIVIDUAL_SPACE` to every knob that exists once the coverage work lands (dependency-role sets as categorical knobs, chunk-boundary strategy, `similarity_threshold`, `ground_to_schema`, `require_schema_match`, `top_k`, noun-fallback on/off, copular-handling on/off);
- add 2–3 random restarts or shuffled knob order per pass — greedy single-start ascent demonstrably plateaus at baseline today.

**Loop B — variant tournament (port the legacy idea).** Register named algorithm variants (e.g. `open_v1`, `open_v1+gap_fill`, `open_v1+copular`, `default+rag_prompt`, `hybrid`) and run them all against the corpus in one command, ranked by strict and soft F1 per scenario. This is legacy's `rag_experiments` pattern rebuilt on the new harness — the unit of experimentation becomes *an algorithm change*, not a knob value. Output: a scoreboard table in the existing JSONL telemetry.

**Loop C — agent-in-the-loop refinement (the actual Karpathy loop).** A script (`scripts/karpathy_loop.py` or an orchestrating skill) that iterates:
1. Run Loop B → produce a structured **error report**: every missed GT triple classified by failure stage (from §5.1 diagnostics) + the 5 worst scenarios + example sentences.
2. Hand the report to an agent session with a bounded instruction: propose ONE change (code, prompt, or knob-space edit) targeting the largest failure class, apply it on a branch.
3. Re-run Loop A on the changed variant (knobs re-tuned per variant — a code change shifts knob optima).
4. Accept iff soft-F1 improves and strict-F1 ≥ previous best; commit with the telemetry row; else revert and record the negative result so it isn't retried.
5. Stop at the floors (strict P≥0.60/R≥0.50/F1≥0.50) or at an iteration/cost cap.

LLM cost control: run rule-mode iterations free; when a change touches the LLM path, record cassettes once per accepted prompt change (~$0.03/config on gemini-flash per prior measurement) and replay thereafter. The cassette infra (`_harness/cassettes.py`) already supports exactly this.

### 5.3 Dataset hygiene

10 hand-labeled scenarios in one domain is both the eval and the tuning set — the loop will overfit. Cheap fixes, in order:
1. Split: 7 dev / 3 holdout; the loop optimizes on dev, reports holdout, accepts only if holdout doesn't crater.
2. Promote the 8 unused arxiv `fixture_*.json` files into labeled scenarios (LLM-draft the GT triples, human-skim once) — roughly doubles the corpus and adds a second domain.
3. Relax GT ambiguity where the hand labels are arbitrary (e.g. accept `ensure`/`ensures` by lemma-normalizing GT predicates at load time) — some of the 0.066 is GT stylistic choice, not extraction error.

### 5.4 Pipeline changes the loop should be seeded with (backlog for Loop C)

Ordered by expected impact on the diagnostics:

1. **Fix the live/LLM 0.0 bug** in the default pipeline (contract mismatch) — prerequisite for any hybrid mode.
2. **RAG-proper prompt for `default`**: vector-match noun chunks first, inject top-k ontology nodes + property definitions into the prompt, verify returned IDs against the ontology. (Directly ports legacy L0→L1.)
3. **Copular and appositive handling in `open_v1`**: "X is a Y" → `rdf:type`/attribute triples; appositions → same-individual aliases. Likely the largest single coverage gap.
4. **Gap-fill stage in `open_v1`**: emit unconsumed noun chunks as candidate individuals (reuse `build_concept_candidates`, currently schema-only), grounded via the vector index — legacy's L2 idea, finally combined with relationship extraction.
5. **Wider dependency capture**: `ccomp`/`xcomp`/`acomp`, passive `agent`, conjunct expansion (subject/object `conj` fan-out — one sentence often encodes N triples).
6. **LLM label canonicalization** (`synthesis_mode="llm"` for individuals): the rule pipeline proposes triples, one cheap LLM call canonicalizes labels/predicates against the ontology vocabulary. This is what moved schema extraction 0.37→0.47; individuals should benefit more because the metric is label-exact on three slots.
7. **Per-source confidence bands** (legacy §3) so Brier becomes meaningful and `relation_confidence` stops being a constant.

## 6. Recommended sequencing

| Step | What | Cost | Unblocks |
|---|---|---|---|
| 1 | Soft-F1 + per-stage diagnostics in harness (§5.1) | small, offline | gives the loop a gradient; quantifies where 0.066 comes from |
| 2 | Dev/holdout split + GT predicate lemma-normalization (§5.3) | small | honest measurement |
| 3 | Diagnose the live-mode 0.0 bug | small | LLM/hybrid modes |
| 4 | Variant tournament runner (Loop B) | medium | algorithm-level A/B |
| 5 | Coverage changes #3–#5 as first tournament variants | medium | expected biggest strict-F1 jump |
| 6 | Agent-in-the-loop script (Loop C) with accept/revert gate | medium | autonomous refinement |
| 7 | LLM canonicalization + cassette refresh cadence (#6) | ~$ per accepted change | closing the last gap to floors |

The POC bar (strict F1 ≥ 0.50) is plausibly reachable with steps 1–5 alone: candidate-level coverage is the dominant failure class today, and every coverage fix compounds with soft-metric-guided knob tuning. The LLM canonicalization step is the insurance if label-exactness remains the residual blocker after coverage is fixed.

---

*Sources: `domain/pipelines/individual_extraction/{orchestrator,open_orchestrator}.py`, `domain/extraction/{services,open_extraction}.py`, `scripts/quality_loop.py`, `tests/integration/pipelines/` harness; legacy `rag/rag_pipeline_service.py`, `rag/processors/*`, `nlp/processors.py`, `api/rag_experiments.py`, `rag/test_scoring.py`.*
