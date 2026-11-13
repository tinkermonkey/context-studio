# Karpathy Loop — Automated Refinement of Individual Extraction

**Status:** Implemented (loop built and run; refinement paused at a clean baseline) **Date:** 2026-07-05 **Scope:** `local-server/` individual-extraction pipelines (`default` LLM, `open_v1`, and hybrids) **Companion analysis:** `local-server/documentation/claudes_thoughts/individual_extraction_design_analysis.md` **Outcome record:** `documentation/individual_extraction_refinement_learnings.md`

> **Update (2026-11):** the loop's objective moved to the **extraction benchmark** (§3.4): three long real documents with hand-made gold extractions, run through the same path a user's source takes. On the short-passage triple corpus the `default` pipeline had reached the old exit criterion and exhausted its backlog (every remaining "ceiling" was a measurement artifact), so the loop had nothing left to climb there. That corpus is now the regression guard. §4.3, §5, §6 and §7 below describe the loop as it runs today; earlier results are kept where they explain a decision.
>
> **Update (2026-07):** the loop has been built and run. The `default` pipeline described in §1/§7 as single-pass and scoring 0.0 is now a **grounded two-pass LLM pipeline** (class-catalog grounding → per-class-pair predicate clamp) scoring dev strict-F1 ≈ 0.66 on the grounded corpus, and the scored split is DR-grounded only (§3.3). §7 records which backlog hypotheses landed, were rejected, or remain open. §1 below is retained as the original problem statement.

## 1. Purpose

Individual extraction — extracting semantic-graph individuals and the relationships between them from text, resolved against a specific ontology — currently scores far below the POC quality bar (rule-mode F1 ≈ 0.066 vs. a 0.50 floor; the last live LLM run scored 0.0). Manual tune-and-rerun iteration is too slow to close that gap.

This document specifies an automated experimentation loop — a "Karpathy loop" — that repeatedly: evaluates the pipeline against ground truth, analyzes the errors, proposes a change, applies it, re-evaluates, and keeps the change only if quality improved. Two ground rules shape the design:

- **The extraction pipelines use LLMs.** The optimization target includes LLM-mode pipelines (RAG-prompted extraction, LLM label canonicalization), not just the deterministic spaCy path. The loop must therefore manage LLM cost, nondeterminism, and recording.

- **Claude Code executes the experiments.** Code changes, prompt changes, and knob-space changes are proposed and implemented by Claude Code — as sub-agents or a Workflow — not by a bespoke AutoML system. The loop infrastructure's job is to give those agents a trustworthy signal, an isolated place to work, and a gate they cannot argue with.

**Exit criterion ("good enough for POC"):** floors on the benchmark's holdout document, on its typed measures (an individual counts when it is found and given the gold type or an acceptable one) — typed precision ≥ 0.60, typed recall ≥ 0.50, typed F1 ≥ 0.50. The same floors were first set on the triple corpus's strict metrics, and were met there in 2026-07.

## 2. Definitions

## 3. Measurement layer (prerequisite — nothing loops without this)

The current metric is exact `(subject, predicate, object)` string-tuple match. It stays as the **acceptance floor**, but it provides no gradient: a triple with a lemma variant or different chunk boundary scores 0. The loop needs a signal that moves, and a decomposition that says *why* a triple was missed.

### 3.1 Metrics

Computed in `tests/integration/pipelines/_harness/metrics.py`, reported per scenario and as the mean:

- **strict P/R/F1** — existing exact-tuple match. The floor gate.

- **soft P/R/F1** — tiered triple credit: exact tuple = 1.0; all three slots match after lemma/stem normalization = 0.9; subject & object labels match by embedding cosine ≥ 0.85 and predicate matches by lemma = 0.7. The hill-climbing signal.

- **candidate_recall** — fraction of GT subject/object labels present among *any* extracted candidate (pre-matching). Isolates coverage failures.

- **predicate_recall** — fraction of GT (subject, object) pairs for which *some* relation was derived, regardless of predicate label. Isolates relation-derivation failures.

- **label_accuracy** — of derived pairs, how many matched labels strictly / softly. Isolates normalization failures.

