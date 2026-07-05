# Karpathy Loop — Automated Refinement of Individual Extraction

**Status:** Proposed
**Date:** 2026-07-05
**Scope:** `local-server/` individual-extraction pipelines (`default` LLM, `open_v1`, and hybrids)
**Companion analysis:** `local-server/documentation/claudes_thoughts/individual_extraction_design_analysis.md`

## 1. Purpose

Individual extraction — extracting semantic-graph individuals and the relationships between them from text, resolved against a specific ontology — currently scores far below the POC quality bar (rule-mode F1 ≈ 0.066 vs. a 0.50 floor; the last live LLM run scored 0.0). Manual tune-and-rerun iteration is too slow to close that gap.

This document specifies an automated experimentation loop — a "Karpathy loop" — that repeatedly: evaluates the pipeline against ground truth, analyzes the errors, proposes a change, applies it, re-evaluates, and keeps the change only if quality improved. Two ground rules shape the design:

1. **The extraction pipelines use LLMs.** The optimization target includes LLM-mode pipelines (RAG-prompted extraction, LLM label canonicalization), not just the deterministic spaCy path. The loop must therefore manage LLM cost, nondeterminism, and recording.
2. **Claude Code executes the experiments.** Code changes, prompt changes, and knob-space changes are proposed and implemented by Claude Code — as sub-agents or a Workflow — not by a bespoke AutoML system. The loop infrastructure's job is to give those agents a trustworthy signal, an isolated place to work, and a gate they cannot argue with.

**Exit criterion ("good enough for POC"):** strict floors on the holdout set — precision ≥ 0.60, recall ≥ 0.50, F1 ≥ 0.50, Brier ≤ 0.25 — matching the existing `FloorGate` in the quality harness.

## 2. Definitions

| Term | Meaning |
|---|---|
| **Scenario** | One labeled fixture: `input.json` (text + ontology), `expected.json` (GT triples), `distractors.json` (negatives). Lives under `tests/integration/fixtures/pipelines/individual_extraction/`. |
| **Variant** | A named pipeline algorithm/configuration under test (e.g. `open_v1`, `open_v1+gap_fill`, `default+rag_prompt`). Registered so the harness can run several side by side. |
| **Knob** | A numeric/categorical config value within a variant (thresholds, dependency-role sets, top-k…). |
| **Experiment** | One proposed change (code, prompt, or knob-space edit) + its evaluation results + an accept/reject decision. |
| **Cassette** | Recorded LLM request/response replayed offline (`_harness/cassettes.py`). Committed; refreshed only on accepted prompt changes. |
| **Ledger** | Append-only JSONL of every experiment, including rejected ones, so failed hypotheses are not retried. |

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

The 10 hand-labeled scenarios are today both the tuning set and the eval set — the loop would overfit them.

- **Dev (7) / holdout (3)** split, fixed by name in the harness config. Loops optimize on dev; holdout is scored on every run but never used for selection.
- **Corpus growth:** promote the 8 unused arxiv `fixture_*.json` files into full scenarios (LLM-drafted GT, one human skim), assigned to dev/holdout to keep the split ratio. Target ≥ 18 scenarios across ≥ 2 domains before Loop C runs unattended. While in this directory, also resolve the stray `basic/` fixture dir (missing `distractors.json`/README, not one of the 10 counted scenarios) — either complete it into an 11th scenario or delete it so it isn't mistaken for a real one.
- **GT normalization:** lemma-normalize GT predicate labels at load time (`ensures`/`ensure` are the same fact). This is a measurement correction, not a relaxation — applied identically to strict and soft metrics.

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

### 4.3 Loop C — Claude Code refinement (the Karpathy loop proper)

One iteration:

1. **Evaluate.** Run Loop B. Produce scoreboard + error reports (§3.2).
2. **Select targets.** From the incumbent's error report, rank failure classes by GT-triple count. Consult the ledger to exclude hypotheses already tried and rejected.
3. **Propose & implement (fan-out).** Spawn N experimenter sub-agents (N ≈ 2–4), each in an **isolated git worktree**, each assigned one hypothesis — either from the seeded backlog (§7) or derived from the error report. Each agent:
   - implements exactly one change (code, prompt, or knob-space edit) on its branch;
   - if the change touches an LLM prompt, records fresh cassettes for it (live calls, cost-capped — see §5);
   - runs the unit/integration tests relevant to its change;
   - returns: diff summary, Loop A-tuned eval results on dev, and its own error-report delta.
