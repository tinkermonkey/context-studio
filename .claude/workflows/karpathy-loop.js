export const meta = {
  name: 'karpathy-loop',
  description: 'Run one Loop C iteration for individual-extraction refinement: evaluate on the benchmark documents, select failure targets, fan out experimenter agents, verify, accept/reject, update the ledger.',
  whenToUse: 'Invoke to run exactly ONE Karpathy-loop iteration (documentation/karpathy_loop_design.md §4.3) for the local-server default individual-extraction pipeline. The objective is the extraction benchmark (long documents scored on the individuals found, tests/integration/fixtures/pipelines/extraction_benchmark/); the short-passage triple corpus is a regression guard. Each call is one iteration; drive repeated iterations from outside this script (e.g. via /loop) and thread state across calls through `args`: {iteration, consecutiveNoAccept, hypothesisCount, integrationBranch, holdoutFloors, maxConsecutiveNoAccept, cumulativeCostUsd, totalBudgetUsd}. Read the returned `stop` field (and `status`) after every call: "stopped" means a floor/plateau/budget stop-check tripped and the outer loop should halt; "error" means the evaluation could not be trusted (stale or unrecorded cassettes) and a human must record them; otherwise pass the returned `consecutiveNoAccept` and incremented `iteration` into the next call’s args. Do not invoke casually: one iteration runs the variant tournament plus several worktree-isolated coding agents, and every experiment that changes a prompt re-records cassettes with the live LLM.',
  phases: [
    { title: 'Evaluate', detail: 'Run Loop B (variant tournament + benchmark replay); read the incumbent scores and failure counts' },
    { title: 'Select', detail: 'Rank benchmark failure kinds by count; drop hypotheses the ledger already decided' },
    { title: 'Experiment', detail: 'Fan out one worktree-isolated agent per hypothesis' },
    { title: 'Verify', detail: 'Adversarial gate-integrity check per candidate' },
    { title: 'Decide', detail: 'Accept gate on the best verified candidate; merge or discard, append the ledger' },
  ],
}

// documentation/karpathy_loop_design.md §6 accept gate constants.
//
// The gate reads two benchmark measures over the dev documents:
//   - `f1`: found F1. Did the run find the gold individuals, whatever type it
//     gave them? The coverage signal.
//   - `typed_f1`: found and given the gold type or an acceptable one. The
//     exactness signal, and the headline number.
// A candidate earns acceptance by improving either without materially damaging
// the other, and must not collapse the holdout document or the triple corpus.
// Both margins sit above what re-recording the SAME pipeline moves the score
// (three recordings of the incumbent, 2026-11-12, temperature 0: dev found F1
// and typed F1 each ranged over 0.006; the holdout document's typed F1 over
// 0.028). Every experiment that changes a prompt re-records, so a smaller gain
// is not distinguishable from a second take.
const EPSILON = 0.02
const HOLDOUT_SLACK = 0.04
// When acceptance is exactness-driven (typed F1 improves), found F1 may dip by
// at most COVERAGE_SLACK: a bounded coverage trade in exchange for exactness.
const COVERAGE_SLACK = 0.05
// The short-passage triple corpus (dev strict-F1) may not drop by more than this.
const GUARD_SLACK = 0.02
// §1 exit criterion: floors on the holdout document's typed measures.
const DEFAULT_HOLDOUT_FLOORS = { precision: 0.6, recall: 0.5, f1: 0.5 }
const DEFAULT_INTEGRATION_BRANCH = 'experiment/karpathy-loop'
const DEFAULT_MAX_CONSECUTIVE_NO_ACCEPT = 3
const DEFAULT_HYPOTHESIS_COUNT = 3
const MIN_HYPOTHESIS_COUNT = 2
const MAX_HYPOTHESIS_COUNT = 4

// The failure kinds the benchmark reports (benchmark.failure_counts): gold
// individuals not found (by tier), found with a type gold does not accept,
// predictions that match nothing in gold, known distractors extracted, and
// gold relationships not stated.
const FAILURE_KINDS = ['missed_core', 'missed_supporting', 'mistyped', 'spurious', 'excluded_extracted', 'relationship_missed']