- **brier** — existing, unchanged; requires per-source confidence (see §7 backlog) to be meaningful.

### 3.2 Error report

Every evaluation emits, alongside the metrics, a machine-readable error report: each missed GT triple classified by failure stage (`candidate_missing` → `relation_not_derived` → `label_mismatch` → `predicate_mismatch`), with the source sentence and the nearest extracted output. This report is the primary input to the experimenter agents — it is the "look at your errors" step of the loop, precomputed.

Format: JSON per run at `local-server/experiments/reports/<run_id>.json`; a short markdown digest (top failure classes, 5 worst scenarios, examples) rendered next to it for agent consumption.

### 3.3 Dataset split

The scored split is **DR-grounded only** (see `karpathy_loop_dr_ontology_design.md`). The 10 legacy software-architecture-concept "placeholder" scenarios — which ran against a throwaway 3-class ontology and tested free-form concept extraction rather than grounded identification — were removed from scoring (recorded with a `SEPARATE_CONTEXT` disposition, no longer scored). They were the sole source of the surface-convention (casing/pluralization) "failures"; the consolidated learnings doc has the full account.

- **Dev (6) / holdout (2)** split of the SME-authored DR-grounded scenarios, fixed by name in `dataset_split.py`. Loop A tunes knobs on dev. Since 2026-11 this corpus is Loop C's **regression guard**, not its objective (§6): the `default` variant's dev strict-F1 may not drop.

- **Corpus growth:** grow and human-review the grounded (Wave 2/3 SME-authored) corpus so both the holdout veto and strict-F1 become statistically trustworthy. This supersedes the earlier plan to promote the arxiv `fixture_*.json` files as placeholder-ontology scenarios.

- **Diagnostic groups (not scored):** recognition episodes (`RECOGNITION_EPISODES`, precision-floored dedup metrics), the Wave 1/4 bootstrap and informal groups, and the retired placeholder scenarios are all reported alongside the scored split but never gate an accept/reject decision.

- **GT normalization:** lemma-normalize GT predicate labels at load time (`ensures`/`ensure` are the same fact). This is a measurement correction, not a relaxation — applied identically to strict and soft metrics.

### 3.4 The extraction benchmark (Loop C's objective)

`local-server/tests/integration/fixtures/pipelines/extraction_benchmark/` holds three documents that describe software from different points of view, each with a `gold.json`: every individual a careful modeller finds in it, typed against the DR schema, with the passages that evidence it (its README says how they were made and what the fields mean).

| document | perspective | individuals (core) | role |
|---|---|---|---|
| `gitlab_architecture` | engineering | 122 (63) | dev |
| `edit_check` | product | 76 (42) | dev |
| `wikimedia_enterprise` | platform | 99 (38) | holdout |

A run is scored on the individuals that would reach the review queue (`_harness/benchmark.py`):

- **found F1** (`f1`) — precision and recall of finding the gold individuals, whatever type they were given. The coverage signal.
- **typed F1** (`typed_f1`) — found and given the gold type or one gold lists as acceptable. The exactness signal and the headline number.
- **core recall**, **type accuracy**, **relationship recall**, and a breakdown by DR layer.
- **failure counts** — gold individuals missed (core, supporting), found but mistyped, predictions that match nothing, known distractors extracted, relationships missed. These drive target selection (§4.3).

Relationships are scored on recall only: gold holds the relationships the text states most plainly, not every one a run could correctly derive.

The benchmark runs two ways. Offline, `scripts/benchmark_replay.py` runs the `default` pipeline in process over each document as a source (headings read, text chunked, each chunk extracted, chunks merged, operations planned) against the pinned DR spec the gold files were made for, answering every LLM call from a cassette; the tournament ends with this pass. Against a running server, `scripts/extraction_benchmark.py run` extracts a document with any pipeline configuration and scores the proposal it produces, and `load` puts the gold extractions into the workspace as datasets.

The gold files, the schema snapshots and the scorer are measurement: frozen for experiments (§6), changed only by a human-reviewed PR, with a `baseline_reset` in the ledger.

## 4. The loop algorithm

Three nested loops, in increasing cost per iteration. Inner loops run to convergence inside each outer-loop iteration.

