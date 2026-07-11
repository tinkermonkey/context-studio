export const meta = {
  name: 'karpathy-loop',
  description: 'Run one Loop C iteration for individual-extraction refinement: evaluate, select failure targets, fan out experimenter agents, verify, accept/reject, update the ledger.',
  whenToUse: 'Invoke to run exactly ONE Karpathy-loop iteration (documentation/karpathy_loop_design.md §4.3) for the local-server individual-extraction pipelines. Each call is one iteration; drive repeated iterations from outside this script (e.g. via /loop) and thread state across calls through `args`: {iteration, consecutiveNoAccept, hypothesisCount, integrationBranch, holdoutFloors, maxConsecutiveNoAccept, cumulativeCostUsd, totalBudgetUsd}. Read the returned `stop` field (and `status`) after every call: "stopped" means a floor/plateau/budget stop-check tripped and the outer loop should halt; otherwise pass the returned `consecutiveNoAccept` and incremented `iteration` into the next call’s args. Do not invoke against the real corpus casually — one iteration runs the full variant tournament plus several worktree-isolated coding agents and can take a long time and real LLM cost.',
  phases: [
    { title: 'Evaluate', detail: 'Run Loop B (variant tournament); read incumbent scoreboard + error report' },
    { title: 'Select', detail: 'Rank failure classes by GT-triple count; drop hypotheses the ledger already rejected' },
    { title: 'Experiment', detail: 'Fan out one worktree-isolated agent per hypothesis' },
    { title: 'Verify', detail: 'Adversarial gate-integrity check per candidate' },
    { title: 'Decide', detail: 'Accept gate on the best verified candidate; merge or discard, append the ledger' },
  ],
}

// documentation/karpathy_loop_design.md §6 accept gate constants.
const EPSILON = 0.005
const HOLDOUT_SLACK = 0.02
// tests/integration/fixtures/pipelines/individual_extraction/NEEDS_HUMAN_REVIEW.md:
// 2 of today's 5 holdout scenarios have unreviewed, agent-drafted GT. Flip
// this to false only once every box in that file is checked off by a human
// — do not flip it just because more scenarios/time have passed.
const HOLDOUT_GT_REVIEW_PENDING = true
// §1 exit criterion (strict floors on holdout).
const DEFAULT_HOLDOUT_FLOORS = { precision: 0.6, recall: 0.5, f1: 0.5 }
// Brier is intentionally not part of this floor check: the tournament runner
// does not compute it yet (needs per-source confidence bands — backlog
// item 6 / design doc §1); wire it in once that lands.
const DEFAULT_INTEGRATION_BRANCH = 'experiment/karpathy-loop'
const DEFAULT_MAX_CONSECUTIVE_NO_ACCEPT = 3
const DEFAULT_HYPOTHESIS_COUNT = 3
const MIN_HYPOTHESIS_COUNT = 2
const MAX_HYPOTHESIS_COUNT = 4

// Seeded hypothesis backlog (documentation/karpathy_loop_design.md §7,
// items 1-6 — item 0, the live-LLM-path bugfix, already landed in Phase 2).
// `stages` maps a hypothesis to the failure-report stage(s)
// (candidate_missing / relation_not_derived / label_mismatch /
// predicate_mismatch) it is expected to move; an empty list means it targets
// a metric outside the per-stage breakdown (e.g. Brier) and is only picked
// as a last-resort filler.
const SEED_BACKLOG = [
  {
    id: 'copular_appositive_handling',
    stages: ['candidate_missing', 'relation_not_derived'],
    summary:
      'Copular/appositive handling in open_v1: "X is a Y" -> type/attribute triples; appositions -> aliases (design doc §7 item 2).',
  },
  {
    id: 'gap_fill_stage',
    stages: ['candidate_missing'],
    summary:
      'Gap-fill stage in open_v1: emit noun chunks unconsumed by SVO triples as candidate individuals, grounded via the vector index, reusing build_concept_candidates (design doc §7 item 3).',
  },
  {
    id: 'wider_dependency_capture',
    stages: ['relation_not_derived', 'candidate_missing'],
    summary:
      'Wider dependency capture in open_v1: ccomp/xcomp/acomp, passive agent, conjunct fan-out (one sentence -> N triples) (design doc §7 item 4).',
  },
  {
    id: 'llm_label_canonicalization',
    stages: ['label_mismatch', 'predicate_mismatch'],
    summary:
      'LLM label canonicalization for individuals: the rule pipeline proposes triples, one cheap LLM call canonicalizes labels/predicates against the ontology vocabulary (design doc §7 item 5).',
  },
  {
    id: 'rag_proper_prompting_default',
    stages: ['candidate_missing'],
    summary:
      'RAG-proper prompting for the default (LLM) pipeline: vector-match noun chunks against the ontology first, inject top-k matched classes + property definitions into the prompt, verify LLM-returned IDs against the ontology instead of trusting them (design doc §7 item 1).',
    // scripts/quality_tournament.py's build_registry() deliberately does not
    // register the `default` pipeline yet (no cassettes recorded for it) --
    // an experimenter assigned this hypothesis today would implement a
    // change Loop B cannot score at all, guaranteeing an accept-gate
    // rejection regardless of merit. Unblock once `default` is registered
    // there (see that function's docstring for the exact steps).
    blocked: true,
  },
  {
    id: 'per_source_confidence_bands',
    stages: [],
    summary:
      'Per-source confidence bands (legacy-style calibrated ranges per extraction source) to make Brier meaningful and enable apply-time thresholding (design doc §7 item 6).',
  },
]

