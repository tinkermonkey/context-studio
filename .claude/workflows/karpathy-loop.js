export const meta = {
  name: 'karpathy-loop',
  description: 'Run one Loop C iteration for individual-extraction refinement: evaluate one implementation (with one of its configurations) on the benchmark documents, select failure targets, fan out experimenter agents, verify, accept/reject, update the ledger.',
  whenToUse: 'Invoke to run exactly ONE Karpathy-loop iteration (documentation/karpathy_loop_design.md §4.3) for one implementation of the local-server individual-extraction pipeline. What is refined is chosen like any run: `args.implementation` and `args.configuration`, each defaulting through the pipeline registry (the type\'s default implementation; the configuration its benchmark recordings were made with, else its default), so pass `{implementation: "find_then_type"}` to refine that one. An implementation needs a backlog and gate margins in this script (`BACKLOGS`, `GATE_MARGINS`): `default` and `find_then_type` have them, and `find_then_type`\'s margins are provisional (see `GATE_MARGINS`). The objective is the extraction benchmark (long documents scored on the individuals found, tests/integration/fixtures/pipelines/extraction_benchmark/); the short-passage triple corpus is a regression guard for an implementation it has recordings of (`default`) and not applicable to any other. Each call is one iteration; drive repeated iterations from outside this script (e.g. via /loop) and thread state across calls through `args`: {implementation, configuration, iteration, consecutiveNoAccept, hypothesisCount, integrationBranch, holdoutFloors, maxConsecutiveNoAccept, cumulativeCostUsd, totalBudgetUsd}. Read the returned `stop` field (and `status`) after every call: "stopped" means a floor/plateau/budget stop-check tripped and the outer loop should halt; "error" means the evaluation could not be trusted (stale or unrecorded cassettes) and a human must record them; "accepted" always comes with a `stop`, because the accepted change sits on the integration branch while the incumbent is measured on `main`: promote that branch to `main` (by PR) before the next call. Halt whenever `stop` is not null. Otherwise pass the returned `consecutiveNoAccept`, `cumulativeCostUsd` and incremented `iteration` into the next call’s args. Do not invoke casually: one iteration runs the variant tournament plus several worktree-isolated coding agents, and every experiment that changes a prompt re-records cassettes with the live LLM.',
  phases: [
    { title: 'Evaluate', detail: 'Run Loop B (variant tournament + benchmark replay of the chosen implementation and configuration); read the incumbent scores and failure counts' },
    { title: 'Select', detail: 'Rank benchmark failure kinds by count; drop hypotheses the ledger already decided' },
    { title: 'Experiment', detail: 'Fan out one worktree-isolated agent per hypothesis' },
    { title: 'Verify', detail: 'Adversarial gate-integrity check per candidate' },
    { title: 'Decide', detail: 'Accept gate on every verified candidate; merge the best that passes, discard the rest, append the ledger' },
  ],
}

// documentation/karpathy_loop_design.md §6 accept gate margins, one set per
// implementation.
//
// The gate reads two benchmark measures over the dev documents:
//   - `f1`: found F1. Did the run find the gold individuals, whatever type it
//     gave them? The coverage signal.
//   - `typed_f1`: found and given the gold type or an acceptable one. The
//     exactness signal, and the headline number.
// A candidate earns acceptance by improving either without materially damaging
// the other, and must not collapse the holdout document or (where it applies)
// the triple corpus.
//   - epsilon: the gain on a dev measure that counts as an improvement.
//   - holdoutSlack: how far the holdout document's typed F1 may drop.
//   - coverageSlack: when acceptance is exactness-driven (typed F1 improves),
//     how far found F1 may dip: a bounded coverage trade for exactness.
//   - guardSlack: how far the short-passage triple corpus (dev strict-F1) may
//     drop. Read only when the guard applies to the implementation.
// epsilon and holdoutSlack have to sit above what recording the SAME
// implementation again moves the score: every experiment that changes a prompt
// re-records, so a smaller gain is not distinguishable from a second take.
// That spread is a property of the implementation and its model, so the
// margins are too. An implementation with no entry here cannot be refined: the
// iteration stops rather than borrow another implementation's margins.
const GATE_MARGINS = {
  default: {
    epsilon: 0.02,
    holdoutSlack: 0.04,
    coverageSlack: 0.05,
    guardSlack: 0.02,
    provisional: false,
    basis: 'three recordings of the unchanged implementation (2026-11-12, google/gemini-3-flash-preview, temperature 0): dev found F1 ranged over 0.006, dev typed F1 over 0.009, the holdout document\'s typed F1 over 0.028',
  },
  // PROVISIONAL. Set from typing noise alone: on 2026-11-14 the same 570
  // mentions were typed again with the unchanged prompt (find answers held
  // fixed, one take). 16.5% of the answers changed; dev typed F1 came out
  // 0.476 against the committed 0.465 (0.011 apart) and the holdout document's
  // 0.442 against 0.481 (0.039 apart). The margins are those spreads scaled as
  // `default`'s were (about 2.2x on dev, 1.4x on holdout) and rounded up,
  // because two takes understate a range and the find and relate stages add
  // noise that was not measured. Replace them, and set `provisional` to false,
  // once the measurement named in `missing` has been made.
  find_then_type: {
    epsilon: 0.03,
    holdoutSlack: 0.06,
    coverageSlack: 0.05,
    // The triple corpus has no recordings of this implementation.
    guardSlack: null,
    provisional: true,
    basis: 'typing noise only (2026-11-14, claude-haiku-5-5, find answers held fixed, two takes): dev typed F1 0.465 vs 0.476, the holdout document\'s typed F1 0.481 vs 0.442, 16.5% of typing answers changed',
    missing: 'full re-recording noise: three recordings of the unchanged implementation, every stage (find, type, relate), as was done for `default`; the spread of dev found F1, dev typed F1 and holdout typed F1 over them',
  },
}
// §1 exit criterion: floors on the holdout document's typed measures.
const DEFAULT_HOLDOUT_FLOORS = { precision: 0.6, recall: 0.5, f1: 0.5 }
const DEFAULT_INTEGRATION_BRANCH = 'experiment/karpathy-loop'
const DEFAULT_MAX_CONSECUTIVE_NO_ACCEPT = 3
const DEFAULT_HYPOTHESIS_COUNT = 3
const MIN_HYPOTHESIS_COUNT = 2
const MAX_HYPOTHESIS_COUNT = 4
// An implementation or configuration name goes into shell commands in the
// agents' prompts, so only the characters registry names are made of are let in.
const TARGET_NAME = /^[A-Za-z0-9][A-Za-z0-9_.+-]*$/

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