```
Loop C (Claude Code refinement — hours/iteration, LLM + agent cost)
└── Loop B (variant tournament — minutes/iteration, cassette-replay cost)
    └── Loop A (knob sweep — seconds/eval, offline)
```

### 4.1 Loop A — knob sweep (deterministic, in-process)

Extends the existing `scripts/quality_loop.py` coordinate ascent:

- **Objective:** maximize mean **soft-F1 on dev**, subject to strict-F1(dev) ≥ incumbent (never trade the floor metric away).

- **Search space:** widened from today's 2 knobs to the full consumed-config surface of the variant, including categorical structure knobs as they land (dependency-role capture sets, chunk-boundary strategy, `similarity_threshold`, `top_k`, `ground_to_schema`, `require_schema_match`, gap-fill on/off, copular handling on/off, `synthesis_mode`).

- **Search strategy:** coordinate ascent with 2–3 random restarts (shuffled knob order, jittered starting point). The current single-start greedy pass demonstrably plateaus at baseline. Escalate to successive halving only if the space grows past ~10³ combinations.

- **LLM handling:** runs against cassettes only — a knob change never triggers a live LLM call. Knobs that would alter prompts (and thus miss the cassette) are excluded from Loop A and belong to Loop C.

Output: best knob config for the variant + telemetry rows (existing JSONL emitter).

### 4.2 Loop B — variant tournament

Reintroduces the legacy POC's strongest asset (the `rag_experiments` parallel-variant harness) on the new stack:

- A **variant registry** maps names to (orchestrator implementation, base config, knob space). Initially: `open_v1` (incumbent), plus each experiment branch under evaluation.

- The tournament runner evaluates every registered variant on all dev scenarios (Loop A tunes each variant's knobs first), then ranks by soft-F1 with strict-F1 and the §3.1 diagnostics displayed alongside.

- Output: a scoreboard (telemetry JSONL + markdown digest) and the per-variant error reports.

One invocation: `python scripts/quality_tournament.py --pipeline individual` (new script beside `quality_loop.py`).

The run ends with the benchmark pass (§3.4) and writes its summary beside the digest (`tournament_<run_id>_benchmark.json`).

**A stale recording is not a score.** The extraction service turns a cassette miss into "no triples", so a variant whose cassettes no longer answer its prompts used to read as a pipeline scoring 0 (it happened in 2026-09 and again by 2026-11, unnoticed both times). The tournament now counts misses: a stale variant is flagged at the top of the digest and the run exits non-zero; the benchmark pass reports `stale` or `not_recorded` instead of numbers.

### 4.3 Loop C — Claude Code refinement (the Karpathy loop proper)

One iteration:

- **Evaluate.** Run Loop B. Read the incumbent's benchmark measures (dev, holdout), its failure counts, and the triple corpus's guard measure. If any recording is stale or missing the iteration stops with an error before it spends anything.

- **Select targets.** Rank the benchmark's failure kinds by count and map the top ones to backlog hypotheses (§7). Consult the ledger to exclude hypotheses already decided.

- **Propose & implement (fan-out).** Spawn N experimenter sub-agents (N ≈ 2–4), each in an **isolated git worktree**, each assigned one hypothesis — either from the seeded backlog (§7) or derived from the error report. Each agent:

- implements exactly one change (code, prompt, or knob-space edit) on its branch;

- if the change touches an LLM prompt, or anything that feeds one (the class catalog, the predicate list, chunking), records both cassette sets again with the live LLM (cost-capped — see §5);

- runs the unit/integration tests relevant to its change;

- returns: diff summary, the candidate's benchmark and guard measures (taken by the same steps as the incumbent's), and how the failure counts moved.

- **Verify (adversarial).** A reviewer sub-agent checks each candidate for gate integrity (see §6): no edits to the frozen paths; tests pass; the committed cassettes replay to the claimed scores; the diff does what the hypothesis says, and nothing in it is specific to a benchmark document. Candidates that fail verification are rejected regardless of score.

- **Accept/reject.** For the best verified candidate, the orchestrator applies the **accept gate** (§6). Accepted → merge to the loop branch, refresh cassettes if applicable, append ledger entry, this variant becomes the incumbent. Rejected → discard worktree, append ledger entry with the negative result and the reason.