const EVALUATION_SCHEMA = {
  type: 'object',
  required: ['incumbentVariant', 'dev', 'holdout', 'failureStageCounts', 'errorReportPath', 'errorReportMarkdownPath', 'scoreboardPath'],
  properties: {
    incumbentVariant: { type: 'string' },
    dev: {
      type: 'object',
      required: ['strict_f1', 'soft_f1'],
      properties: {
        strict_precision: { type: 'number' },
        strict_recall: { type: 'number' },
        strict_f1: { type: 'number' },
        soft_f1: { type: 'number' },
        candidate_recall: { type: 'number' },
        predicate_recall: { type: 'number' },
      },
    },
    holdout: {
      type: 'object',
      required: ['strict_precision', 'strict_recall', 'strict_f1', 'soft_f1'],
      properties: {
        strict_precision: { type: 'number' },
        strict_recall: { type: 'number' },
        strict_f1: { type: 'number' },
        soft_f1: { type: 'number' },
      },
    },
    // Wave 1 DR bootstrap-scenario diagnostics (karpathy_loop_dr_ontology_design.md
    // §5 / dataset_split.py's DR_BOOTSTRAP_SCENARIOS). Reported every iteration for
    // visibility and logged to the ledger (see decidePrompt), but this object is
    // NEVER read by meetsFloors or acceptGate below -- neither function even accepts
    // it as a parameter, so it structurally cannot gate a stop/accept/reject decision.
    bootstrap: {
      type: 'object',
      properties: {
        strict_f1: { type: 'number' },
        soft_f1: { type: 'number' },
      },
    },
    // Wave 4 informal-prose diagnostics (karpathy_loop_dr_ontology_design.md §8,
    // #1109 Phase 8 / dataset_split.py's WAVE4_INFORMAL_SCENARIOS). Same
    // always-reported, never-gates-a-decision treatment as `bootstrap` above --
    // quality_tournament.py's `_run_variant` computes it the same way and
    // `meetsFloors`/`acceptGate` below never accept it as a parameter.
    wave4: {
      type: 'object',
      properties: {
        strict_f1: { type: 'number' },
        soft_f1: { type: 'number' },
      },
    },
    failureStageCounts: { type: 'object' },
    errorReportPath: { type: 'string' },
    errorReportMarkdownPath: { type: 'string' },
    scoreboardPath: { type: 'string' },
  },
}

const LEDGER_SCHEMA = {
  type: 'object',
  required: ['rejectedHypotheses'],
  properties: { rejectedHypotheses: { type: 'array', items: { type: 'string' } } },
}

const EXPERIMENT_RESULT_SCHEMA = {
  type: 'object',
  required: [
    'hypothesisId', 'worktreePath', 'branchName', 'baseCommit', 'diffStat', 'changedFiles',
    'touchesPrompt', 'cassettesRefreshed', 'testsPassed', 'dev', 'holdout', 'summary', 'errorReportDelta',
  ],
  properties: {
    hypothesisId: { type: 'string' },
    worktreePath: { type: 'string' },
    branchName: { type: 'string' },
    baseCommit: { type: 'string' },
    diffStat: { type: 'string' },
    changedFiles: { type: 'array', items: { type: 'string' } },
    touchesPrompt: { type: 'boolean' },
    cassettesRefreshed: { type: 'boolean' },
    testsPassed: { type: 'boolean' },
    testsSummary: { type: 'string' },
    dev: {
      type: 'object',
      required: ['strict_f1', 'soft_f1'],
      properties: {
        strict_f1: { type: 'number' },
        soft_f1: { type: 'number' },
        candidate_recall: { type: 'number' },
        predicate_recall: { type: 'number' },
      },
    },
    holdout: {
      type: 'object',
      required: ['strict_f1', 'soft_f1'],
      properties: { strict_f1: { type: 'number' }, soft_f1: { type: 'number' } },
    },
    // Diagnostic-only, same as EVALUATION_SCHEMA.bootstrap above -- reported for the
    // ledger, never an input to verification or the accept gate.
    bootstrap: {
      type: 'object',
      properties: { strict_f1: { type: 'number' }, soft_f1: { type: 'number' } },
    },
    // Diagnostic-only, same as EVALUATION_SCHEMA.wave4 above -- reported for the
    // ledger, never an input to verification or the accept gate.
    wave4: {
      type: 'object',
      properties: { strict_f1: { type: 'number' }, soft_f1: { type: 'number' } },
    },
    summary: { type: 'string' },
    errorReportDelta: { type: 'string' },
  },
}