// Seeded hypothesis backlogs (documentation/karpathy_loop_design.md §7), one
// per implementation: a hypothesis is a change to one implementation's shape,
// and what one lacks another may do by design. `kinds` maps a hypothesis to
// the benchmark failure kinds it is expected to move; an empty list means it
// targets something the failure counts do not show and is only picked as a
// last-resort filler.
// `blocked: true` keeps a hypothesis out of selection: the accept gate reads
// only the individuals' found F1 and typed F1, so a change that moves only
// relationships or confidences cannot pass it however well it works. Unblock
// one when the gate reads a measure it can move.
// The ledger scopes hypothesis ids by implementation, so the same id in two
// backlogs is two hypotheses.
//
// `default` (the two-pass shape: domain/extraction/services.py,
// domain/pipelines/individual_extraction/orchestrator.py). Hypotheses from the
// earlier triple-corpus era (two-pass extraction, class catalog grounding,
// concept objects, label canonicalization: landed; noun-chunk surfacing and
// retrieval-based typing: rejected) are recorded in §7 of the design doc and
// are not repeated here.
const DEFAULT_BACKLOG = [
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
    blocked: true,
    summary:
      'Derive relationships across chunks. The derive stage sees only the individuals identified in its own chunk, so a relationship between individuals introduced in different sections is never stated. After merging, run the derive stage once more over the merged individuals with the passages that mention two of them.',
  },
  {
    id: 'per_source_confidence_bands',
    kinds: [],
    blocked: true,
    summary:
      'Per-source confidence bands (calibrated ranges per extraction source) so apply-time thresholding means something. Not visible in the failure counts.',
  },
]

// `find_then_type` (domain/extraction/find_then_type.py,
// domain/pipelines/individual_extraction/find_then_type.py). It already offers
// the whole class catalog, finds statements as individuals and gives an
// individual one class, so none of those is here. Written from the committed
// recording's dev failure counts (18 core and 67 supporting individuals missed,
// 15 mistyped, 93 spurious, 109 relationships missed) and from scratch runs on
// 2026-11-14 that held the find answers fixed and varied only typing. Tried
// there and not repeated here:
//   - whole class definitions in the catalog instead of their first 260
//     characters (`_DEFINITION_CHARS`): no gain (dev typed F1 0.446);
//   - loosening the typing prompt's "none" rule by wording alone: 13 more
//     right, 24 more wrong, 78 more mentions recorded that gold does not hold
//     (dev typed F1 0.41).
const FIND_THEN_TYPE_BACKLOG = [
  {
    // Typing answers "none" for about a quarter of the mentions whose name
    // matches a gold individual (45 of 180), the same ones from take to take.
    // The model's stated reasons are that the mention is "only a heading or
    // table label here" or "only cited in passing": it judges the one passage
    // it is shown.
    id: 'type_from_all_occurrences',
    kinds: ['missed_supporting', 'missed_core', 'mistyped'],
    summary:
      'Type a mention from every place it was found, not only the first. `_Candidate.typed_in` (domain/pipelines/individual_extraction/find_then_type.py) picks one occurrence, the first with a placed passage, and the typing call sees that passage and the text around it; a thing introduced in a heading or a table and described three sections later is typed from the heading and answered "none". The candidate already holds every occurrence (`_Candidate.found`): give the typing call the passages of all of them (each with a shorter window, within the same prompt size), so "what the text says of it" is everything the source says of it.',
  },
  {
    id: 'structure_in_typing_context',
    kinds: ['missed_supporting', 'missed_core'],
    summary:
      'Show the typing call where its passage sits. The find stage is told to include what is named only once in a table, a list or a diagram; the typing stage sees 1,200 characters each side of the passage (`CONTEXT_WINDOW_CHARS`, domain/extraction/find_then_type.py) with no heading path and, for a table row, often without the table\u2019s header row, and is told to answer "none" for "a repeat of a heading". So an element whose only passage is a table row or a heading is found and then dropped. Add the passage\u2019s heading path and, when it is in a table, the header row, to the typing context. Changing the wording of the "none" rule alone has been tried and lost; this changes what the call is shown.',
  },
  {
    // 93 predictions on the dev documents match nothing in gold: the largest
    // count that is not relationships, and precision (0.52) is now below recall.
    id: 'scope_question_at_typing',
    kinds: ['spurious', 'excluded_extracted'],
    summary:
      'Decide scope separately from class. The typing call answers one question, "which class, or none", so whether a mention belongs in the model at all is settled as a side effect of whether some class fits, and most things fit some class. Ask first whether the candidate is part of what the document describes or its immediate context (its users, the organisations and the external systems it works with), as opposed to prior art, tools named for comparison, example values and people; type only what passes. State the rule in general terms: nothing specific to a document.',
  },
  {
    // Typing the same mentions twice with the same prompt changed 16.5% of the
    // answers. A wrong class and a wrongly dropped mention both come out of it,
    // and it is why this implementation's gate margins are wide.
    id: 'typing_majority_vote',
    kinds: ['mistyped', 'spurious'],
    summary:
      'Type each mention three times and keep the answer two calls agree on (no agreement: the answer with the highest confidence). The model takes no temperature, and a repeat of the same typing call changes about one answer in six; the catalog is a cached system prompt, so two more calls per mention cost little input. This triples the typing calls of a recording (about 570 to 1,700 for the benchmark): say what the recording cost.',
  },
  {
    // Measured with claude-haiku-5-5: the relate stage's answer was cut at its
    // 8,000 output-token limit on the GitLab document in two of four takes (a
    // failed chunk, so the run is not scored), and relationship recall on the
    // Edit check document came out between 0.00 and 0.09 from take to take.
    id: 'relate_within_output_limit',
    kinds: ['relationship_missed'],
    blocked: true,
    summary:
      'Keep the relate stage inside its output limit. It is asked for every relationship among all of a chunk\u2019s typed individuals in one answer capped at 8,000 output tokens (`max_tokens` in domain/extraction/services.py); find-then-type types far more individuals per chunk than the two-pass shape, so the answer is cut on dense chunks. Ask for the relationships of a bounded number of subjects per call. The relate stage is shared with the `default` implementation (`derive_relationships` in domain/extraction/prompts.py): a change to it makes both implementations\u2019 recordings stale.',
  },
  {
    id: 'cross_chunk_relationships',
    kinds: ['relationship_missed'],
    blocked: true,
    summary:
      'Derive relationships across chunks. The relate stage sees only the individuals typed in its own chunk, so a relationship between individuals introduced in different sections is never stated. After merging, run the relate stage once more over the merged individuals with the passages that mention two of them. The relate stage is shared with the `default` implementation.',
  },
]

