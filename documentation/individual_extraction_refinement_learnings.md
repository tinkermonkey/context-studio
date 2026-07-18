# Individual-Extraction Refinement — Consolidated Learnings

Companion to `karpathy_loop_design.md`. Captures the durable outcomes and lessons
from the Karpathy-loop refinement of the `default` (LLM) individual-extraction
pipeline, so the effort can be paused at a clean baseline without losing what was
learned.

## 1. Outcome — the `default` pipeline

Measured on the DR individual-extraction dev split (offline cassette replay,
`scripts/quality_tournament.py`):

| stage | dev strict-F1 | dev soft-F1 | holdout soft-F1 |
|---|---|---|---|
| `open_v1` (rule / spaCy) | 0.086 | 0.132 | 0.102 |
| + RAG-grounded single-pass prompt | 0.324 | 0.412 | 0.458 |
| + two-pass (closed-predicate relationships) | 0.359 | 0.379 | — |
| + individual label canonicalization | 0.367 | 0.380 | 0.416 |
| **+ relationship-object recall (current baseline)** | **0.371** | **0.412** | **0.457** |

~4.3× strict-F1 over the rule baseline, with far cleaner predicates
(`relation_not_derived` 45→6, `predicate_mismatch`→0) and better labels.

## 2. Final pipeline architecture (what won)

The `default` pipeline (`domain/extraction/services.py`) is a **two-pass LLM
extraction** — spaCy is NOT on this path (it only drives `open_v1`):

- **Pass 1 — individual grounding.** The prompt is grounded, RAG-style, in the
  ontology's **class catalog**; the model emits every distinct individual as an
  `is_a` typing triple. Returned class refs are **canonicalized** against the
  ontology (`_canonicalize_triples_against_ontology`) by matching *any* of a
  class's identifying forms (external refs, identifier, title) — never dropping
  an unmatched triple (silent-failure-safe). Individual surface labels are then
  canonicalized to the ontology vocabulary.
- **Pass 2 — relationship derivation.** Relationships are derived only over the
  identified individuals, with the predicate **clamped to the ontology's closed
  vocabulary** (from property definitions' `canonical_predicate`). Pass 2 may
  **introduce a new concept/quality/outcome as the relationship OBJECT** (the fix
  that recovered abstract relationship targets); subject stays a pass-1
  individual and the predicate stays clamped.

Key property: exactness-first. Closing the predicate set crushed relation/
predicate drift; opening the object side recovered coverage without reopening
predicate drift.

## 3. Loop mechanics — three bugs fixed + a gate change

All landed on `main` with regression tests (`karpathy-loop.mechanics.test.mjs`):

1. **Stale-cache launch.** `Workflow({name})` ran a cached snapshot, not the edited
   `.claude/workflows/karpathy-loop.js`. **Launch by `scriptPath`** to use the live file.
2. **Hard-coded incumbent.** Evaluate read `open_v1`'s report regardless of the
   scoreboard. **Incumbent = rank-1 scoreboard variant** (auto-follows the best).
3. **Pipeline-blind selection.** `selectTargets` matched hypotheses to failure
   stages without regard to which pipeline they modify, so it kept picking
   `open_v1` hypotheses that cannot beat a `default` incumbent. **Pipeline-scoped
   selection** (`hypothesisPipeline`/`incumbentPipelineOf`).
4. **Symmetric accept gate (§6).** The gate rewarded only soft-F1 (coverage) and
   used strict-F1 (exactness) as a hard floor, so an exactness-improving change
   that dipped soft-F1 was structurally unacceptable. Now a candidate may win on
   **either** metric without materially harming the other (strict-driven
   acceptance tolerates a bounded `SOFT_SLACK`=0.05 soft dip). This is what let
   `two_pass` and `label_canonicalization` land.

**Operational note:** the integration branch (`experiment/karpathy-loop`) and
`main` are kept in lockstep — accepts are promoted to `main` between iterations,
because experimenter worktrees fork from `main`, so the incumbent base must live
there.

## 4. Methodology — the actual lesson

**Blind mechanical hypotheses failed; root-cause-driven ones won.** Two attempts
to recover `candidate_missing` by mechanically surfacing spaCy noun-chunks
regressed hard (dev soft-F1 ~halved) because they grounded arbitrary chunks to
classes — noise, not the missed entities. A **direct trace of where entities were
lost** revealed the real cause (pass-1 kept relationship *subjects* 75% of the
time but *objects* only 12%), and the very next hypothesis — targeting that exact
gap — won on every axis. Diagnose before spending.

## 5. Failure taxonomy — and why we stopped

- **`relation_not_derived` — solved** by the closed-predicate pass-2 (45→6).
- **`candidate_missing` — mostly addressed, hard tail remains.** ~82% of missed
  entities are literally present in the source; the relationship-object fix
  recovered the easy ones. The remainder is a genuinely harder tail (abstract
  inference, ontology class-typing artifacts).
- **`label_mismatch` — NOT a real quality gap.** After the above, the dominant
  remaining strict-F1 loss is **surface-convention mismatch**: the pipeline
  produces natural labels (`Event Loop`, `Testing`, `Classes`) while the ground
  truth uses snake_case-singular-lowercase (`event_loop`, `testing`, `class`),
  plus predicate phrasing (`should_follow` vs `follow`). The **soft** scorer
  already credits these (which is why soft-F1 ≫ strict-F1); **strict-F1 is
  therefore contaminated by GT surface convention**, not measuring real quality.

**Conclusion:** further strict-F1 gains against this corpus/GT would largely be
surface-form matching (case/plural/phrasing), not extraction quality. The
extraction refinement has hit its **useful ceiling for this measurement setup**.
`soft-F1` (~0.41 dev / ~0.46 holdout) is the truer quality signal.

## 6. If the effort resumes — where the real value is

Not in more extraction micro-optimization. Candidates, roughly in priority:

1. **Fix the measurement, not the pipeline.** Either make the strict scorer
   morphology-tolerant (case/number/snake-case normalization before exact match)
   so strict-F1 reflects real matches, or regenerate GT with a single, consistent
   label convention. Until then, evaluate on soft-F1.
2. **Grow and human-review the corpus/GT.** The holdout is thin (few scenarios)
   and some GT is agent-drafted; a larger, reviewed corpus would make both the
   holdout veto and strict-F1 trustworthy (see `NEEDS_HUMAN_REVIEW.md`).
3. **Only then**, if a real quality gap remains, attack the `candidate_missing`
   hard tail (abstract-concept inference) — a genuine model/prompt problem, not a
   mechanical one.