const VERIFY_SCHEMA = {
  type: 'object',
  required: ['hypothesisId', 'integrityOk', 'forbiddenPathHits', 'testsReproduced', 'singleChangeOk', 'diffMatchesHypothesis', 'verdict', 'reason'],
  properties: {
    hypothesisId: { type: 'string' },
    integrityOk: { type: 'boolean' },
    forbiddenPathHits: { type: 'array', items: { type: 'string' } },
    testsReproduced: { type: 'boolean' },
    singleChangeOk: { type: 'boolean' },
    diffMatchesHypothesis: { type: 'boolean' },
    verdict: { type: 'string', enum: ['pass', 'fail'] },
    reason: { type: 'string' },
  },
}

const DECIDE_SCHEMA = {
  type: 'object',
  required: ['hypothesisId', 'decision', 'ledgerAppended'],
  properties: {
    hypothesisId: { type: 'string' },
    decision: { type: 'string', enum: ['accepted', 'rejected'] },
    merged: { type: 'boolean' },
    cassettesRefreshed: { type: 'boolean' },
    worktreeDiscarded: { type: 'boolean' },
    ledgerAppended: { type: 'boolean' },
    notes: { type: 'string' },
  },
}

const LEDGER_READ_PROMPT = [
  'From `local-server/`, run `python experiments/ledger.py rejected-hypotheses` and return every printed line',
  '(one hypothesis id per line; empty output means no rejections yet) as `rejectedHypotheses`.',
  'Return structured output only — no prose.',
].join('\n')

function evaluatePrompt() {
  return [
    'Run Loop B — the individual-extraction variant tournament — and report back the incumbent scoreboard and error report (documentation/karpathy_loop_design.md §4.3 step 1).',
    '',
    'Steps:',
    '1. `cd local-server && source .venv/bin/activate`',
    '2. `python scripts/quality_tournament.py --pipeline individual --passes 2 --restarts 3`',
    '3. Find the newest `experiments/reports/tournament_<run_id>.md` scoreboard digest and the newest',
    '   `experiments/reports/tournament_open_v1_<run_id>.json` error report. (\'open_v1\' is the current',
    '   incumbent per `scripts/quality_tournament.py`\'s `build_registry()` docstring; if a different',
    '   variant has since become the registered incumbent, use its report instead and say so in `summary`.)',
    '4. Read the error report JSON: pull `dev_mean`, `holdout_mean`, and `failure_stage_counts`',
    '   (candidate_missing / relation_not_derived / label_mismatch / predicate_mismatch counts).',
    '5. Read the scoreboard telemetry',
    '   `tests/integration/fixtures/pipelines/_metrics/quality_tournament_individual_extraction.jsonl`',
    '   (last four rows for the incumbent variant: fixture_id="dev", fixture_id="holdout",',
    '   fixture_id="bootstrap", and fixture_id="wave4") for the full dev/holdout metrics objects (strict',
    '   precision/recall/F1, soft F1, candidate_recall, predicate_recall) and the bootstrap/wave4',
    '   diagnostic metrics.',
    '6. Return the bootstrap row as `bootstrap` and the wave4 row as `wave4` -- report both for',
    '   visibility and the ledger (karpathy_loop_dr_ontology_design.md §5 and §8: two distinct,',
    '   always-visible diagnostic groups), but both are informational only: never merge either into',
    '   `dev`/`holdout` and never let either change which failure stage looks worst in',
    '   `failureStageCounts`.',
    '',
    'Return structured output only — no prose.',
  ].join('\n')
}