const BACKLOGS = {
  default: DEFAULT_BACKLOG,
  find_then_type: FIND_THEN_TYPE_BACKLOG,
}

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

// The triple corpus (short SME passages), the regression guard, as the
// tournament's benchmark report states it for the target (its `guard` object).
// `applies` is false for an implementation the triple corpus has no recordings
// of, with the `reason`; the gate then reads no guard number, and the ledger
// entry records that it did not apply. When it applies, `strict_f1` over the
// corpus's dev scenarios is the one number the accept gate reads from it.
const GUARD_METRICS = {
  type: 'object',
  required: ['applies'],
  properties: {
    applies: { type: 'boolean' },
    reason: { type: 'string' },
    variant: { type: 'string' },
    strict_f1: { type: 'number' },
    soft_f1: { type: 'number' },
  },
}

const EVALUATION_SCHEMA = {
  type: 'object',
  required: ['implementation', 'configuration', 'model', 'measurementStatus', 'errorReportPath', 'scoreboardPath'],
  properties: {
    // What was measured, as the benchmark report states it: the registry's
    // defaults when `args` named none.
    implementation: { type: 'string' },
    configuration: { type: 'string' },
    model: { type: 'string' },
    // "scored" only when the tournament exited 0 and the benchmark summary's
    // status is "scored". Anything else stops the iteration before it spends.
    measurementStatus: { type: 'string', enum: ['scored', 'stale', 'not_recorded', 'failed'] },
    measurementDetail: { type: 'string' },
    // Recordings the target does not read that were already stale on `main`
    // (variant names). A candidate may add nothing to this list.
    staleElsewhere: { type: 'array', items: { type: 'string' } },
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
    'changesPrompts', 'cassettesRecorded', 'testsPassed', 'measurementStatus',
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
    // `dev`, `holdout` and `guard` are present exactly when this is "scored".
    measurementStatus: { type: 'string', enum: ['scored', 'stale', 'not_recorded', 'failed'] },
    measurementDetail: { type: 'string' },
    staleElsewhere: { type: 'array', items: { type: 'string' } },
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
    // Every other recorded benchmark target, replayed in the candidate's
    // worktree: a change to a part the implementations share shows here.
    otherTargets: {
      type: 'array',
      items: {
        type: 'object',
        required: ['implementation', 'configuration', 'status'],
        properties: {
          implementation: { type: 'string' },
          configuration: { type: 'string' },
          status: { type: 'string' },
          devTypedF1: { type: 'number' },
          devFoundF1: { type: 'number' },
        },
      },
    },
    verdict: { type: 'string', enum: ['pass', 'fail'] },
    reason: { type: 'string' },
  },
}

const DECIDE_SCHEMA = {
  type: 'object',
  required: ['hypothesisId', 'decision', 'ledgerAppended'],
  properties: {
    hypothesisId: { type: 'string' },
    decision: { type: 'string', enum: ['accepted', 'rejected', 'deferred', 'unmeasured'] },
    merged: { type: 'boolean' },
    worktreeDiscarded: { type: 'boolean' },
    ledgerAppended: { type: 'boolean' },
    notes: { type: 'string' },
  },
}

// The command-line flags that choose a target. Either part may be absent
// before the incumbent is measured: the scripts then resolve it through the
// pipeline registry, and the benchmark report says what they resolved it to.
function targetFlags(target) {
  return [
    target.implementation ? `--implementation ${target.implementation}` : '',
    target.configuration ? `--configuration ${target.configuration}` : '',
  ].filter(Boolean).join(' ')
}

function tournamentCommand(target) {
  return ['python scripts/quality_tournament.py --pipeline individual --passes 1 --restarts 1', targetFlags(target)].filter(Boolean).join(' ')
}

function benchmarkRecordCommand(target) {
  return ['python scripts/benchmark_replay.py --record --spend', targetFlags(target)].filter(Boolean).join(' ')
}

// The triple corpus's recordings are of the `default` implementation's
// variants, whichever implementation is being refined.
const TRIPLE_CORPUS_RECORD_COMMAND = 'python scripts/record_default_cassettes.py --record'

function describeStale(names) {
  return names && names.length > 0 ? names.join(', ') : 'nothing'
}

function describeGuard(guard) {
  if (guard && guard.applies === false) return 'triple-corpus guard not applicable'
  return `triple-corpus guard strict-F1 ${guard && guard.strict_f1}`
}

// Hypothesis ids are scoped by implementation in the ledger: a rejection under
// one implementation says nothing about the same id under another.
function ledgerReadPrompt(implementation) {
  return [
    'From `local-server/`, with its virtual environment active, read the loop ledger\'s hypothesis history',
    `for the \`${implementation}\` implementation:`,
    `1. \`python experiments/ledger.py rejected-hypotheses --implementation ${implementation}\` — return every`,
    '   printed line (one hypothesis id per line; empty output means no rejections yet) as',
    '   `rejectedHypotheses`.',
    `2. \`python experiments/ledger.py accepted-hypotheses --implementation ${implementation}\` — return every`,
    '   printed line as `acceptedHypotheses` (empty output means no acceptances yet). These are already',
    '   merged into the incumbent, so selection skips them: re-drafting a merged hypothesis can only lose',
    '   the accept gate.',
    'Both commands list only this implementation\'s entries since the last baseline reset that applies to it.',
    'Return structured output only — no prose.',
  ].join('\n')
}