// Paths an experiment may never change: the measurement layer, the gold
// extractions and the schema they were judged by, and the experiment record.
const FROZEN_PATHS = [
  'local-server/tests/integration/pipelines/_harness/',
  'local-server/tests/integration/fixtures/pipelines/extraction_benchmark/',
  'local-server/tests/integration/fixtures/pipelines/individual_extraction/',
  'local-server/tests/integration/fixtures/dr_spec/',
  'local-server/scripts/quality_tournament.py',
  'local-server/scripts/benchmark_replay.py',
  'local-server/scripts/extraction_benchmark.py',
  'local-server/experiments/ledger.jsonl',
]

// Seeded hypothesis backlog (documentation/karpathy_loop_design.md §7). Every
// entry changes the default pipeline (domain/extraction/, domain/pipelines/
// individual_extraction/). `kinds` maps a hypothesis to the benchmark failure
// kinds it is expected to move; an empty list means it targets something the
// failure counts do not show and is only picked as a last-resort filler.
// Hypotheses from the earlier triple-corpus era (two-pass extraction, class
// catalog grounding, concept objects, label canonicalization: landed; noun-chunk
// surfacing and retrieval-based typing: rejected) are recorded in §7 of the
// design doc and are not repeated here.
const SEED_BACKLOG = [
  {
    // Measured before any LLM call (2026-11-12): for 150 of the 297 gold
    // individuals, neither the gold class nor an acceptable one is among the 50
    // classes the identify prompt offers for the chunk that evidences the
    // individual (Wikimedia Enterprise 60 of 99, where no motivation-layer class
    // is ever offered; Edit check 40 of 76; GitLab 50 of 122). The prompt tells
    // the model to pick the closest listed class, so those are mistyped by
    // construction.
    id: 'full_class_catalog',
    kinds: ['mistyped', 'missed_core', 'missed_supporting'],
    summary:
      'Offer the whole class catalog in the identify prompt. `ExtractionService._relevant_class_catalog` (domain/extraction/services.py) retrieves the 50 classes nearest the chunk by embedding; the class a gold individual needs is missing from that list for about half the benchmark individuals, and whole layers (motivation, for a business document) are never offered. The catalog is 193 references and titles, about 2k tokens: offer all of them, grouped by layer, or make the retrieval layer-balanced so no layer is absent.',
  },
  {
    id: 'class_definitions_in_prompt',
    kinds: ['mistyped'],
    summary:
      'Give the model the class definitions. The identify prompt lists each class as `reference (Title)` only; DR’s definitions, with their "Use X instead when…" guidance that separates a type from its neighbours (goal vs outcome vs requirement, component vs system software vs service), never reach it. Add the first sentence of each offered class’s definition, or add a typing step that shows the full definitions of the few closest classes for each identified individual.',
  },
  {
    id: 'layer_guidance_in_prompt',
    kinds: ['mistyped'],
    summary:
      'Give the model the taxonomy’s own account of itself: its description (what an element is, the granularity rule) and one line per layer saying what belongs there. Today the prompt names the ontology by title only (`Ontology: Documentation Robotics`).',
  },
  {
    id: 'statement_individuals',
    kinds: ['missed_core', 'missed_supporting'],
    summary:
      'Ask for statements, not only named things. The identify prompt asks for "a concrete named thing, concept, or component", so explicitly stated goals, requirements, principles, constraints, drivers, findings and outcomes (the motivation layer: a third to a half of the gold individuals in the product and platform documents) have nothing to be found by. Tell the model to extract a statement the text presents as one of these, with a short title of its own and the statement as the passage.',
  },
  {
    id: 'chunk_context_header',
    kinds: ['mistyped', 'missed_core', 'spurious'],
    summary:
      'Tell each chunk where it is. A source is extracted chunk by chunk (domain/pipelines/individual_extraction/orchestrator.py) and each chunk’s prompt holds only that chunk’s text: a chunk from the middle of a document does not know which system the document describes. Prefix each chunk with the document title and its heading path.',
  },
  {
    id: 'tables_and_diagrams',
    kinds: ['missed_core', 'missed_supporting'],
    summary:
      'Read tables and diagrams as inventories. GitLab’s component table and Mermaid diagrams, and Edit check’s outcome tables, name elements that prose never repeats. Check that chunking keeps a table’s header with its rows, and say in the identify prompt that table rows and diagram nodes name individuals.',
  },
  {
    id: 'scope_rule_in_prompt',
    kinds: ['spurious', 'excluded_extracted'],
    summary:
      'State the scope rule. The identify prompt says "every distinct individual the text mentions MUST appear", which pulls in prior art, tools named only for comparison, example values and link lists. Say that an individual is part of the system the document describes or its immediate context, and that things named only as examples, comparisons or references are not.',
  },
  {
    id: 'one_class_per_individual_at_merge',
    kinds: ['mistyped'],
    summary:
      'Settle one class per individual when chunks merge. `plan_individual_operations` (domain/pipelines/individual_extraction/source_operations.py) gives an individual every class any chunk typed it with, so a name typed differently in two chunks is proposed with both. Choose one: the class of the passage that defines it, else the most frequent.',
  },
  {
    id: 'cross_chunk_relationships',
    kinds: ['relationship_missed'],
    summary:
      'Derive relationships across chunks. The derive stage sees only the individuals identified in its own chunk, so a relationship between individuals introduced in different sections is never stated. After merging, run the derive stage once more over the merged individuals with the passages that mention two of them.',
  },
  {
    id: 'per_source_confidence_bands',
    kinds: [],
    summary:
      'Per-source confidence bands (calibrated ranges per extraction source) so apply-time thresholding means something. Not visible in the failure counts.',
  },
]