function experimentPrompt(hypothesis, evaluation) {
  return [
    'You are one of several parallel experimenter agents refining the individual-extraction pipeline',
    '(Karpathy loop, documentation/karpathy_loop_design.md §4.3 step 3). Implement EXACTLY ONE change —',
    'the hypothesis below — and nothing else. Note any unrelated issues you notice in your summary instead',
    'of fixing them.',
    '',
    `Hypothesis id: ${hypothesis.id}`,
    `Hypothesis: ${hypothesis.summary}`,
    `Targeting failure stage: ${hypothesis.targetStage}`,
    '',
    `Context: the incumbent error report is at ${evaluation.errorReportPath} (JSON) /`,
    `${evaluation.errorReportMarkdownPath} (markdown digest). Read it and look specifically at missed`,
    `triples classified "${hypothesis.targetStage}" for concrete examples to design against.`,
    '',
    'Hard rules — violating any of these gets this candidate rejected on verification regardless of score',
    '(documentation/karpathy_loop_design.md §6):',
    '- Exactly one change. No bundled unrelated edits.',
    '- Never edit anything under `local-server/tests/integration/pipelines/_harness/` (the measurement layer).',
    '- Never edit GT fixtures or the split definition under',
    '  `local-server/tests/integration/fixtures/pipelines/individual_extraction/`.',
    '- Never edit `local-server/experiments/ledger.jsonl`.',
    '- Follow CLAUDE.md conventions: `domain/` has zero infrastructure imports (verify with',
    '  `python scripts/check_domain_imports.py`), dataclasses (not Pydantic/SQLAlchemy) in `domain/`,',
    '  snake_case functions/variables, CamelCase classes, triple double-quoted docstrings.',
    '',
    'Steps:',
    '1. `cd local-server && source .venv/bin/activate`',
    '2. Implement the change.',
    '3. If the change touches an LLM prompt, record fresh cassettes for it (scoped to that prompt only —',
    '   see `tests/integration/pipelines/_harness/cassettes.py` and the individual_extraction quality test',
    '   suite\'s `--refresh-cassettes` flow) and set `cassettesRefreshed: true`.',
    '4. Run the tests relevant to your change (at minimum the individual-extraction quality/unit tests you',
    '   touched, plus `python scripts/check_domain_imports.py`); set `testsPassed` and `testsSummary`.',
    '5. Run `python scripts/quality_tournament.py --pipeline individual --passes 1 --restarts 1` to get a',
    '   Loop-A-tuned dev/holdout evaluation of your changed pipeline, plus its bootstrap and wave4',
    '   diagnostics (report these as `bootstrap` and `wave4` for the ledger only -- they must never',
    '   factor into your own read of whether this candidate is working). Compare the new failure-stage',
    '   counts for your target stage against the incumbent report from step 3 above and summarize the',
    '   delta.',
    '6. Capture, from inside the worktree: `git diff main...HEAD --stat` (diffStat),',
    '   `git diff main...HEAD --name-only` (changedFiles), `git rev-parse --show-toplevel` (worktreePath),',
    '   `git branch --show-current` (branchName), `git merge-base HEAD main` (baseCommit).',
    '',
    'Return structured output only — no prose.',
  ].join('\n')
}

function verifyPrompt(candidate) {
  return [
    'You are the adversarial verifier for one Karpathy-loop experiment candidate',
    '(documentation/karpathy_loop_design.md §4.3 step 4 / §6). Default to failing the candidate if anything',
    'is ambiguous.',
    '',
    `Candidate hypothesis id: ${candidate.hypothesisId}`,
    `Candidate summary: ${candidate.summary}`,
    `Worktree: ${candidate.worktreePath} (branch ${candidate.branchName}, base ${candidate.baseCommit})`,
    `Claimed changed files: ${JSON.stringify(candidate.changedFiles)}`,
    `Claimed diff stat: ${candidate.diffStat}`,
    `Claimed tests passed: ${candidate.testsPassed}`,
    '',
    'Checks — ALL must pass for verdict "pass":',
    '1. Integrity: `cd` into the worktree and run `git diff main...HEAD --name-only`. FAIL',
    '   (`integrityOk: false`, list every offender in `forbiddenPathHits`) if any changed path starts with',
    '   `local-server/tests/integration/pipelines/_harness/` or',
    '   `local-server/tests/integration/fixtures/pipelines/individual_extraction/`, or equals',
    '   `local-server/experiments/ledger.jsonl`.',
    '2. Single change: read the actual diff (`git diff main...HEAD`). FAIL (`singleChangeOk: false`) if it',
    '   bundles edits addressing more than one concern.',
    '3. Diff matches hypothesis: does the diff actually implement what the candidate summary claims? FAIL',
    '   (`diffMatchesHypothesis: false`) on mismatch.',
    '4. Tests: re-run the tests the candidate claims to have run (and',
    '   `python scripts/check_domain_imports.py`) inside the worktree. FAIL (`testsReproduced: false`) if',
    '   anything fails now, even if the candidate claimed success.',
    '',
    'Return structured output only — no prose.',
  ].join('\n')
}