// How to read one tournament run. Shared by the evaluate and experiment prompts
// so the incumbent and every candidate are measured by the same steps.
function measureSteps(target) {
  return [
    `a. \`${tournamentCommand(target)}\`. Note its exit`,
    '   code. It replays recorded LLM responses only; it never calls an LLM.',
    '   - Exit 3: a recording this target reads (its benchmark cassettes, or a triple-corpus variant',
    '     that runs its implementation) no longer answers the pipeline\'s prompts. `measurementStatus`',
    '     is "stale".',
    '   - Any other non-zero exit: `measurementStatus` is "failed"; put the error in the detail field.',
    '   - Exit 0 with a "STALE CASSETTES" section at the top of the digest: the stale recordings are ones',
    '     this target does not read (a variant that runs another implementation). They do not make the',
    '     target\'s numbers wrong; list what the section names (each variant name, or "benchmark") in',
    '     `staleElsewhere`, and give an empty list when there is no such section.',
    'b. Find the newest `experiments/reports/tournament_<run_id>.md` digest (`scoreboardPath`) and the',
    '   `experiments/reports/tournament_<run_id>_benchmark.json` beside it (`errorReportPath`).',
    'c. Read the benchmark JSON. Its `implementation`, `configuration` and `model` say what was run. Its',
    '   `status` must be "scored"; "not_recorded" or "stale" becomes the `measurementStatus` (the',
    '   benchmark cassettes of that implementation and configuration are missing or out of date), and',
    '   any other status ("partial": a benchmark document is missing) is "failed". When scored: `dev` and',
    '   `holdout` are its `dev` and `holdout` objects (typed_f1, typed_precision, typed_recall, f1,',
    '   precision, recall, recall_core, type_accuracy, relationship_recall), and the failure counts are',
    '   its `failure_counts`. Each document\'s `missed`, `mistyped`, `spurious` and `excluded_hits` lists',
    '   under `scores` are the concrete examples.',
    'd. `guard` is the benchmark JSON\'s `guard` object (the short-passage triple corpus, for the',
    '   implementation that was run). Copy `applies` as it is. When `applies` is false, copy `reason`',
    '   and nothing else: the guard does not apply to this implementation, and no row of the scoreboard',
    '   stands in for it. When `applies` is true, its `status` must be "scored" (then copy `variant`,',
    '   `strict_f1` and `soft_f1`); "stale" becomes the `measurementStatus`, and any other status is',
    '   "failed".',
  ]
}

// `requested` is what `args` named, either part possibly null: the scripts
// resolve what is missing through the pipeline registry.
function evaluatePrompt(requested) {
  const named = requested.implementation
    ? `the \`${requested.implementation}\` implementation${requested.configuration ? ` with its \`${requested.configuration}\` configuration` : ' with the configuration its benchmark recordings were made with'}`
    : 'the pipeline registry\'s default implementation of individual extraction, with the configuration its benchmark recordings were made with'
  return [
    'Measure the incumbent individual-extraction pipeline (documentation/karpathy_loop_design.md §4.3 step 1).',
    `The incumbent is ${named}, on \`main\`. Change nothing; this step only reads.`,
    '',
    'Steps (from `local-server/`, virtual environment active):',
    ...measureSteps(requested),
    'e. Set `implementation`, `configuration` and `model` to the benchmark JSON\'s fields of those names:',
    '   what the run resolved the target to. If the benchmark JSON was not written, give what the',
    '   tournament printed on its "== benchmark:" line, or empty strings. If `measurementStatus` is not',
    '   "scored", still return those three, `measurementStatus`, `measurementDetail` (what is stale or',
    '   missing, and the recording command the digest names) and the two paths; leave the metrics out.',
    '',
    'Return structured output only — no prose.',
  ].join('\n')
}

function experimentPrompt(hypothesis, evaluation) {
  const target = { implementation: evaluation.implementation, configuration: evaluation.configuration }
  return [
    `You are one of several parallel experimenter agents refining the \`${evaluation.implementation}\``,
    `implementation of individual extraction, run with its \`${evaluation.configuration}\` configuration`,
    `(model ${evaluation.model}) (Karpathy loop, documentation/karpathy_loop_design.md §4.3 step 3).`,
    'Implement EXACTLY ONE change — the hypothesis below — and nothing else. Note any unrelated issue you',
    'notice in your summary instead of fixing it.',
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
    `${evaluation.holdout.typed_f1}, ${describeGuard(evaluation.guard)}.`,
    '',
    'Hard rules — breaking any of these gets the candidate rejected on verification whatever it scores',
    '(documentation/karpathy_loop_design.md §6):',
    '- Exactly one change. No bundled unrelated edits.',
    `- The change is to the \`${evaluation.implementation}\` implementation. Do not change which implementation,`,
    '  configuration or model the benchmark runs; a change to a part other implementations share (the',
    '  relationship stage, chunking, merging, planning) is allowed, and step 4 says what it then owes.',
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
    '   list, how text is chunked), recorded responses no longer apply. Find out which, offline:',
    '     `python scripts/benchmark_replay.py --all` replays every recorded benchmark target and prints',
    '     each one\'s `target:` line and status;',
    `     \`${tournamentCommand(target)}\` lists stale triple-corpus variants in a`,
    '     "STALE CASSETTES" section at the top of its digest.',
    `   Already stale on \`main\`, before your change, and not yours to record: ${describeStale(evaluation.staleElsewhere)}.`,
    '   Record again, with the live LLM, every other set that is stale (this costs money; each recording',
    '   uses the model of its target\'s configuration):',
    `     \`${benchmarkRecordCommand(target)}\` for this target;`,
    '     the same command with another target\'s `--implementation` and `--configuration` (from its',
    '     `target:` line) for each other benchmark target that went stale: the change touched a part the',
    '     implementations share, and a recording left stale fails verification;',
    `     \`${TRIPLE_CORPUS_RECORD_COMMAND}\` when the digest lists a \`default\` variant as stale.`,
    '   Set `changesPrompts` and `cassettesRecorded`, and estimate `recordingCostUsd` from the token',
    '   counts in the cassettes. Never edit a cassette file by hand, and never delete one: a stale',
    '   recording is recorded again.',
    '5. Commit to this worktree branch: `git add -A && git commit -m "<hypothesis-id>: <what changed>"`.',
    '   Required: the verifier and the merge step read `git diff main...HEAD`, which shows only committed',
    '   changes.',
    '6. Run the tests for what you touched (the unit tests of the modules you changed, and',
    '   `python scripts/check_domain_imports.py`); set `testsPassed` and `testsSummary`.',
    '7. Measure the candidate exactly as the incumbent was measured:',
    ...measureSteps(target),
    '   Report `measurementStatus`, `dev`, `holdout` and `guard`. A status other than "scored" means step 4',
    '   was needed and skipped, or failed: fix that rather than reporting numbers. If it still cannot be',
    '   scored, report the status and say why in `measurementDetail`, and leave `dev`, `holdout` and',
    '   `guard` out: never report a number the steps above did not produce.',
    '8. In `failureCountsDelta`, compare the candidate\'s failure counts with the incumbent\'s for your',
    '   target kind and say which concrete examples moved.',
    '9. Capture, from inside the worktree after committing: `git diff main...HEAD --stat` (diffStat),',
    '   `git diff main...HEAD --name-only` (changedFiles), `git rev-parse --show-toplevel` (worktreePath),',
    '   `git branch --show-current` (branchName), `git merge-base HEAD main` (baseCommit).',
    '',
    'Return structured output only — no prose.',
  ].join('\n')
}