const BENCHMARK_METRICS = {
  type: 'object',
  required: ['typed_f1', 'f1'],
  properties: {
    typed_f1: { type: 'number' },
    typed_precision: { type: 'number' },
    typed_recall: { type: 'number' },
    f1: { type: 'number' },
    precision: { type: 'number' },
    recall: { type: 'number' },
    recall_core: { type: 'number' },
    type_accuracy: { type: 'number' },
    relationship_recall: { type: 'number' },
  },
}

// The triple corpus (short SME passages), reported every iteration as the
// regression guard. `strict_f1` over its dev scenarios is the one number the
// accept gate reads from it.
const GUARD_METRICS = {
  type: 'object',
  required: ['strict_f1'],
  properties: { strict_f1: { type: 'number' }, soft_f1: { type: 'number' } },
}

const EVALUATION_SCHEMA = {
  type: 'object',
  required: ['incumbentVariant', 'measurementStatus', 'errorReportPath', 'scoreboardPath'],
  properties: {
    incumbentVariant: { type: 'string' },
    // "scored" only when the tournament exited 0 and the benchmark summary's
    // status is "scored". Anything else stops the iteration before it spends.
    measurementStatus: { type: 'string', enum: ['scored', 'stale', 'not_recorded', 'failed'] },
    measurementDetail: { type: 'string' },
    dev: BENCHMARK_METRICS,
    holdout: BENCHMARK_METRICS,
    guard: GUARD_METRICS,
    failureCounts: { type: 'object' },
    errorReportPath: { type: 'string' },
    scoreboardPath: { type: 'string' },
  },
}

const LEDGER_SCHEMA = {
  type: 'object',
  required: ['rejectedHypotheses', 'acceptedHypotheses'],
  properties: {
    rejectedHypotheses: { type: 'array', items: { type: 'string' } },
    acceptedHypotheses: { type: 'array', items: { type: 'string' } },
  },
}

const EXPERIMENT_RESULT_SCHEMA = {
  type: 'object',
  required: [
    'hypothesisId', 'worktreePath', 'branchName', 'baseCommit', 'diffStat', 'changedFiles',
    'changesPrompts', 'cassettesRecorded', 'testsPassed', 'measurementStatus', 'dev', 'holdout', 'guard',
    'summary', 'failureCountsDelta',
  ],
  properties: {
    hypothesisId: { type: 'string' },
    worktreePath: { type: 'string' },
    branchName: { type: 'string' },
    baseCommit: { type: 'string' },
    diffStat: { type: 'string' },
    changedFiles: { type: 'array', items: { type: 'string' } },
    changesPrompts: { type: 'boolean' },
    cassettesRecorded: { type: 'boolean' },
    recordingCostUsd: { type: 'number' },
    testsPassed: { type: 'boolean' },
    testsSummary: { type: 'string' },
    measurementStatus: { type: 'string', enum: ['scored', 'stale', 'not_recorded', 'failed'] },
    dev: BENCHMARK_METRICS,
    holdout: BENCHMARK_METRICS,
    guard: GUARD_METRICS,
    summary: { type: 'string' },
    failureCountsDelta: { type: 'string' },
  },
}