function decidePrompt(candidate, decision, reason, iteration, integrationBranch, incumbentVariant) {
  // cost_usd is left at 0 here: real per-experiment USD accounting requires
  // wiring the workflow's token budget to the active model's per-token
  // price, which is out of scope for this orchestration-mechanics phase
  // (documentation/karpathy_loop_design.md §5) — a future phase can
  // populate it from budget deltas.
  const ledgerEntry = {
    experiment_id: `${iteration}-${candidate.hypothesisId}`,
    iteration,
    hypothesis: candidate.hypothesisId,
    // Distinct from `agent` (§8 example: "open_v1+copular" vs "worktree-2") —
    // `variant` names the pipeline configuration for future target-selection
    // and history review; `agent` identifies which worktree/branch did it.
    variant: `${incumbentVariant}+${candidate.hypothesisId}`,
    diff_stat: candidate.diffStat,
    base_commit: candidate.baseCommit,
    dev: candidate.dev,
    holdout: candidate.holdout,
    // Diagnostic-only Wave 1 DR bootstrap metrics (karpathy_loop_dr_ontology_design.md
    // §5), logged here purely so the ledger's history of an experiment is complete --
    // ledger.py's `validate_entry` does not require this field, and nothing that reads
    // the ledger (e.g. `rejected_hypotheses`) consults it. `decision` above was already
    // computed from `dev`/`holdout` alone (see `acceptGate`, which never takes a
    // bootstrap argument), so this can never itself have been grounds for `decision`.
    bootstrap: candidate.bootstrap || null,
    // Diagnostic-only Wave 4 informal-prose metrics (karpathy_loop_dr_ontology_design.md
    // §8, #1109 Phase 8) -- same treatment as `bootstrap` above: logged for a complete
    // ledger history, never consulted by any ledger reader, and never itself grounds
    // for `decision` since `acceptGate` never takes a wave4 argument either.
    wave4: candidate.wave4 || null,
    decision,
    reason,
    cost_usd: 0,
    agent: candidate.branchName,
  }
  // Passed to the agent as a literal heredoc body (see the `append --stdin`
  // step below), never interpolated into a single-quoted shell argument —
  // `reason` routinely contains free-form LLM text (verifier prose) that can
  // carry apostrophes, backticks, or `$`, any of which would break a
  // single-quoted `'...'` shell literal.
  const ledgerEntryJson = JSON.stringify(ledgerEntry)

  const lines = [
    `Experiment "${candidate.hypothesisId}" in worktree ${candidate.worktreePath}`,
    `(branch ${candidate.branchName}) was ${decision.toUpperCase()} in Karpathy-loop iteration ${iteration}`,
    '(documentation/karpathy_loop_design.md §4.3 step 5 / §8).',
    `Reason: ${reason}`,
    '',
    'Work from the repository root (NOT the worktree) for every step below.',
  ]

  if (decision === 'accepted') {
    lines.push(
      `1. Ensure a local branch \`${integrationBranch}\` exists (create it from \`main\` if absent:`,
      `   \`git branch ${integrationBranch} main\`).`,
      `2. \`git checkout ${integrationBranch} && git merge --no-ff ${candidate.branchName}\`. Resolve only`,
      '   trivial conflicts; if the merge is non-trivial, stop and report the conflict instead of guessing.',
      candidate.touchesPrompt
        ? '3. The candidate touches an LLM prompt — refresh cassettes on the merged branch (re-run the'
        + ' recording command from the candidate\'s cassette step) and commit the refreshed cassette files.'
        : '3. (no prompt changes claimed — skip cassette refresh)',
      '4. From `local-server/`, append the ledger entry via stdin. Do NOT paste the JSON into a',
      '   single-quoted shell argument — free-form text in `reason` can contain apostrophes, backticks,',
      '   or `$` that break shell quoting. Run this exactly, with the heredoc delimiter line unindented:',
      "   python experiments/ledger.py append --stdin <<'LEDGER_ENTRY_EOF'",
      ledgerEntryJson,
      '   LEDGER_ENTRY_EOF',
      '   Set `ledgerAppended: true` only if this command exits 0.',
      `5. \`git worktree remove ${candidate.worktreePath}\` (do NOT delete branch ${candidate.branchName} —`,
      '   it is now merged history on the integration branch).',
    )
  } else {
    lines.push(
      '1. From `local-server/`, append the ledger entry via stdin (same rationale as the accepted path —',
      '   do NOT paste the JSON into a single-quoted shell argument). Run this exactly, with the heredoc',
      '   delimiter line unindented:',
      "   python experiments/ledger.py append --stdin <<'LEDGER_ENTRY_EOF'",
      ledgerEntryJson,
      '   LEDGER_ENTRY_EOF',
      '   Set `ledgerAppended: true` only if this command exits 0.',
      `2. \`git worktree remove --force ${candidate.worktreePath}\`.`,
      `3. \`git branch -D ${candidate.branchName}\`.`,
    )
  }
  lines.push('', 'Return structured output only — no prose.')
  return lines.join('\n')
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function meetsFloors(holdout, floors, holdoutReviewPending) {
  // documentation/karpathy_loop_design.md §6 + NEEDS_HUMAN_REVIEW.md: never
  // declare POC success off holdout GT a human hasn't reviewed yet.
  if (holdoutReviewPending) return false
  return (
    holdout.strict_precision >= floors.precision
    && holdout.strict_recall >= floors.recall
    && holdout.strict_f1 >= floors.f1
  )
}

// documentation/karpathy_loop_design.md §4.3 step 2: rank failure classes
// by GT-triple count, map the top ones to backlog hypotheses, skip anything
// the ledger already rejected or that's marked `blocked` (Loop B cannot
// evaluate it yet — see the hypothesis's own comment in SEED_BACKLOG).
function selectTargets(failureStageCounts, rejectedHypothesisIds, count) {
  const rankedStages = Object.entries(failureStageCounts || {})
    .sort((a, b) => b[1] - a[1])
    .map(([stage]) => stage)

  const chosen = []
  const chosenIds = new Set()

  for (const stage of rankedStages) {
    if (chosen.length >= count) break
    for (const hyp of SEED_BACKLOG) {
      if (chosen.length >= count) break
      if (hyp.blocked) continue
      if (chosenIds.has(hyp.id) || rejectedHypothesisIds.includes(hyp.id)) continue
      if (!hyp.stages.includes(stage)) continue
      chosen.push({ id: hyp.id, summary: hyp.summary, targetStage: stage })
      chosenIds.add(hyp.id)
    }
  }

  // Backfill with any remaining untried hypothesis (including stage-less
  // ones like confidence bands) if the ranked stages didn't fill the fleet.
  for (const hyp of SEED_BACKLOG) {
    if (chosen.length >= count) break
    if (hyp.blocked) continue
    if (chosenIds.has(hyp.id) || rejectedHypothesisIds.includes(hyp.id)) continue
    chosen.push({ id: hyp.id, summary: hyp.summary, targetStage: hyp.stages[0] || 'general' })
    chosenIds.add(hyp.id)
  }

  return chosen
}

// documentation/karpathy_loop_design.md §6 accept gate.
//
// Holdout collapse is NOT yet treated as authoritative: 2 of today's 5
// holdout scenarios (arxiv_llm_research_lab, arxiv_researcher_profile) have
// agent-drafted ground truth that tests/integration/fixtures/pipelines/
// individual_extraction/NEEDS_HUMAN_REVIEW.md explicitly flags as unreviewed
// and "must not be treated as an authoritative accept/reject signal." Gating
// merges (or declaring POC success — see `meetsFloors`) on that GT is
// exactly the metric-gaming risk §6 warns against, so while
// `holdoutReviewPending` is true a holdout collapse is surfaced as a
// non-blocking advisory instead of a rejection reason. Pass `false` once
// every box in NEEDS_HUMAN_REVIEW.md is checked off by a human.
//
// Deliberately takes only `dev`/`holdout` inputs (karpathy_loop_dr_ontology_design.md
// §5 Must-Fix 2 / ADR-7, §8): Wave 1 DR bootstrap-scenario and Wave 4 informal-prose
// diagnostics are reported (see EVALUATION_SCHEMA.bootstrap/wave4,
// EXPERIMENT_RESULT_SCHEMA.bootstrap/wave4, and the ledger entry in decidePrompt) but
// never passed in here, so they cannot -- structurally, not just by convention -- be
// sufficient (or even relevant) grounds for accept/reject.
function acceptGate(candidate, incumbentDev, incumbentHoldout, epsilon, holdoutSlack, holdoutReviewPending) {
  const reasons = []
  const advisories = []

  const devSoftImproves = candidate.dev.soft_f1 - incumbentDev.soft_f1 > epsilon
  if (!devSoftImproves) {
    reasons.push(`dev soft-F1 ${candidate.dev.soft_f1} does not beat incumbent ${incumbentDev.soft_f1} by more than epsilon=${epsilon}`)
  }

  const noFloorRegression = candidate.dev.strict_f1 >= incumbentDev.strict_f1
  if (!noFloorRegression) {
    reasons.push(`dev strict-F1 ${candidate.dev.strict_f1} regresses below incumbent ${incumbentDev.strict_f1}`)
  }

  const holdoutCollapsed = candidate.holdout.strict_f1 < incumbentHoldout.strict_f1 - holdoutSlack
  const noHoldoutCollapse = holdoutReviewPending ? true : !holdoutCollapsed
  if (holdoutCollapsed) {
    const message = `holdout strict-F1 ${candidate.holdout.strict_f1} collapses more than ${holdoutSlack} below incumbent ${incumbentHoldout.strict_f1}`
    if (holdoutReviewPending) {
      advisories.push(`${message} (advisory only -- holdout GT pending human review per NEEDS_HUMAN_REVIEW.md; not blocking acceptance)`)
    } else {
      reasons.push(message)
    }
  }

  return { passes: devSoftImproves && noFloorRegression && noHoldoutCollapse, reasons, advisories }
}

// `args` may arrive already parsed, or — depending on how this workflow was
// invoked (a slash-command wrapper, or a stringified /loop hand-off) — as a
// JSON string. Without this, every read below silently falls back to its
// default, so state threading (iteration, consecutiveNoAccept, budgets,
// hypothesisCount) is quietly dropped and the loop restarts from scratch every
// call. Normalize to an object first.
let loopArgs = args
if (typeof loopArgs === 'string') {
  try {
    loopArgs = JSON.parse(loopArgs)
  } catch {
    loopArgs = {}
  }
}
if (!loopArgs || typeof loopArgs !== 'object') {
  loopArgs = {}
}

const iteration = loopArgs.iteration || 1
const consecutiveNoAccept = loopArgs.consecutiveNoAccept || 0
const maxConsecutiveNoAccept = loopArgs.maxConsecutiveNoAccept || DEFAULT_MAX_CONSECUTIVE_NO_ACCEPT
const hypothesisCount = clamp(loopArgs.hypothesisCount || DEFAULT_HYPOTHESIS_COUNT, MIN_HYPOTHESIS_COUNT, MAX_HYPOTHESIS_COUNT)
const integrationBranch = loopArgs.integrationBranch || DEFAULT_INTEGRATION_BRANCH
const holdoutFloors = loopArgs.holdoutFloors || DEFAULT_HOLDOUT_FLOORS
const cumulativeCostUsd = loopArgs.cumulativeCostUsd || 0
const totalBudgetUsd = loopArgs.totalBudgetUsd != null ? loopArgs.totalBudgetUsd : null

// §4.3 step 6, pre-flight half: don't spend anything on an iteration the
// caller already knows should not run.
if (consecutiveNoAccept >= maxConsecutiveNoAccept) {
  return {
    status: 'stopped',
    reason: `plateau: ${consecutiveNoAccept} consecutive no-accept iterations (>= ${maxConsecutiveNoAccept}) — escalate to human`,
    iteration,
    consecutiveNoAccept,
  }
}
if (totalBudgetUsd != null && cumulativeCostUsd >= totalBudgetUsd) {
  return {
    status: 'stopped',
    reason: `budget exhausted: cumulative $${cumulativeCostUsd} >= cap $${totalBudgetUsd}`,
    iteration,
    consecutiveNoAccept,
  }
}

phase('Evaluate')
log(`Karpathy loop iteration ${iteration}: evaluating incumbent (Loop B)`)
const evaluation = await agent(evaluatePrompt(), { schema: EVALUATION_SCHEMA, phase: 'Evaluate', label: 'evaluate:loopB' })
if (!evaluation) {
  return { status: 'error', reason: 'Evaluate step returned no result (agent skipped or failed)', iteration, consecutiveNoAccept }
}

// §4.3 step 6, other half: stop on success before spending anything else.
if (HOLDOUT_GT_REVIEW_PENDING && meetsFloors(evaluation.holdout, holdoutFloors, false)) {
  log('Holdout strict floors appear met, but GT for 2/5 holdout scenarios is still pending human review (NEEDS_HUMAN_REVIEW.md) -- not declaring success yet. Continuing the loop.')
}
if (meetsFloors(evaluation.holdout, holdoutFloors, HOLDOUT_GT_REVIEW_PENDING)) {
  return {
    status: 'stopped',
    reason: 'holdout strict floors met (§1 exit criterion)',
    iteration,
    consecutiveNoAccept,
    evaluation,
  }
}

phase('Select')
const ledgerInfo = await agent(LEDGER_READ_PROMPT, { schema: LEDGER_SCHEMA, phase: 'Select', label: 'select:ledger', effort: 'low' })
const rejectedHypotheses = (ledgerInfo && ledgerInfo.rejectedHypotheses) || []
const targets = selectTargets(evaluation.failureStageCounts, rejectedHypotheses, hypothesisCount)
log(`Selected ${targets.length} target hypothesis(es): ${targets.map((t) => t.id).join(', ') || '(none — all seeded hypotheses already rejected)'}`)

if (targets.length === 0) {
  return {
    status: 'no_accept',
    reason: 'no untried hypotheses remain in the seeded backlog for the current top failure classes',
    iteration,
    consecutiveNoAccept: consecutiveNoAccept + 1,
    evaluation,
  }
}

phase('Experiment')
const experimentResults = await parallel(targets.map((target) => async () => {
  const result = await agent(experimentPrompt(target, evaluation), {
    schema: EXPERIMENT_RESULT_SCHEMA,
    phase: 'Experiment',
    label: `experiment:${target.id}`,
    isolation: 'worktree',
  })
  return result ? { ...result, hypothesisId: result.hypothesisId || target.id } : null
}))
const candidates = experimentResults.filter(Boolean)

if (candidates.length === 0) {
  return {
    status: 'no_accept',
    reason: 'all experimenter agents failed or were skipped',
    iteration,
    consecutiveNoAccept: consecutiveNoAccept + 1,
    evaluation,
    targets,
  }
}

phase('Verify')
const verdicts = await parallel(candidates.map((candidate) => () =>
  agent(verifyPrompt(candidate), { schema: VERIFY_SCHEMA, phase: 'Verify', label: `verify:${candidate.hypothesisId}` })
))
const paired = candidates.map((candidate, i) => ({ candidate, verdict: verdicts[i] }))
const verified = paired.filter((p) =>
  p.verdict
  && p.verdict.verdict === 'pass'
  && p.verdict.integrityOk
  && p.verdict.testsReproduced
  && p.verdict.singleChangeOk
  && p.verdict.diffMatchesHypothesis
  && (p.verdict.forbiddenPathHits || []).length === 0
)

let best = null
for (const p of verified) {
  if (!best || p.candidate.dev.soft_f1 > best.candidate.dev.soft_f1) best = p
}

let gateResult = null
if (best) {
  gateResult = acceptGate(best.candidate, evaluation.dev, evaluation.holdout, EPSILON, HOLDOUT_SLACK, HOLDOUT_GT_REVIEW_PENDING)
  if (gateResult.advisories.length) {
    log(`Accept-gate advisories (non-blocking): ${gateResult.advisories.join('; ')}`)
  }
}
const accepted = Boolean(best && gateResult && gateResult.passes)

phase('Decide')
const decisions = paired.map((p) => {
  if (accepted && p.candidate.hypothesisId === best.candidate.hypothesisId) {
    return { candidate: p.candidate, decision: 'accepted', reason: 'passed verification and the §6 accept gate' }
  }
  const verifyFailed = !(p.verdict && p.verdict.verdict === 'pass')
  let reason
  if (verifyFailed) {
    reason = `failed verification: ${p.verdict ? p.verdict.reason : 'verifier agent returned no result'}`
  } else if (best && p.candidate.hypothesisId === best.candidate.hypothesisId) {
    reason = `verified but failed the §6 accept gate: ${gateResult.reasons.join('; ')}`
  } else {
    reason = 'verified but not the best-scoring verified candidate this iteration (§4.3 step 5: only the best verified candidate is checked against the accept gate)'
  }
  return { candidate: p.candidate, decision: 'rejected', reason }
})

const outcomes = await parallel(decisions.map((d) => () =>
  agent(decidePrompt(d.candidate, d.decision, d.reason, iteration, integrationBranch, evaluation.incumbentVariant), {
    schema: DECIDE_SCHEMA,
    phase: 'Decide',
    label: `decide:${d.candidate.hypothesisId}`,
  })
))

const nextConsecutiveNoAccept = accepted ? 0 : consecutiveNoAccept + 1

return {
  status: accepted ? 'accepted' : 'no_accept',
  iteration,
  consecutiveNoAccept: nextConsecutiveNoAccept,
  incumbentVariant: accepted ? best.candidate.branchName : evaluation.incumbentVariant,
  evaluation,
  targets,
  candidates: paired,
  decisions,
  outcomes,
  stop: nextConsecutiveNoAccept >= maxConsecutiveNoAccept
    ? { reason: `plateau reached after this iteration (${nextConsecutiveNoAccept} consecutive no-accept)` }
    : null,
}