// `staleOnMain` is the incumbent measurement's `staleElsewhere`: what was stale
// before the candidate changed anything.
function verifyPrompt(candidate, target, staleOnMain) {
  const guardApplies = !(candidate.guard && candidate.guard.applies === false)
  const claimedGuard = guardApplies
    ? `guard strict-F1 ${candidate.guard.strict_f1}, guard soft-F1 ${candidate.guard.soft_f1}`
    : 'guard not applicable'
  return [
    'You are the adversarial verifier for one Karpathy-loop experiment candidate',
    '(documentation/karpathy_loop_design.md §4.3 step 4 / §6). Fail the candidate if anything is ambiguous.',
    '',
    `Candidate hypothesis id: ${candidate.hypothesisId}`,
    `Refining: the \`${target.implementation}\` implementation with its \`${target.configuration}\` configuration`,
    `Candidate summary: ${candidate.summary}`,
    `Worktree: ${candidate.worktreePath} (branch ${candidate.branchName}, base ${candidate.baseCommit})`,
    `Claimed changed files: ${JSON.stringify(candidate.changedFiles)}`,
    `Claimed diff stat: ${candidate.diffStat}`,
    `Claimed tests passed: ${candidate.testsPassed}`,
    `Claimed scores: dev typed F1 ${candidate.dev.typed_f1}, dev found F1 ${candidate.dev.f1}, holdout typed F1 ${candidate.holdout.typed_f1}, ${claimedGuard}`,
    '',
    'Checks — ALL must pass for verdict "pass":',
    '1. Integrity: `cd` into the worktree and run `git diff main...HEAD --name-only`. FAIL',
    '   (`integrityOk: false`, list every offender in `forbiddenPathHits`) if any changed path starts with,',
    '   or equals, one of:',
    ...FROZEN_PATHS.map((p) => `     ${p}`),
    '   Also FAIL integrity if a prompt or code change names a benchmark document or quotes its text.',
    '   Also FAIL integrity (list the paths in `forbiddenPathHits`) if',
    '   `git diff main...HEAD --diff-filter=D --name-only` lists any file under',
    '   `local-server/tests/integration/fixtures/cassettes/`: a recording is recorded again, never',
    '   deleted, and a deleted one is not replayed by any check below.',
    '2. Single change: read the diff (`git diff main...HEAD`, leaving the cassette JSON aside). FAIL',
    '   (`singleChangeOk: false`) if it bundles edits addressing more than one concern.',
    '3. Diff matches hypothesis: does the diff implement what the summary claims? FAIL',
    '   (`diffMatchesHypothesis: false`) on mismatch.',
    '4. Tests: re-run the tests the candidate claims to have run, and `python scripts/check_domain_imports.py`,',
    '   inside the worktree. FAIL (`testsReproduced: false`) if anything fails now.',
    '5. Scores: from the worktree\'s `local-server/`, run `python scripts/benchmark_replay.py --all --json`.',
    '   It replays every benchmark target that has recordings, not only this one, and must exit 0: every',
    '   entry of its `targets` list must have status "scored" (the committed cassettes answer every prompt',
    '   of the committed code). A change to a part the implementations share (the relationship stage,',
    '   chunking, merging, planning) makes another implementation\'s recordings stale; a candidate that',
    '   left one stale FAILS. The entry whose `implementation` is',
    `   "${target.implementation}" and \`configuration\` is "${target.configuration}" must show the claimed dev`,
    '   typed_f1, dev f1 and holdout typed_f1 to three decimals. Report every other entry in',
    '   `otherTargets` (implementation, configuration, status, and its dev typed_f1 and dev f1 as',
    '   `devTypedF1` and `devFoundF1`): they are recorded with the decision.',
    `   Then run \`${tournamentCommand(target)}\``,
    '   (it replays recordings only): it must exit 0, a "STALE CASSETTES" section in the newest',
    '   `experiments/reports/tournament_<run_id>.md` digest may name nothing but what was already stale',
    `   on \`main\` (${describeStale(staleOnMain)}), and the \`guard\` object of the`,
    '   `tournament_<run_id>_benchmark.json` beside it must',
    guardApplies
      ? '   have `applies` true, status "scored" and the claimed guard strict-F1 as its `strict_f1`.'
      : '   have `applies` false: the guard does not apply to this implementation, and a number claimed for it is a FAIL.',
    '   FAIL (`scoresReproduced: false`) if any of these differs: the accept gate reads every one of them.',
    '',
    'Return structured output only — no prose.',
  ].join('\n')
}

