# Individual-Extraction Refinement — Consolidated Learnings

Companion to `karpathy_loop_design.md`. Captures the durable outcomes and lessons
from the Karpathy-loop refinement of the `default` (LLM) individual-extraction
pipeline, so the effort can be paused at a clean baseline without losing what was
learned.

## 1. Outcome — the `default` pipeline

**Scored grounded-only** (DR-spec scenarios; the throwaway-placeholder scenarios
were removed from the split — see §5). Offline cassette replay,
`scripts/quality_tournament.py`:

| variant | dev strict-F1 | dev soft-F1 | candidate_recall | label-acc (strict) | holdout strict-F1 |
|---|---|---|---|---|---|
| `open_v1` (rule / spaCy) | 0.059 | 0.111 | 0.50 | 0.449 | 0.036 |
| **`default` (grounded two-pass, current baseline)** | **0.659** | **0.681** | **0.858** | **0.877** | **0.939** |

**~11× strict-F1 over the rule baseline on the intended (grounded) task**, with
clean predicates (`relation_not_derived`→5, `predicate_mismatch`→0) and strong
label accuracy (0.877 strict). Holdout is high but thin (only 2 grounded holdout
scenarios today — advisory, not authoritative).

> **Note on the numbers:** an earlier version of this doc reported a "0.37 strict /
> ceiling" for the pipeline. That was a **mixed-corpus artifact**: ~44% of the old
> scored split was ungrounded placeholder scenarios that score ~0 and halved the
> average. On the grounded scenarios the pipeline was always ~0.66 — the "ceiling"
> was a measurement problem, now fixed (§5). The build progression (RAG grounding
> → two-pass → label canonicalization → relationship-object recall) each landed a
> real gain; those intermediate numbers were measured on the old mixed corpus.

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

## 5. The benchmark was polluted — the biggest finding

The apparent "diminishing returns / casing noise" turned out to be a **benchmark
composition problem**, not a pipeline problem. The old scored split was ~44%
**ungrounded placeholder scenarios**: software-architecture-concept prose
(`clean_code`, `design_patterns`, `object_oriented_design`, …) graded against a
**throwaway 3-class ontology** (`individual`/`property`/`entity`) with no domain
classes to identify against. Those scenarios test *free-form concept extraction*,
not the grounded individual identification this pipeline exists to do.

Split by ontology context, the current pipeline scored:

| scenarios | dev strict-F1 | dev soft-F1 | strict label-acc |
|---|---|---|---|
| DR-grounded | **0.66** | 0.68 | 0.88 |
| placeholder / throwaway | **0.00** | 0.07 | — |

The placeholder scenarios scored ~0 and dragged the average to 0.37, **and** were
the sole source of the surface-convention noise (their snake_case GT vs the
pipeline's natural labels; the DR GT uses Title Case, which the pipeline matches).
**Fix:** the placeholder scenarios were removed from the scored split
(`dataset_split.py`) — the benchmark is now **DR-grounded only**. The headline
score is the true one (§1): dev strict-F1 0.659, and `label_mismatch` collapsed
from 32→5 once the ungrounded scenarios were gone.

**Grounded-only failure taxonomy** (small, real): `candidate_missing` 26,
`label_mismatch` 5, `relation_not_derived` 5 — all modest and genuinely
grounded-extraction issues.

## 6. If the effort resumes — where the real value is

The measurement fix (removing placeholder scenarios) is **done**. Remaining, in
priority:

1. **Grow and human-review the grounded corpus.** The grounded holdout is now
   only 2 scenarios — high (0.939) but statistically thin; it can't authoritatively
   veto. A larger, SME-reviewed DR-grounded corpus (more Wave-2/3-style scenarios)
   would make both the holdout veto and strict-F1 trustworthy.
2. **The grounded `candidate_missing` tail (26).** With the benchmark clean this
   is now a genuine model/prompt problem (abstract-concept inference on grounded
   text), not a mechanical or measurement artifact.
3. **Retire the orphaned placeholder fixtures/cassettes** (10 scenario dirs +
   their `individual_extraction_default` cassettes) at some point — they are no
   longer scored but still on disk.