const VERIFY_SCHEMA = {
  type: 'object',
  required: ['hypothesisId', 'integrityOk', 'forbiddenPathHits', 'testsReproduced', 'scoresReproduced', 'singleChangeOk', 'diffMatchesHypothesis', 'verdict', 'reason'],
  properties: {
    hypothesisId: { type: 'string' },
    integrityOk: { type: 'boolean' },
    forbiddenPathHits: { type: 'array', items: { type: 'string' } },
    testsReproduced: { type: 'boolean' },
    scoresReproduced: { type: 'boolean' },
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
    worktreeDiscarded: { type: 'boolean' },
    ledgerAppended: { type: 'boolean' },
    notes: { type: 'string' },
  },
}

const LEDGER_READ_PROMPT = [
  'From `local-server/`, with its virtual environment active, read the loop ledger\'s hypothesis history:',
  '1. `python experiments/ledger.py rejected-hypotheses` — return every printed line (one hypothesis id',
  '   per line; empty output means no rejections yet) as `rejectedHypotheses`.',
  '2. `python experiments/ledger.py accepted-hypotheses` — return every printed line as',
  '   `acceptedHypotheses` (empty output means no acceptances yet). These are already merged into the',
  '   incumbent, so selection skips them: re-drafting a merged hypothesis can only lose the accept gate.',
  'Both commands list only entries since the last baseline reset.',
  'Return structured output only — no prose.',
].join('\n')

// How to read one tournament run. Shared by the evaluate and experiment prompts
// so the incumbent and every candidate are measured by the same steps.
const MEASURE_STEPS = [
  'a. `python scripts/quality_tournament.py --pipeline individual --passes 1 --restarts 1`. Note its exit',
  '   code. It replays recorded LLM responses only; it never calls an LLM.',
  '   - Exit 3, or a "STALE CASSETTES" section at the top of the digest: the triple-corpus cassettes no',
  '     longer answer the pipeline\'s prompts. `measurementStatus` is "stale".',
  '   - Any other non-zero exit: `measurementStatus` is "failed"; put the error in the detail field.',
  'b. Find the newest `experiments/reports/tournament_<run_id>.md` digest (`scoreboardPath`) and the',
  '   `experiments/reports/tournament_<run_id>_benchmark.json` beside it (`errorReportPath`).',
  'c. Read the benchmark JSON. Its `status` must be "scored"; "not_recorded" or "stale" becomes the',
  '   `measurementStatus` (the benchmark cassettes are missing or out of date). When scored: `dev` and',
  '   `holdout` are its `dev` and `holdout` objects (typed_f1, typed_precision, typed_recall, f1,',
  '   precision, recall, recall_core, type_accuracy, relationship_recall), and the failure counts are',
  '   its `failure_counts`. Each document\'s `missed`, `mistyped`, `spurious` and `excluded_hits` lists',
  '   under `scores` are the concrete examples.',
  'd. `guard` is the `default` row of the digest\'s scoreboard table: its `dev strict-F1` column as',
  '   `strict_f1` and its `dev soft-F1` column as `soft_f1` (the short-passage triple corpus).',
]

function evaluatePrompt() {
  return [
    'Measure the incumbent individual-extraction pipeline (documentation/karpathy_loop_design.md §4.3 step 1).',
    'The incumbent is the `default` pipeline on `main`. Change nothing; this step only reads.',
    '',
    'Steps (from `local-server/`, virtual environment active):',
    ...MEASURE_STEPS,
    'e. Set `incumbentVariant` to "default". If `measurementStatus` is not "scored", still return',
    '   `incumbentVariant`, `measurementStatus`, `measurementDetail` (what is stale or missing, and the',
    '   recording command the digest names) and the two paths; leave the metrics out.',
    '',
    'Return structured output only — no prose.',
  ].join('\n')
}