- **Stop check.** Stop when: the holdout document's typed floors are met (success); or K = 3 consecutive iterations produce no accepted change (plateau — escalate to human); or the iteration/cost budget is exhausted.

### 4.4 Orchestration in Claude Code

Loop C maps directly onto Claude Code's multi-agent primitives; no new orchestration framework is needed.

- **Orchestrator:** a Claude Code session (interactive, or scheduled via `/loop`) that owns iteration state, the ledger, and merge decisions. It never edits pipeline code itself.

- **Fan-out:** a Workflow script per iteration — `pipeline(hypotheses, implement, evaluate, verify)` with `isolation: 'worktree'` on the implement stage so parallel experiments cannot conflict. The workflow names no agent profiles; each step's prompt carries what the agent needs.

- **Sequencing:** hypotheses within one iteration must be independent (touch different failure classes or different files); otherwise run them in successive iterations. The orchestrator enforces this when selecting targets.

- **Human checkpoints:** the loop runs unattended within one iteration, but merges to `main` are batched and PR'd for human review at natural milestones (e.g. every accepted-change cluster, or when floors are reached). The loop branch (`experiment/karpathy-loop`) is the integration line in between.

## 5. LLM management

- **Determinism:** all pipeline LLM calls use temperature 0 and a fixed seed; the cassette key is `sha256(system|user|model|temperature|seed)`, so identical configs replay identically.

- **Cassette-first:** Loops A and B never make live calls. Only Loop C step 3 records.

- **Two cassette sets, two recorders:** the triple corpus (`cassettes/individual_extraction_default/`, `python scripts/record_default_cassettes.py --record`) and the benchmark (`cassettes/extraction_benchmark/`, `python scripts/benchmark_replay.py --record --spend`). The cassette key hashes the whole prompt, so a change to a prompt, or to anything that feeds one (the class catalog offered, the predicate list, how a source is chunked, the DR spec snapshot), invalidates the recordings it touches; anyone making such a change on `main` re-records in the same PR.

- **Refresh policy:** an experiment that changes a prompt records both sets on its branch; an accepted candidate's cassettes come to the integration branch with its merge. Recording uses the cheap model (gemini-flash class) unless an experiment specifically targets model choice. The benchmark is about 17 chunks, so two calls each.

- **Budget:** the orchestrator tracks estimated cost per iteration (cassette refresh count × per-refresh cost + agent tokens) against a per-iteration cap and a total-run cap, both set at launch. Exhaustion is a hard stop, recorded in the ledger.

- **Live-mode smoke:** one live (non-cassette) evaluation of the incumbent per accepted-change cluster, to ensure the recorded world hasn't diverged from reality. Prerequisite: fix the currently-broken live path (last run scored 0.0 across all scenarios — suspected output-contract mismatch; this is item 0 of the backlog).

## 6. Accept gate and guardrails

An experiment is **accepted** iff it improves the benchmark's dev documents and collapses neither the holdout document nor the triple corpus. The gate reads the benchmark's found F1 (coverage) and typed F1 (exactness) where the text below, written for the triple corpus, says soft-F1 and strict-F1; the reasoning is unchanged:

- **Improvement (benchmark dev):** found F1 improves by more than ε and typed F1 does not regress at all (coverage-driven), **or** typed F1 improves by more than ε and found F1 dips by at most COVERAGE_SLACK = 0.05 (exactness-driven). ε = 0.02 here, not the triple corpus's 0.005: every experiment that changes a prompt re-records, and three recordings of the unchanged incumbent (2026-11-12, temperature 0) ranged over 0.006 on each dev measure.
- **No holdout collapse:** typed F1 on the holdout document ≥ incumbent − 0.04 (the same three recordings ranged over 0.028 on it). One document is a noisy veto: a rejection on this ground alone deserves a human look before the hypothesis is written off.
- **Guard:** the triple corpus's dev strict-F1 for the `default` variant ≥ incumbent − 0.02 (GUARD_SLACK).
- **Integrity:** the diff touches none of the frozen paths: `tests/integration/pipelines/_harness/`, `tests/integration/fixtures/pipelines/extraction_benchmark/`, `tests/integration/fixtures/pipelines/individual_extraction/`, `tests/integration/fixtures/dr_spec/`, `scripts/quality_tournament.py`, `scripts/benchmark_replay.py`, `scripts/extraction_benchmark.py`, `experiments/ledger.jsonl`; and no prompt or code change names a benchmark document.
- **Health:** unchanged (below).