// `target` is what the iteration refined ({implementation, configuration,
// model}); `margins` the gate margins it was judged by; `otherTargets` what the
// verifier saw of every other recorded benchmark target.
function decidePrompt(candidate, decision, reason, iteration, integrationBranch, target, margins, otherTargets) {
  const ledgerEntry = {
    // Hypothesis ids are scoped by implementation, so the id names it.
    experiment_id: `${iteration}-${target.implementation}-${candidate.hypothesisId}`,
    iteration,
    // What was refined and measured.
    implementation: target.implementation,
    configuration: target.configuration,
    model: target.model,
    hypothesis: candidate.hypothesisId,
    // `variant` names the change; `agent` the branch that did it.
    variant: `${target.implementation}+${candidate.hypothesisId}`,
    diff_stat: candidate.diffStat,
    base_commit: candidate.baseCommit,
    // Benchmark measures over the dev and holdout documents.
    // null for a candidate that could not be measured.
    dev: candidate.dev || null,
    holdout: candidate.holdout || null,
    // The triple corpus, kept so the record shows what the guard saw:
    // `{applies: false, reason}` when it does not apply to the implementation.
    guard: candidate.guard || null,
    // The margins the gate used, and whether they are provisional.
    margins: margins
      ? { epsilon: margins.epsilon, holdout_slack: margins.holdoutSlack, coverage_slack: margins.coverageSlack, guard_slack: margins.guardSlack, provisional: Boolean(margins.provisional) }
      : null,
    // Every other recorded benchmark target, as replayed on the candidate's branch.
    other_targets: otherTargets || [],
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
      '2. Merge in a temporary worktree, never by checking the branch out in the repository root (the',
      '   root stays on the branch it is on: the incumbent is measured there, and the ledger file below',
      '   is an uncommitted change in it):',
      `   \`git worktree add <a new temporary directory> ${integrationBranch}\`, then inside it`,
      `   \`git merge --no-ff ${candidate.branchName}\`, then \`git worktree remove\` it. The candidate's`,
      '   recorded cassettes come with the merge. Resolve only trivial conflicts; if the merge is not',
      '   trivial, `git merge --abort`, remove the temporary worktree, set `merged: false` and report the',
      '   conflict instead of guessing.',
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
  } else if (decision === 'deferred') {
    // Passed the gate but another candidate was accepted. No ledger entry: a
    // "rejected" entry would keep a hypothesis that passed from being drafted
    // again against the new incumbent.
    lines.push(
      '1. Do NOT append a ledger entry; set `ledgerAppended: false`.',
      `2. \`git worktree remove --force ${candidate.worktreePath}\`.`,
      `3. \`git branch -D ${candidate.branchName}\`.`,
    )
  } else {
    // "rejected" and "unmeasured" both leave a ledger entry and no worktree.
    // Only a "rejected" entry keeps the hypothesis from being selected again.
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
// and anything marked `blocked` or `done`. `backlog` is the implementation's
// own (BACKLOGS), and the two id lists are that implementation's ledger history.
function selectTargets(failureCounts, rejectedHypothesisIds, acceptedHypothesisIds, count, backlog) {
  const excludedIds = new Set([...rejectedHypothesisIds, ...acceptedHypothesisIds])
  const rankedKinds = Object.entries(failureCounts || {})
    .sort((a, b) => b[1] - a[1])
    .map(([kind]) => kind)

  const chosen = []
  const chosenIds = new Set()
  const eligible = (hyp) => !hyp.blocked && !hyp.done && !chosenIds.has(hyp.id) && !excludedIds.has(hyp.id)

  for (const kind of rankedKinds) {
    if (chosen.length >= count) break
    for (const hyp of backlog) {
      if (chosen.length >= count) break
      if (!eligible(hyp) || !hyp.kinds.includes(kind)) continue
      chosen.push({ id: hyp.id, summary: hyp.summary, targetKind: kind })
      chosenIds.add(hyp.id)
    }
  }

  // Backfill with any remaining untried hypothesis (including kind-less ones)
  // if the ranked kinds did not fill the fleet.
  for (const hyp of backlog) {
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
// grounds for accepting or rejecting. `margins` is the implementation's entry
// of GATE_MARGINS.
//
// The guard applies unless the incumbent's measurement says it does not
// (`guard.applies === false`: the triple corpus has no recordings of the
// implementation). Then no guard number is read, on either side; the candidate
// must have been measured the same way.
function acceptGate(candidate, incumbent, margins) {
  const { epsilon, holdoutSlack, coverageSlack, guardSlack } = margins || {}
  const reasons = []
  const guardApplies = !(incumbent && incumbent.guard && incumbent.guard.applies === false)

  const unset = [['epsilon', epsilon], ['holdoutSlack', holdoutSlack], ['coverageSlack', coverageSlack]]
    .concat(guardApplies ? [['guardSlack', guardSlack]] : [])
    .filter(([, value]) => !Number.isFinite(value))
    .map(([name]) => name)
  if (unset.length > 0) {
    return { passes: false, reasons: [`no gate margin for: ${unset.join(', ')}`] }
  }

  // A missing number is not a pass: every comparison below is false against
  // undefined, which would read as "did not collapse".
  const read = [['dev', 'f1'], ['dev', 'typed_f1'], ['holdout', 'typed_f1']].concat(guardApplies ? [['guard', 'strict_f1']] : [])
  const missing = []
  for (const [name, run] of [['candidate', candidate], ['incumbent', incumbent]]) {
    for (const [group, key] of read) {
      if (!Number.isFinite(run && run[group] && run[group][key])) missing.push(`${name} ${group}.${key}`)
    }
  }
  if (missing.length > 0) {
    return { passes: false, reasons: [`not measured: ${missing.join(', ')}`] }
  }
  if (!guardApplies && !(candidate.guard && candidate.guard.applies === false)) {
    return { passes: false, reasons: ['the triple-corpus guard does not apply to the incumbent but the candidate reports one: they were not measured the same way'] }
  }

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
  // choice on short passages, by the implementation it has recordings of.
  const guardCollapsed = guardApplies && candidate.guard.strict_f1 < incumbent.guard.strict_f1 - guardSlack
  if (guardCollapsed) {
    reasons.push(`triple-corpus strict-F1 ${candidate.guard.strict_f1} drops more than ${guardSlack} below the incumbent's ${incumbent.guard.strict_f1}`)
  }

  return { passes: improves && !holdoutCollapsed && !guardCollapsed, reasons }
}

// A candidate carries all three measurements only when its run was scored. The
// guard measurement may be "does not apply" (`{applies: false}`); it is still
// there.
function isMeasured(candidate) {
  return Boolean(candidate && candidate.measurementStatus === 'scored' && candidate.dev && candidate.holdout && hasGuard(candidate.guard))
}

// A guard measurement is either "does not apply" or a number.
function hasGuard(guard) {
  return Boolean(guard) && (guard.applies === false || Number.isFinite(guard.strict_f1))
}

// Whether the guard applies is a fact of the implementation (its margins have
// a guardSlack exactly when the triple corpus has recordings of it), and the
// measurement has to agree: an agent's report alone never switches the guard
// off, or on.
function guardAgreesWithMargins(guard, margins) {
  return Number.isFinite(margins.guardSlack) === (guard.applies !== false)
}

// §4.3 step 5: every verified candidate is checked against the accept gate, and
// of those that pass, the one with the highest dev typed F1 (then found F1) is
// accepted. One per iteration: two candidates were each measured against the
// same incumbent, never together.
function gateCandidates(verified, incumbent, margins) {
  const gated = verified.map((p) => ({
    ...p,
    gate: acceptGate(p.candidate, incumbent, margins),
  }))
  let best = null
  for (const p of gated) {
    if (!p.gate.passes) continue
    const better = !best
      || p.candidate.dev.typed_f1 > best.candidate.dev.typed_f1
      || (p.candidate.dev.typed_f1 === best.candidate.dev.typed_f1 && p.candidate.dev.f1 > best.candidate.dev.f1)
    if (better) best = p
  }
  return { gated, best }
}

// The `stop` field of an iteration that ran: an accepted change has to reach
// `main` before the next iteration measures the incumbent there, and a run of
// iterations without an accept is a plateau.
function stopAfter(accepted, nextConsecutiveNoAccept, maxConsecutiveNoAccept, integrationBranch) {
  if (accepted) {
    return { reason: `accepted: promote ${integrationBranch} to main before the next iteration (the incumbent is measured on main)` }
  }
  if (nextConsecutiveNoAccept >= maxConsecutiveNoAccept) {
    return { reason: `plateau reached after this iteration (${nextConsecutiveNoAccept} consecutive no-accept)` }
  }
  return null
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
// What to refine. Either may be left out: the measuring scripts then resolve
// it through the pipeline registry (the type's default implementation; the
// configuration its benchmark recordings were made with, else its default),
// and everything after the Evaluate step uses what they resolved it to.
const requested = {
  implementation: loopArgs.implementation || null,
  configuration: loopArgs.configuration || null,
}

for (const [name, value] of Object.entries(requested)) {
  if (value != null && !TARGET_NAME.test(String(value))) {
    return {
      status: 'error',
      reason: `args.${name} is not a registry name: ${JSON.stringify(value)}`,
      iteration,
      consecutiveNoAccept,
      cumulativeCostUsd,
      stop: { reason: `args.${name} is not a registry name` },
    }
  }
}
// Known before anything is measured when `args` names the implementation.
if (requested.implementation && !(BACKLOGS[requested.implementation] && GATE_MARGINS[requested.implementation])) {
  return {
    status: 'error',
    reason: `the loop has no backlog or no gate margins for the ${requested.implementation} implementation: add both to BACKLOGS and GATE_MARGINS in .claude/workflows/karpathy-loop.js (the margins from re-recording that implementation unchanged)`,
    iteration,
    consecutiveNoAccept,
    cumulativeCostUsd,
    stop: { reason: `no backlog or gate margins for ${requested.implementation}` },
  }
}

// §4.3 step 6, pre-flight half: don't spend anything on an iteration the
// caller already knows should not run.
if (consecutiveNoAccept >= maxConsecutiveNoAccept) {
  return {
    status: 'stopped',
    reason: `plateau: ${consecutiveNoAccept} consecutive no-accept iterations (>= ${maxConsecutiveNoAccept}) — escalate to human`,
    iteration,
    consecutiveNoAccept,
    cumulativeCostUsd,
    stop: { reason: 'plateau' },
  }
}
if (totalBudgetUsd != null && cumulativeCostUsd >= totalBudgetUsd) {
  return {
    status: 'stopped',
    reason: `budget exhausted: cumulative $${cumulativeCostUsd} >= cap $${totalBudgetUsd}`,
    iteration,
    consecutiveNoAccept,
    cumulativeCostUsd,
    stop: { reason: 'budget exhausted' },
  }
}

phase('Evaluate')
log(`Karpathy loop iteration ${iteration}: measuring the incumbent (Loop B + benchmark replay) for ${requested.implementation || 'the registry\'s default implementation'}`)
const evaluation = await agent(evaluatePrompt(requested), { schema: EVALUATION_SCHEMA, phase: 'Evaluate', label: 'evaluate:loopB' })
if (!evaluation) {
  return {
    status: 'error',
    reason: 'Evaluate step returned no result (agent skipped or failed)',
    iteration,
    consecutiveNoAccept,
    cumulativeCostUsd,
    stop: { reason: 'the incumbent could not be measured' },
  }
}
// A stale or missing recording is not a low score. Nothing is selected,
// drafted or accepted against a measurement that did not happen.
if (evaluation.measurementStatus !== 'scored' || !evaluation.dev || !evaluation.holdout || !hasGuard(evaluation.guard)) {
  return {
    status: 'error',
    reason: `the incumbent could not be measured (${evaluation.measurementStatus}): ${evaluation.measurementDetail || 'see the tournament digest'}. Record what is stale or missing on main before running the loop (the benchmark: ${benchmarkRecordCommand({ implementation: evaluation.implementation || requested.implementation, configuration: evaluation.configuration || requested.configuration })}; the triple corpus: ${TRIPLE_CORPUS_RECORD_COMMAND})`,
    iteration,
    consecutiveNoAccept,
    cumulativeCostUsd,
    stop: { reason: 'the incumbent could not be measured' },
    evaluation,
  }
}

// What the scripts ran is what the rest of the iteration refines.
const target = { implementation: evaluation.implementation, configuration: evaluation.configuration, model: evaluation.model }
const mismatched = Object.entries(requested).filter(([name, value]) => value != null && value !== target[name])
if (!TARGET_NAME.test(String(target.implementation)) || !TARGET_NAME.test(String(target.configuration)) || mismatched.length > 0) {
  return {
    status: 'error',
    reason: `the measurement does not say it ran what was asked for (asked: ${JSON.stringify(requested)}; measured: ${JSON.stringify(target)})`,
    iteration,
    consecutiveNoAccept,
    cumulativeCostUsd,
    stop: { reason: 'the incumbent could not be measured' },
    evaluation,
  }
}
const backlog = BACKLOGS[target.implementation]
const margins = GATE_MARGINS[target.implementation]
if (!backlog || !margins) {
  return {
    status: 'error',
    reason: `the loop has no backlog or no gate margins for the ${target.implementation} implementation: add both to BACKLOGS and GATE_MARGINS in .claude/workflows/karpathy-loop.js (the margins from re-recording that implementation unchanged)`,
    iteration,
    consecutiveNoAccept,
    cumulativeCostUsd,
    stop: { reason: `no backlog or gate margins for ${target.implementation}` },
    evaluation,
  }
}
if (!guardAgreesWithMargins(evaluation.guard, margins)) {
  return {
    status: 'error',
    reason: `the measurement says the triple-corpus guard ${evaluation.guard.applies === false ? 'does not apply' : 'applies'} to ${target.implementation}, and its gate margins (GATE_MARGINS) say the opposite: one of them is wrong, and nothing is accepted or rejected until they agree`,
    iteration,
    consecutiveNoAccept,
    cumulativeCostUsd,
    stop: { reason: 'the guard and the gate margins disagree' },
    evaluation,
  }
}
if (margins.provisional) {
  log(`The gate margins for ${target.implementation} are provisional (${margins.basis}). Still to measure: ${margins.missing}. An accept or a reject under them is not yet a trusted verdict.`)
}

// §4.3 step 6, other half: stop on success before spending anything else.
if (meetsFloors(evaluation.holdout, holdoutFloors)) {
  return {
    status: 'stopped',
    reason: 'holdout typed floors met (§1 exit criterion)',
    iteration,
    consecutiveNoAccept,
    cumulativeCostUsd,
    stop: { reason: 'holdout typed floors met' },
    evaluation,
  }
}

phase('Select')
const ledgerInfo = await agent(ledgerReadPrompt(target.implementation), { schema: LEDGER_SCHEMA, phase: 'Select', label: 'select:ledger', effort: 'low' })
const rejectedHypotheses = (ledgerInfo && ledgerInfo.rejectedHypotheses) || []
const acceptedHypotheses = (ledgerInfo && ledgerInfo.acceptedHypotheses) || []
const targets = selectTargets(evaluation.failureCounts, rejectedHypotheses, acceptedHypotheses, hypothesisCount, backlog)
log(`Selected ${targets.length} target hypothesis(es): ${targets.map((t) => t.id).join(', ') || '(none — the backlog is exhausted)'}`)

if (targets.length === 0) {
  return {
    status: 'no_accept',
    reason: `no untried hypotheses remain in the ${target.implementation} backlog (all already rejected, accepted or blocked) — read the benchmark report and add new hypotheses to BACKLOGS.${target.implementation}`,
    iteration,
    consecutiveNoAccept: consecutiveNoAccept + 1,
    cumulativeCostUsd,
    // Another iteration would select nothing again.
    stop: { reason: 'the hypothesis backlog is exhausted' },
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
// Every agent that returned did work in a worktree, and may have paid for a
// recording, whether or not its candidate could be measured.
const returned = experimentResults.filter(Boolean)
const iterationCostUsd = returned.reduce((sum, c) => sum + (c.recordingCostUsd || 0), 0)
const candidates = returned.filter(isMeasured)
const unmeasured = returned.filter((c) => !isMeasured(c))

if (returned.length === 0) {
  return {
    status: 'no_accept',
    reason: 'no experimenter returned a result (agents failed or were skipped)',
    iteration,
    consecutiveNoAccept: consecutiveNoAccept + 1,
    cumulativeCostUsd,
    stop: stopAfter(false, consecutiveNoAccept + 1, maxConsecutiveNoAccept, integrationBranch),
    evaluation,
    targets,
    experimentResults,
  }
}

phase('Verify')
const verdicts = await parallel(candidates.map((candidate) => () =>
  agent(verifyPrompt(candidate, target, evaluation.staleElsewhere), { schema: VERIFY_SCHEMA, phase: 'Verify', label: `verify:${candidate.hypothesisId}` })
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

const { gated, best } = gateCandidates(verified, evaluation, margins)
const accepted = Boolean(best)

phase('Decide')
const decisions = paired.map((p) => {
  // By identity, not by hypothesis id: an id is whatever the agent returned.
  const gatedEntry = gated.find((g) => g.candidate === p.candidate)
  if (!p.verdict) {
    return { candidate: p.candidate, decision: 'unmeasured', reason: 'not verified: the verifier agent returned no result' }
  }
  if (!gatedEntry) {
    return { candidate: p.candidate, decision: 'rejected', reason: `failed verification: ${p.verdict.reason}` }
  }
  if (gatedEntry === best) {
    return { candidate: p.candidate, decision: 'accepted', reason: 'passed verification and the §6 accept gate' }
  }
  if (gatedEntry.gate.passes) {
    return {
      candidate: p.candidate,
      decision: 'deferred',
      reason: `passed the §6 accept gate, but ${best.candidate.hypothesisId} scored higher and one change is accepted per iteration; not written to the ledger, so it is drafted again against the new incumbent`,
    }
  }
  return {
    candidate: p.candidate,
    decision: 'rejected',
    reason: `verified but failed the §6 accept gate: ${gatedEntry.gate.reasons.join('; ')}`,
  }
}).concat(unmeasured.map((candidate) => ({
  // Recorded, with its cost, but not as a rejection: a recording that failed or
  // a run that could not be scored says nothing about the hypothesis, which
  // stays selectable and may be drafted again next iteration. Nothing counts
  // repeats; the loop halts for a human after every accept and after three
  // iterations without one, and the ledger shows a hypothesis that keeps
  // failing to measure.
  candidate,
  decision: 'unmeasured',
  reason: `not measured (${candidate.measurementStatus}): ${candidate.measurementDetail || 'no detail given'}`,
})))

const outcomes = await parallel(decisions.map((d) => () => {
  const pair = paired.find((p) => p.candidate === d.candidate)
  const otherTargets = (pair && pair.verdict && pair.verdict.otherTargets) || []
  return agent(decidePrompt(d.candidate, d.decision, d.reason, iteration, integrationBranch, target, margins, otherTargets), {
    schema: DECIDE_SCHEMA,
    phase: 'Decide',
    label: `decide:${d.candidate.hypothesisId}`,
  })
}))

const nextConsecutiveNoAccept = accepted ? 0 : consecutiveNoAccept + 1

return {
  status: accepted ? 'accepted' : 'no_accept',
  iteration,
  consecutiveNoAccept: nextConsecutiveNoAccept,
  cumulativeCostUsd: cumulativeCostUsd + iterationCostUsd,
  implementation: target.implementation,
  configuration: target.configuration,
  // True when the verdicts above were reached under margins not yet backed by
  // a re-recording measurement (GATE_MARGINS): treat them as provisional too.
  provisionalMargins: Boolean(margins.provisional),
  acceptedHypothesis: accepted ? best.candidate.hypothesisId : null,
  evaluation,
  targets,
  candidates: paired,
  unmeasured,
  decisions,
  outcomes,
  stop: stopAfter(accepted, nextConsecutiveNoAccept, maxConsecutiveNoAccept, integrationBranch),
}