4. **Verify (adversarial).** A reviewer sub-agent checks each candidate for gate integrity (see §6): no edits to metrics, harness, GT fixtures, or the split; tests pass; the diff does what the hypothesis says. Candidates that fail verification are rejected regardless of score.
5. **Accept/reject.** For the best verified candidate, the orchestrator applies the **accept gate** (§6). Accepted → merge to the loop branch, refresh cassettes if applicable, append ledger entry, this variant becomes the incumbent. Rejected → discard worktree, append ledger entry with the negative result and the reason.
6. **Stop check.** Stop when: holdout strict floors are met (success); or K = 3 consecutive iterations produce no accepted change (plateau — escalate to human); or the iteration/cost budget is exhausted.

### 4.4 Orchestration in Claude Code

Loop C maps directly onto Claude Code's multi-agent primitives; no new orchestration framework is needed.

- **Orchestrator:** a Claude Code session (interactive, or scheduled via `/loop`) that owns iteration state, the ledger, and merge decisions. It never edits pipeline code itself.
- **Fan-out:** a Workflow script per iteration — `pipeline(hypotheses, implement, evaluate, verify)` with `isolation: 'worktree'` on the implement stage so parallel experiments cannot conflict. Experimenter agents use the `local-server-engineer`/`context-studio-data-expert` profiles as appropriate; the verifier uses a reviewer profile.
- **Sequencing:** hypotheses within one iteration must be independent (touch different failure classes or different files); otherwise run them in successive iterations. The orchestrator enforces this when selecting targets.
- **Human checkpoints:** the loop runs unattended within one iteration, but merges to `main` are batched and PR'd for human review at natural milestones (e.g. every accepted-change cluster, or when floors are reached). The loop branch (`experiment/karpathy-loop`) is the integration line in between.

## 5. LLM management

- **Determinism:** all pipeline LLM calls use temperature 0 and a fixed seed; the cassette key is `sha256(system|user|model|temperature|seed)`, so identical configs replay identically.
- **Cassette-first:** Loops A and B never make live calls. Only Loop C step 3 records — and only for the specific prompts its change introduced.
- **Refresh policy:** cassettes are refreshed (a) when an experiment changes a prompt (scoped to that prompt), and (b) on a periodic full refresh (e.g. weekly or per accepted-change cluster) to catch drift. Refreshes use the cheap recording model (gemini-flash class, ~$0.03 per config per corpus at current size) unless an experiment specifically targets model choice.
- **Budget:** the orchestrator tracks estimated cost per iteration (cassette refresh count × per-refresh cost + agent tokens) against a per-iteration cap and a total-run cap, both set at launch. Exhaustion is a hard stop, recorded in the ledger.
- **Live-mode smoke:** one live (non-cassette) evaluation of the incumbent per accepted-change cluster, to ensure the recorded world hasn't diverged from reality. Prerequisite: fix the currently-broken live path (last run scored 0.0 across all scenarios — suspected output-contract mismatch; this is item 0 of the backlog).

## 6. Accept gate and guardrails

An experiment is **accepted** iff all of:

1. **Improvement:** mean soft-F1(dev) > incumbent by more than ε (ε = 0.005, to ignore noise-level wins).
2. **No floor regression:** mean strict-F1(dev) ≥ incumbent.
3. **No holdout collapse:** strict-F1(holdout) ≥ incumbent − 0.02. Holdout never *selects* winners; it only vetoes overfitting. Note: with only 3 holdout scenarios (today's split), a single scenario is ~33% of this score, so the veto is statistically noisy — it is not trustworthy enough to gate merges until the §3.3 corpus growth lands (≥ 18 scenarios). Before then, treat any holdout-triggered rejection or acceptance as advisory, not authoritative.
4. **Integrity:** the diff touches no files under the harness (`tests/integration/pipelines/_harness/`), no GT fixtures, no split definition, and no ledger history. Enforced mechanically by a path check on `git diff`, and reviewed by the verifier agent.
5. **Health:** the backend test suite passes; domain-purity check passes (`scripts/check_domain_imports.py`).

Additional guardrails:

- **Negative-result memory:** every rejected experiment's hypothesis, diff summary, and scores go in the ledger (`local-server/experiments/ledger.jsonl`). Target selection excludes previously rejected hypotheses unless the codebase has materially changed in the relevant area.
- **Metric-gaming defense:** metrics/GT are frozen paths (gate rule 4). Changes to the measurement layer itself are allowed only as human-reviewed PRs outside the loop, and reset the incumbent baselines.
- **One change per experiment:** an experimenter agent that bundles unrelated edits is rejected on verification — attribution is the whole point of the loop.
- **Runaway defense:** worktrees are discarded on rejection; the loop branch only ever receives accepted, verified merges; iteration and cost caps are hard.

## 7. Seeded hypothesis backlog

Loop C starts from ranked hypotheses rather than a cold start (full rationale in the companion analysis):

0. **Fix the live LLM path** (`default` pipeline scoring 0.0 — output-contract mismatch). Prerequisite, not an experiment.
1. **RAG-proper prompting for `default`:** vector-match noun chunks against the ontology first; inject top-k matched classes + property definitions into the prompt; verify LLM-returned IDs against the ontology instead of trusting them.
2. **Copular/appositive handling in `open_v1`:** "X is a Y" → type/attribute triples; appositions → aliases.
3. **Gap-fill stage in `open_v1`:** emit noun chunks unconsumed by SVO triples as candidate individuals, grounded via the vector index (reuses `build_concept_candidates`, currently schema-only — this is the legacy POC's noun-coverage idea finally combined with relationship extraction).
4. **Wider dependency capture:** `ccomp`/`xcomp`/`acomp`, passive `agent`, conjunct fan-out (one sentence → N triples).
5. **LLM label canonicalization for individuals:** rule pipeline proposes triples; one cheap LLM call canonicalizes labels/predicates against the ontology vocabulary (analogous change moved schema extraction 0.37 → 0.47).
6. **Per-source confidence bands** (legacy-style calibrated ranges per extraction source) to make Brier meaningful and enable apply-time thresholding.

## 8. Artifacts and layout

```
local-server/
├── scripts/
│   ├── quality_loop.py            # Loop A (extended: soft-F1 objective, wider space, restarts)
│   └── quality_tournament.py      # Loop B (new)
├── experiments/
│   ├── ledger.jsonl               # append-only experiment record (accepted + rejected)
│   ├── reports/<run_id>.json      # error reports (§3.2) + markdown digests
│   └── README.md                  # how to run each loop
└── tests/integration/pipelines/
    ├── _harness/metrics.py        # + soft-F1, diagnostics (§3.1)
    └── fixtures/.../_metrics/*.jsonl   # existing telemetry (unchanged schema, new metric keys)
```

Ledger entry shape (one line per experiment):

```json
{"experiment_id": "...", "iteration": 12, "hypothesis": "copular handling",
 "variant": "open_v1+copular", "diff_stat": "...", "base_commit": "...",
 "dev": {"strict_f1": 0.31, "soft_f1": 0.52, "candidate_recall": 0.71},
 "holdout": {"strict_f1": 0.28, "soft_f1": 0.47},
 "decision": "accepted", "reason": "", "cost_usd": 0.11, "agent": "worktree-2"}
```

## 9. Build plan

| Phase | Deliverable | Depends on |
|---|---|---|
| 1 | Measurement layer: soft-F1 + diagnostics + error reports + dev/holdout split + GT predicate normalization | — |
| 2 | Live-path bugfix (backlog item 0) | — |
| 3 | Loop A extension (objective, space, restarts) | 1 |
| 4 | Loop B tournament runner + variant registry | 1, 3 |
| 5 | Corpus growth to ≥ 18 scenarios | 1 |
| 6 | Loop C orchestration: workflow script, verifier profile, accept gate, ledger | 4 |
| 7 | First unattended Loop C run (budgeted), floors assessment | 2, 5, 6 |

Phases 1–4 are useful standalone (they make manual experimentation honest and fast) even before Loop C automates the outer cycle.