The original formulation, for the record:

- **Symmetric improvement (dev):** soft-F1 and strict-F1 measure different quality axes — soft-F1 rewards *coverage* (tiered near-miss credit, §3.1), strict-F1 rewards *exactness* (exact tuples). A curated knowledge graph values both, so a candidate may earn acceptance by improving **either**, provided it does not materially damage the other:
  - **Soft-driven:** mean soft-F1(dev) > incumbent by more than ε (ε = 0.005, to ignore noise-level wins) **and** mean strict-F1(dev) ≥ incumbent (the exactness floor stays hard — coverage gains never trade exactness away).
  - **Strict-driven:** mean strict-F1(dev) > incumbent by more than ε **and** mean soft-F1(dev) ≥ incumbent − SOFT_SLACK (SOFT_SLACK = 0.05) — a bounded coverage trade in exchange for exactness. A soft-F1 drop beyond SOFT_SLACK is a real coverage regression, not a trade, and is rejected.

  The gate is deliberately biased toward exactness: strict-driven acceptance tolerates a bounded soft dip, but soft-driven acceptance tolerates *no* strict regression. This reflects the product value — for a curated graph, a wrong edge or mislabeled node is a defect, whereas a slightly-less-complete-but-exact graph is preferable. (This replaced the earlier soft-F1-only improvement rule after `two_pass` improved strict-F1 +0.035 and label-accuracy +0.25 while dipping soft-F1 −0.033: a favorable exactness trade the old gate structurally could not accept.)