function experimentPrompt(hypothesis, evaluation) {
  return [
    'You are one of several parallel experimenter agents refining the default individual-extraction',
    'pipeline (Karpathy loop, documentation/karpathy_loop_design.md §4.3 step 3). Implement EXACTLY ONE',
    'change — the hypothesis below — and nothing else. Note any unrelated issue you notice in your summary',
    'instead of fixing it.',
    '',
    `Hypothesis id: ${hypothesis.id}`,
    `Hypothesis: ${hypothesis.summary}`,
    `Targeting failure kind: ${hypothesis.targetKind}`,
    '',
    `Context: the incumbent's benchmark report is ${evaluation.errorReportPath}. Read the`,
    `"${hypothesis.targetKind}" examples in it (each document's missed / mistyped / spurious /`,
    'excluded_hits lists under `scores`) and design against concrete cases. The gold extractions and how',
    'they were made are in `tests/integration/fixtures/pipelines/extraction_benchmark/` (start with its',
    'README); read them, never edit them.',
    `Incumbent: dev typed F1 ${evaluation.dev.typed_f1}, dev found F1 ${evaluation.dev.f1}, holdout typed F1`,
    `${evaluation.holdout.typed_f1}, triple-corpus guard strict-F1 ${evaluation.guard.strict_f1}.`,
    '',
    'Hard rules — breaking any of these gets the candidate rejected on verification whatever it scores',
    '(documentation/karpathy_loop_design.md §6):',
    '- Exactly one change. No bundled unrelated edits.',
    '- Never change any of these paths (the measurement layer, the gold data, the record):',
    ...FROZEN_PATHS.map((p) => `    ${p}`),
    '- Do not write the document names, or anything specific to the benchmark documents, into prompts or',
    '  code: a change must be one you would make for any document.',
    '- Follow CLAUDE.md conventions: `domain/` has zero infrastructure imports (verify with',
    '  `python scripts/check_domain_imports.py`), dataclasses (not Pydantic/SQLAlchemy) in `domain/`,',
    '  snake_case functions/variables, CamelCase classes, triple double-quoted docstrings.',
    '',
    'Steps:',
    '1. This worktree should be at `main`. Confirm with `git merge-base --is-ancestor main HEAD`; if it is',
    '   behind, `git merge --no-edit main` before changing anything.',
    '2. `cd local-server`. The virtual environment lives in the main checkout: use its interpreter',
    '   (`<main checkout>/local-server/.venv/bin/python`) if this worktree has none.',
    '3. Implement the change.',
    '4. If the change alters any LLM prompt, or anything that feeds one (the class catalog, the predicate',
    '   list, how text is chunked), the recorded responses no longer apply. Record both cassette sets with',
    '   the live LLM (this costs money; it uses the cheap recording model):',
    '     `python scripts/record_default_cassettes.py --record`',
    '     `python scripts/benchmark_replay.py --record --spend`',
    '   Set `changesPrompts` and `cassettesRecorded`, and estimate `recordingCostUsd` from the token',
    '   counts in the cassettes. Never edit a cassette file by hand.',
    '5. Commit to this worktree branch: `git add -A && git commit -m "<hypothesis-id>: <what changed>"`.',
    '   Required: the verifier and the merge step read `git diff main...HEAD`, which shows only committed',
    '   changes.',
    '6. Run the tests for what you touched (the unit tests of the modules you changed, and',
    '   `python scripts/check_domain_imports.py`); set `testsPassed` and `testsSummary`.',
    '7. Measure the candidate exactly as the incumbent was measured:',
    ...MEASURE_STEPS,
    '   Report `measurementStatus`, `dev`, `holdout` and `guard`. A status other than "scored" means step 4',
    '   was needed and skipped, or failed: fix that rather than reporting numbers.',
    '8. In `failureCountsDelta`, compare the candidate\'s failure counts with the incumbent\'s for your',
    '   target kind and say which concrete examples moved.',
    '9. Capture, from inside the worktree after committing: `git diff main...HEAD --stat` (diffStat),',
    '   `git diff main...HEAD --name-only` (changedFiles), `git rev-parse --show-toplevel` (worktreePath),',
    '   `git branch --show-current` (branchName), `git merge-base HEAD main` (baseCommit).',
    '',
    'Return structured output only — no prose.',
  ].join('\n')
}

function verifyPrompt(candidate) {
  return [
    'You are the adversarial verifier for one Karpathy-loop experiment candidate',
    '(documentation/karpathy_loop_design.md §4.3 step 4 / §6). Fail the candidate if anything is ambiguous.',
    '',
    `Candidate hypothesis id: ${candidate.hypothesisId}`,
    `Candidate summary: ${candidate.summary}`,
    `Worktree: ${candidate.worktreePath} (branch ${candidate.branchName}, base ${candidate.baseCommit})`,
    `Claimed changed files: ${JSON.stringify(candidate.changedFiles)}`,
    `Claimed diff stat: ${candidate.diffStat}`,
    `Claimed tests passed: ${candidate.testsPassed}`,
    `Claimed scores: dev typed F1 ${candidate.dev.typed_f1}, dev found F1 ${candidate.dev.f1}, holdout typed F1 ${candidate.holdout.typed_f1}, guard strict-F1 ${candidate.guard.strict_f1}`,
    '',
    'Checks — ALL must pass for verdict "pass":',
    '1. Integrity: `cd` into the worktree and run `git diff main...HEAD --name-only`. FAIL',
    '   (`integrityOk: false`, list every offender in `forbiddenPathHits`) if any changed path starts with,',
    '   or equals, one of:',
    ...FROZEN_PATHS.map((p) => `     ${p}`),
    '   Also FAIL integrity if a prompt or code change names a benchmark document or quotes its text.',
    '2. Single change: read the diff (`git diff main...HEAD`, leaving the cassette JSON aside). FAIL',
    '   (`singleChangeOk: false`) if it bundles edits addressing more than one concern.',
    '3. Diff matches hypothesis: does the diff implement what the summary claims? FAIL',
    '   (`diffMatchesHypothesis: false`) on mismatch.',
    '4. Tests: re-run the tests the candidate claims to have run, and `python scripts/check_domain_imports.py`,',
    '   inside the worktree. FAIL (`testsReproduced: false`) if anything fails now.',
    '5. Scores: from the worktree\'s `local-server/`, run `python scripts/benchmark_replay.py --json`. It',
    '   must exit 0 with status "scored" (the committed cassettes answer every prompt of the committed',
    '   code), and its dev typed_f1 and f1 must equal the claimed ones to three decimals. FAIL',
    '   (`scoresReproduced: false`) otherwise.',
    '',
    'Return structured output only — no prose.',
  ].join('\n')
}