- **No holdout collapse:** strict-F1(holdout) ≥ incumbent − 0.02. Holdout never *selects* winners; it only vetoes overfitting. Note: with only 2 grounded holdout scenarios (today's split), a single scenario is ~50% of this score, so the veto is statistically noisy — it is not trustworthy enough to gate merges until the §3.3 grounded-corpus growth lands. Before then, treat any holdout-triggered rejection or acceptance as advisory, not authoritative.

- **Integrity:** the diff touches no files under the harness (`tests/integration/pipelines/_harness/`), no GT fixtures, no split definition, and no ledger history. Enforced mechanically by a path check on `git diff`, and reviewed by the verifier agent.

- **Health:** the backend test suite passes; domain-purity check passes (`scripts/check_domain_imports.py`).

Additional guardrails:

- **Negative-result memory:** every rejected experiment's hypothesis, diff summary, and scores go in the ledger (`local-server/experiments/ledger.jsonl`). Target selection excludes previously rejected hypotheses unless the codebase has materially changed in the relevant area.

- **Metric-gaming defense:** metrics/GT are frozen paths (gate rule 4). Changes to the measurement layer itself are allowed only as human-reviewed PRs outside the loop, and reset the incumbent baselines.

- **One change per experiment:** an experimenter agent that bundles unrelated edits is rejected on verification — attribution is the whole point of the loop.

- **Runaway defense:** worktrees are discarded on rejection; the loop branch only ever receives accepted, verified merges; iteration and cost caps are hard.

## 7. Seeded hypothesis backlog

Loop C started from ranked hypotheses rather than a cold start (full rationale in the companion analysis). Status annotations below reflect what has since landed on `main`; the durable outcomes live in `individual_extraction_refinement_learnings.md`.

### Done

- **Fix the live LLM path** (`default` pipeline scoring 0.0 — output-contract mismatch). Prerequisite, resolved.

- **RAG-proper prompting for **`default`** — DONE.** Landed as **prompt-level class-catalog grounding + canonicalize-only**, *not* the originally-phrased "vector-match noun chunks then verify IDs" mechanic. The ontology class catalog is injected into the pass-1 prompt and the LLM types each individual; returned class refs are canonicalized against the ontology by matching any of a class's identifying forms (external refs, identifier, title) and are never dropped (silent-failure-safe). Vector retrieval turned out to be the right tool for *recognition* (see below), not for typing.

- **Two-pass individual-then-relationship extraction for **`default`** (predicate-set clamping) — DONE (#1136).** Pass 1 identifies/types individuals; pass 2 derives relationships with the predicate **clamped per class-pair** using the ontology's `rdfs:domain`/`rdfs:range` (`domain_class_id`/`range_class_id`) + class hierarchy, offered as per-subject-class options. This crushed the predicate-drift failure mode (`develops`/`develops_alone`/`researches`) that Context Studio's fixed-predicate design exists to prevent.

- **Type new relationship-objects — DONE (#1139).** Pass 2 may introduce a *new* concept/quality/outcome as the relationship OBJECT (subject stays a pass-1 individual, predicate stays clamped). This recovered abstract relationship targets — the true cause of the `candidate_missing` tail, which a root-cause trace pinned to object recall (~12%), not subject recall.

- **LLM label canonicalization for individuals — DONE.** Individual surface labels are canonicalized to the ontology vocabulary (interim Title-Case heuristic).

### New capability

- **Semantic entity recognition / dedup — landed (#1137, epic #1142).** A recognition step resolves an extracted mention to an *existing* graph individual so a re-mention reuses the node instead of duplicating it: new `IndividualVectorIndex` port + `IndividualMatch` (`domain/ontology/ports.py`) and `SqliteIndividualVectorIndex` adapter, consumed by `ExtractionService._recognize_individuals` (exact-label then conservative class-scoped vector match; threshold 0.90 + ambiguity margin + acronym guard; never fuses two existing nodes). Measured on the multi-document `individual_recognition` episode corpus (`RECOGNITION_EPISODES`, precision-floored, reported but not scored). Finding: recognition *solves* the casing/pluralization surface-variant problem (precision 1.0 / recall 1.0) but does **not** resolve abbreviation-aliases (`K8s`↔`Kubernetes`, cosine ~0.39) — a documented limitation for a future alias registry.

### Rejected / not viable

- **Mechanical noun-chunk surfacing (gap-fill, copular/appositive, coverage-completion) — REJECTED.** Surfacing spaCy noun-chunks unconsumed by SVO triples as grounded candidates was proven a dead end twice (dev soft-F1 ~halved) — it grounds arbitrary chunks to classes (noise). The real cause of missed coverage was relationship-OBJECT recall, fixed via pass-2 concept-objects above, not candidate surfacing. This retires the `open_v1` gap-fill, copular-handling, and wider-dependency-capture hypotheses, which are off the `default` incumbent pipeline anyway.

- **Layer-scoped grounding (`grounding_layers`) for **`open_v1`** — REJECTED.** An `open_v1`-only knob, off the `default` incumbent pipeline; not worth carrying against the current incumbent.

- **Definition-driven / retrieval-based TYPING — found NOT viable as baseline (#1141, #1138).** Generic ArchiMate class definitions don't embed near specific instance names (e.g. "Nextflow"→`applicationcomponent` ranks 32/186), so vector retrieval is the wrong tool for *typing*. Retained as a component behind an `extraction_mode` flag but not baseline; the right use of vector retrieval is *recognition* (above).

### Benchmark backlog (2026-11, seeded in `.claude/workflows/karpathy-loop.js`)

Each maps to the benchmark failure kinds it should move.

- **Offer the whole class catalog** (`full_class_catalog`). Measured before any LLM call: for 150 of the 297 gold individuals, neither the gold class nor an acceptable one is among the 50 classes the identify prompt offers for the chunk that evidences the individual (Wikimedia Enterprise 60 of 99, where no motivation-layer class is ever offered; Edit check 40 of 76; GitLab 50 of 122). The prompt tells the model to pick the closest listed class, so those are mistyped by construction. The whole catalog is 193 references and titles.
- **Class definitions in the prompt** (`class_definitions_in_prompt`). The prompt lists `reference (Title)` only; DR's definitions and their "Use X instead when…" guidance never reach the model.
- **Taxonomy and layer guidance** (`layer_guidance_in_prompt`).
- **Statements as individuals** (`statement_individuals`): goals, requirements, principles, drivers, findings, outcomes have no name to be found by.
- **Chunk context** (`chunk_context_header`): a chunk does not know which document, or which section, it is from.
- **Tables and diagrams as inventories** (`tables_and_diagrams`).
- **The scope rule** (`scope_rule_in_prompt`): "every individual the text mentions" pulls in prior art and examples.
- **One class per individual at merge** (`one_class_per_individual_at_merge`).
- **Relationships across chunks** (`cross_chunk_relationships`).

**Baseline (2026-11-12, recorded with `google/gemini-3-flash-preview`):** dev found F1 0.411, typed F1 0.205; holdout found F1 0.326, typed F1 0.170; triple-corpus guard dev strict-F1 0.932. On the dev documents 126 gold individuals are not found (41 core), 36 are mistyped, 57 predictions match nothing, and 133 of 136 stated relationships are missing. Statements are the largest gap: 2 of the dev documents' 41 motivation-layer individuals are found, and 1 of the holdout document's 43. Per-document numbers and the run-to-run spread are in `local-server/experiments/README.md`.

Found while building the benchmark, not loop hypotheses: a response the provider errors on part-way (OpenRouter `finish_reason: "error"`) or cuts at the 8,000-token output limit fails to parse and is treated as a chunk with no individuals, with only a warning (it happened on the first recording: a chunk that yields about 30 individuals came back empty); the merge key drops corporate suffixes, so "Wikimedia Enterprise" (the product) and "Wikimedia Enterprise LLC" (the legal entity) would merge into one individual; and applying a proposal re-reads all its operations for each one applied, so a 2,000-operation proposal (a schema bundle) takes minutes.

### Still open

- **Per-source confidence bands** (legacy-style calibrated ranges per extraction source) to make Brier meaningful and enable apply-time thresholding.

- **Grow and human-review the grounded corpus** so the holdout veto and strict-F1 become statistically trustworthy (§3.3).

## 8. Artifacts and layout

```
local-server/
├── scripts/
│   ├── quality_loop.py            # Loop A (extended: soft-F1 objective, wider space, restarts)
│   ├── quality_tournament.py      # Loop B; ends with the benchmark pass
│   ├── benchmark_replay.py        # the default pipeline over the benchmark documents, from cassettes (or --record)
│   ├── extraction_benchmark.py    # validate / load / score / run against a running server
│   └── record_default_cassettes.py  # re-record the triple corpus
├── experiments/
│   ├── ledger.jsonl               # append-only experiment record (accepted + rejected)
│   ├── reports/<run_id>.json      # error reports (§3.2) + markdown digests
│   └── README.md                  # how to run each loop
└── tests/integration/pipelines/
    ├── _harness/metrics.py        # + soft-F1, diagnostics (§3.1)
    ├── _harness/benchmark.py      # benchmark gold files and scoring (§3.4)
    ├── fixtures/pipelines/extraction_benchmark/   # the three documents and their gold extractions
    └── fixtures/.../_metrics/*.jsonl   # existing telemetry (unchanged schema, new metric keys)
```

Ledger entry shape (one line per experiment; `dev` and `holdout` are benchmark measures, `guard` the triple corpus; entries before the 2026-11 baseline reset carry triple-corpus metrics in `dev`/`holdout`; the numbers here are illustrative):

```json
{"experiment_id": "...", "iteration": 12, "hypothesis": "full_class_catalog",
 "variant": "default+full_class_catalog", "diff_stat": "...", "base_commit": "...",
 "dev": {"typed_f1": 0.41, "f1": 0.58, "recall_core": 0.66, "type_accuracy": 0.71},
 "holdout": {"typed_f1": 0.37, "f1": 0.55},
 "guard": {"strict_f1": 0.92, "soft_f1": 0.93},
 "decision": "accepted", "reason": "", "cost_usd": 0.11, "agent": "worktree-2"}
```

## 9. Build plan

Phases 1–4 are useful standalone (they make manual experimentation honest and fast) even before Loop C automates the outer cycle.