function decidePrompt(candidate, decision, reason, iteration, integrationBranch, incumbentVariant) {
  const ledgerEntry = {
    experiment_id: `${iteration}-${candidate.hypothesisId}`,
    iteration,
    hypothesis: candidate.hypothesisId,
    // `variant` names the pipeline configuration; `agent` the branch that did it.
    variant: `${incumbentVariant}+${candidate.hypothesisId}`,
    diff_stat: candidate.diffStat,
    base_commit: candidate.baseCommit,
    // Benchmark measures over the dev and holdout documents.
    dev: candidate.dev,
    holdout: candidate.holdout,
    // The triple corpus, kept so the record shows what the guard saw.
    guard: candidate.guard || null,
    decision,
    reason,
    cost_usd: candidate.recordingCostUsd || 0,
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
      `2. \`git checkout ${integrationBranch} && git merge --no-ff ${candidate.branchName}\`. The candidate's`,
      '   recorded cassettes come with the merge. Resolve only trivial conflicts; if the merge is not',
      '   trivial, stop and report the conflict instead of guessing.',
      '3. From `local-server/`, append the ledger entry via stdin. Do NOT paste the JSON into a',
      '   single-quoted shell argument — free-form text in `reason` can contain apostrophes, backticks,',
      '   or `$` that break shell quoting. Run this exactly, with the heredoc delimiter line unindented:',
      "   python experiments/ledger.py append --stdin <<'LEDGER_ENTRY_EOF'",
      ledgerEntryJson,
      '   LEDGER_ENTRY_EOF',
      '   Set `ledgerAppended: true` only if this command exits 0.',
      `4. \`git worktree remove ${candidate.worktreePath}\` (do NOT delete branch ${candidate.branchName} —`,
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

// §1 exit criterion: the holdout document's typed measures meet every floor.
function meetsFloors(holdout, floors) {
  return (
    holdout.typed_precision >= floors.precision
    && holdout.typed_recall >= floors.recall
    && holdout.typed_f1 >= floors.f1
  )
}

// documentation/karpathy_loop_design.md §4.3 step 2: rank the benchmark's
// failure kinds by count, map the top ones to backlog hypotheses, and skip
// anything the ledger already rejected, anything already accepted (it is
// merged into the incumbent — re-drafting it can only lose the accept gate),
// and anything marked `blocked` or `done` in SEED_BACKLOG.
function selectTargets(failureCounts, rejectedHypothesisIds, acceptedHypothesisIds, count) {
  const excludedIds = new Set([...rejectedHypothesisIds, ...acceptedHypothesisIds])
  const rankedKinds = Object.entries(failureCounts || {})
    .sort((a, b) => b[1] - a[1])
    .map(([kind]) => kind)

  const chosen = []
  const chosenIds = new Set()
  const eligible = (hyp) => !hyp.blocked && !hyp.done && !chosenIds.has(hyp.id) && !excludedIds.has(hyp.id)

  for (const kind of rankedKinds) {
    if (chosen.length >= count) break
    for (const hyp of SEED_BACKLOG) {
      if (chosen.length >= count) break
      if (!eligible(hyp) || !hyp.kinds.includes(kind)) continue
      chosen.push({ id: hyp.id, summary: hyp.summary, targetKind: kind })
      chosenIds.add(hyp.id)
    }
  }

  // Backfill with any remaining untried hypothesis (including kind-less ones)
  // if the ranked kinds did not fill the fleet.
  for (const hyp of SEED_BACKLOG) {
    if (chosen.length >= count) break
    if (!eligible(hyp)) continue
    chosen.push({ id: hyp.id, summary: hyp.summary, targetKind: hyp.kinds[0] || 'general' })
    chosenIds.add(hyp.id)
  }

  return chosen
}

// documentation/karpathy_loop_design.md §6 accept gate.
//
// Takes the benchmark's dev and holdout measures and the triple corpus's guard
// measure, and nothing else: no other diagnostic the tournament prints can be
// grounds for accepting or rejecting.
function acceptGate(candidate, incumbent, epsilon, holdoutSlack, coverageSlack, guardSlack) {
  const reasons = []

  // Improvement on dev: found F1 rewards coverage, typed F1 rewards exactness.
  //   - Coverage-driven: found F1 improves and typed F1 does not regress at all.
  //   - Exactness-driven: typed F1 improves and found F1 dips by at most
  //     coverageSlack (a bounded coverage trade in exchange for exactness).
  // The asymmetry is deliberate: for a curated graph a mistyped node is a
  // defect, a slightly less complete but correct graph is not.
  const foundDelta = candidate.dev.f1 - incumbent.dev.f1
  const typedDelta = candidate.dev.typed_f1 - incumbent.dev.typed_f1
  const foundImproves = foundDelta > epsilon
  const typedImproves = typedDelta > epsilon
  const coverageDriven = foundImproves && typedDelta >= 0
  const exactnessDriven = typedImproves && foundDelta >= -coverageSlack
  const improves = coverageDriven || exactnessDriven
  if (!improves) {
    if (!foundImproves && !typedImproves) {
      reasons.push(`neither dev found F1 ${candidate.dev.f1} nor dev typed F1 ${candidate.dev.typed_f1} beats the incumbent (found ${incumbent.dev.f1}, typed ${incumbent.dev.typed_f1}) by more than epsilon=${epsilon}`)
    } else if (foundImproves) {
      reasons.push(`dev found F1 improves but dev typed F1 ${candidate.dev.typed_f1} regresses below the incumbent's ${incumbent.dev.typed_f1}`)
    } else {
      reasons.push(`dev typed F1 improves but dev found F1 ${candidate.dev.f1} drops more than coverageSlack=${coverageSlack} below the incumbent's ${incumbent.dev.f1}`)
    }
  }

  // The holdout document never selects a winner; it only vetoes a change that
  // helps the dev documents at its expense. One document is a noisy veto: a
  // rejection on this ground alone deserves a human look before the
  // hypothesis is written off.
  const holdoutCollapsed = candidate.holdout.typed_f1 < incumbent.holdout.typed_f1 - holdoutSlack
  if (holdoutCollapsed) {
    reasons.push(`holdout typed F1 ${candidate.holdout.typed_f1} drops more than ${holdoutSlack} below the incumbent's ${incumbent.holdout.typed_f1}`)
  }

  // The triple corpus guards what the earlier loop won: typing and predicate
  // choice on short passages.
  const guardCollapsed = candidate.guard.strict_f1 < incumbent.guard.strict_f1 - guardSlack
  if (guardCollapsed) {
    reasons.push(`triple-corpus strict-F1 ${candidate.guard.strict_f1} drops more than ${guardSlack} below the incumbent's ${incumbent.guard.strict_f1}`)
  }

  return { passes: improves && !holdoutCollapsed && !guardCollapsed, reasons }
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
log(`Karpathy loop iteration ${iteration}: measuring the incumbent (Loop B + benchmark replay)`)
const evaluation = await agent(evaluatePrompt(), { schema: EVALUATION_SCHEMA, phase: 'Evaluate', label: 'evaluate:loopB' })
if (!evaluation) {
  return { status: 'error', reason: 'Evaluate step returned no result (agent skipped or failed)', iteration, consecutiveNoAccept }
}
// A stale or missing recording is not a low score. Nothing is selected,
// drafted or accepted against a measurement that did not happen.
if (evaluation.measurementStatus !== 'scored' || !evaluation.dev || !evaluation.holdout || !evaluation.guard) {
  return {
    status: 'error',
    reason: `the incumbent could not be measured (${evaluation.measurementStatus}): ${evaluation.measurementDetail || 'see the tournament digest'}. Record the cassettes on main (scripts/record_default_cassettes.py --record; scripts/benchmark_replay.py --record --spend) before running the loop`,
    iteration,
    consecutiveNoAccept,
    evaluation,
  }
}

// §4.3 step 6, other half: stop on success before spending anything else.
if (meetsFloors(evaluation.holdout, holdoutFloors)) {
  return {
    status: 'stopped',
    reason: 'holdout typed floors met (§1 exit criterion)',
    iteration,
    consecutiveNoAccept,
    evaluation,
  }
}

phase('Select')
const ledgerInfo = await agent(LEDGER_READ_PROMPT, { schema: LEDGER_SCHEMA, phase: 'Select', label: 'select:ledger', effort: 'low' })
const rejectedHypotheses = (ledgerInfo && ledgerInfo.rejectedHypotheses) || []
const acceptedHypotheses = (ledgerInfo && ledgerInfo.acceptedHypotheses) || []
const targets = selectTargets(evaluation.failureCounts, rejectedHypotheses, acceptedHypotheses, hypothesisCount)
log(`Selected ${targets.length} target hypothesis(es): ${targets.map((t) => t.id).join(', ') || '(none — the backlog is exhausted)'}`)

if (targets.length === 0) {
  return {
    status: 'no_accept',
    reason: 'no untried hypotheses remain in the seeded backlog (all already rejected or accepted) — read the benchmark report and add new hypotheses to SEED_BACKLOG',
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
// A candidate that could not be measured is not a candidate.
const candidates = experimentResults.filter((c) => c && c.measurementStatus === 'scored' && c.dev && c.holdout && c.guard)

if (candidates.length === 0) {
  return {
    status: 'no_accept',
    reason: 'no experimenter returned a measured candidate (agents failed, were skipped, or left stale cassettes)',
    iteration,
    consecutiveNoAccept: consecutiveNoAccept + 1,
    evaluation,
    targets,
    experimentResults,
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
  && p.verdict.scoresReproduced
  && p.verdict.singleChangeOk
  && p.verdict.diffMatchesHypothesis
  && (p.verdict.forbiddenPathHits || []).length === 0
)

let best = null
for (const p of verified) {
  if (!best || p.candidate.dev.typed_f1 > best.candidate.dev.typed_f1) best = p
}

const gateResult = best
  ? acceptGate(best.candidate, evaluation, EPSILON, HOLDOUT_SLACK, COVERAGE_SLACK, GUARD_SLACK)
  : null
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
const iterationCostUsd = candidates.reduce((sum, c) => sum + (c.recordingCostUsd || 0), 0)

return {
  status: accepted ? 'accepted' : 'no_accept',
  iteration,
  consecutiveNoAccept: nextConsecutiveNoAccept,
  cumulativeCostUsd: cumulativeCostUsd + iterationCostUsd,
  incumbentVariant: evaluation.incumbentVariant,
  acceptedHypothesis: accepted ? best.candidate.hypothesisId : null,
  evaluation,
  targets,
  candidates: paired,
  decisions,
  outcomes,
  stop: nextConsecutiveNoAccept >= maxConsecutiveNoAccept
    ? { reason: `plateau reached after this iteration (${nextConsecutiveNoAccept} consecutive no-accept)` }
    : null,
}
