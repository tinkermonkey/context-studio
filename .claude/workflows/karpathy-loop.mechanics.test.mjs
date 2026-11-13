#!/usr/bin/env node
/**
 * Standalone mechanics check for karpathy-loop.js's pure decision-logic
 * functions (documentation/karpathy_loop_design.md §4.3/§6): `clamp`,
 * `meetsFloors`, `selectTargets`, and `acceptGate`.
 *
 * karpathy-loop.js cannot be executed directly by plain Node: it is a
 * Workflow script whose top-level body uses host-injected bindings
 * (`agent`, `phase`, `parallel`, `log`, `args`) and top-level `await`/
 * `return`, which only the Workflow runtime supplies. Running it "for
 * real" means spawning live sub-agents against the real corpus — not a
 * unit-level check, and not something to do casually (see the script's
 * `whenToUse`).
 *
 * So instead: extract the pure, side-effect-free prefix of the file — every
 * function/constant declared *before* the top-level orchestration
 * statements that call `agent()`/`phase()`/`parallel()` — and evaluate that
 * source directly in a sandbox. This exercises the ACTUAL implementation
 * (not a re-typed copy of it), with no agent fan-out and no repo mutation.
 *
 * Run: node .claude/workflows/karpathy-loop.mechanics.test.mjs
 */

import assert from "node:assert/strict";
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_PATH = path.join(__dirname, "karpathy-loop.js");
// Everything above this line is pure declarations; this line and below is
// the top-level orchestration that requires the Workflow runtime.
const ORCHESTRATION_MARKER = "let loopArgs = args";

function loadPureDeclarations() {
  const fullSource = fs.readFileSync(SOURCE_PATH, "utf8");
  const markerIndex = fullSource.indexOf(ORCHESTRATION_MARKER);
  assert.ok(
    markerIndex > -1,
    `could not find orchestration marker in ${SOURCE_PATH} -- has karpathy-loop.js been restructured? update ORCHESTRATION_MARKER in this file.`,
  );
  // The sliced prefix still contains the file's one ESM-only token
  // (`export const meta`); strip it so the prefix is plain, evaluable JS.
  const declarations = fullSource.slice(0, markerIndex).replace("export const meta", "const meta");

  const sandbox = { console };
  vm.createContext(sandbox);
  vm.runInContext(
    `${declarations}\nglobalThis.__mechanics = { clamp, meetsFloors, selectTargets, acceptGate, SEED_BACKLOG, FAILURE_KINDS, FROZEN_PATHS, EPSILON, HOLDOUT_SLACK, COVERAGE_SLACK, GUARD_SLACK, DEFAULT_HOLDOUT_FLOORS, evaluatePrompt, experimentPrompt, verifyPrompt };`,
    sandbox,
    { filename: SOURCE_PATH },
  );
  return sandbox.__mechanics;
}

const { clamp, meetsFloors, selectTargets, acceptGate, SEED_BACKLOG, FAILURE_KINDS, FROZEN_PATHS, EPSILON, HOLDOUT_SLACK, COVERAGE_SLACK, GUARD_SLACK, DEFAULT_HOLDOUT_FLOORS, evaluatePrompt, experimentPrompt, verifyPrompt } =
  loadPureDeclarations();

let passCount = 0;
let failCount = 0;

function test(name, fn) {
  try {
    fn();
    passCount += 1;
    console.log(`ok - ${name}`);
  } catch (err) {
    failCount += 1;
    console.error(`FAIL - ${name}`);
    console.error(err);
  }
}

// -- clamp -------------------------------------------------------------

test("clamp bounds a value below the minimum", () => {
  assert.equal(clamp(1, 2, 4), 2);
});
test("clamp bounds a value above the maximum", () => {
  assert.equal(clamp(9, 2, 4), 4);
});
test("clamp passes through an in-range value", () => {
  assert.equal(clamp(3, 2, 4), 3);
});

// -- meetsFloors (§4.3 step 6 success stop-check) -----------------------

test("meetsFloors triggers the success stop-check when every holdout floor is met exactly", () => {
  const holdout = { typed_precision: 0.6, typed_recall: 0.5, typed_f1: 0.5 };
  assert.equal(meetsFloors(holdout, DEFAULT_HOLDOUT_FLOORS), true);
});
test("meetsFloors does not trigger when a single floor is missed", () => {
  const holdout = { typed_precision: 0.59, typed_recall: 0.5, typed_f1: 0.5 };
  assert.equal(meetsFloors(holdout, DEFAULT_HOLDOUT_FLOORS), false);
});
test("meetsFloors does not trigger on a holdout with no typed measures (an unmeasured run)", () => {
  assert.equal(meetsFloors({}, DEFAULT_HOLDOUT_FLOORS), false);
});

// -- acceptGate (§6 accept gate) -----------------------------------------
// Boundary cases are constructed so the subtraction the gate itself performs
// lands on an exact IEEE-754 value (e.g. diffing against 0) rather than
// relying on decimal literals like `0.5 + 0.005` landing exactly on
// `EPSILON`, which they do not.

function incumbentAt({ f1 = 0, typed_f1 = 0.3, holdout = 0.28, guard = 0.9 } = {}) {
  return { dev: { f1, typed_f1 }, holdout: { typed_f1: holdout }, guard: { strict_f1: guard } };
}
function candidateAt({ f1 = 0, typed_f1 = 0.3, holdout = 0.28, guard = 0.9 } = {}) {
  return { dev: { f1, typed_f1 }, holdout: { typed_f1: holdout }, guard: { strict_f1: guard } };
}
function gate(candidate, incumbent) {
  return acceptGate(candidate, incumbent, EPSILON, HOLDOUT_SLACK, COVERAGE_SLACK, GUARD_SLACK);
}

test("acceptGate accepts when dev found F1 beats the incumbent by more than epsilon and nothing regresses", () => {
  const result = gate(candidateAt({ f1: EPSILON + 0.001 }), incumbentAt());
  assert.equal(result.passes, true);
  // `result.reasons` is an array from the vm sandbox realm, so compare by
  // length/content rather than assert.deepEqual (cross-realm arrays never
  // share a prototype).
  assert.equal(result.reasons.length, 0);
});
test("acceptGate rejects exactly at the improvement boundary (diff == epsilon, not > epsilon)", () => {
  const result = gate(candidateAt({ f1: EPSILON }), incumbentAt());
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("neither dev found F1")));
});
test("acceptGate rejects a coverage gain that costs any typed F1 (no slack on exactness)", () => {
  const result = gate(candidateAt({ f1: 0.6, typed_f1: 0.29 }), incumbentAt());
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("regresses")));
});
test("acceptGate accepts a typed F1 gain that dips found F1 within coverageSlack", () => {
  const incumbent = incumbentAt({ f1: 0.5, typed_f1: 0.3 });
  const result = gate(candidateAt({ f1: 0.5 - COVERAGE_SLACK + 0.01, typed_f1: 0.4 }), incumbent);
  assert.equal(result.passes, true);
});
test("acceptGate rejects a typed F1 gain when found F1 drops beyond coverageSlack", () => {
  const incumbent = incumbentAt({ f1: 0.5, typed_f1: 0.3 });
  const result = gate(candidateAt({ f1: 0.5 - COVERAGE_SLACK - 0.01, typed_f1: 0.4 }), incumbent);
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("coverageSlack")));
});
test("acceptGate rejects when the holdout document's typed F1 drops beyond the slack", () => {
  const incumbent = incumbentAt({ holdout: 0.5 });
  const result = gate(candidateAt({ f1: 0.6, holdout: 0.5 - HOLDOUT_SLACK - 0.01 }), incumbent);
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("holdout typed F1")));
});
test("acceptGate tolerates a holdout drop exactly at the slack boundary", () => {
  // incumbent 0.02 and candidate 0: the gate computes 0 < 0.02 - 0.02, which is false.
  const incumbent = incumbentAt({ holdout: HOLDOUT_SLACK });
  const result = gate(candidateAt({ f1: 0.6, holdout: 0 }), incumbent);
  assert.equal(result.passes, true);
});
test("acceptGate rejects when the triple-corpus guard drops beyond its slack, however good the benchmark gain", () => {
  const incumbent = incumbentAt({ guard: 0.9 });
  const result = gate(candidateAt({ f1: 0.9, typed_f1: 0.9, holdout: 0.9, guard: 0.9 - GUARD_SLACK - 0.01 }), incumbent);
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("triple-corpus strict-F1")));
});
test("acceptGate is not rescued by a guard or holdout gain when dev does not improve", () => {
  const result = gate(candidateAt({ holdout: 0.9, guard: 1 }), incumbentAt());
  assert.equal(result.passes, false);
});
test("acceptGate reads only dev, holdout and guard: extra diagnostics on a candidate change nothing", () => {
  const incumbent = incumbentAt();
  const plain = gate(candidateAt({ f1: 0.2 }), incumbent);
  const decorated = gate({ ...candidateAt({ f1: 0.2 }), bootstrap: { strict_f1: 0 }, recognition: { f1: 0 } }, incumbent);
  assert.equal(decorated.passes, plain.passes);
  assert.equal(acceptGate.length, 6);
});

// -- selectTargets (§4.3 step 2) -----------------------------------------

test("every backlog hypothesis names only failure kinds the benchmark reports", () => {
  for (const hyp of SEED_BACKLOG) {
    assert.ok(hyp.id && hyp.summary, "a hypothesis needs an id and a summary");
    for (const kind of hyp.kinds) {
      assert.ok(FAILURE_KINDS.includes(kind), `${hyp.id}: unknown failure kind ${kind}`);
    }
  }
  const ids = SEED_BACKLOG.map((h) => h.id);
  assert.equal(new Set(ids).size, ids.length, "hypothesis ids are unique");
});
test("every benchmark failure kind has at least one hypothesis", () => {
  for (const kind of FAILURE_KINDS) {
    assert.ok(SEED_BACKLOG.some((h) => h.kinds.includes(kind)), `no hypothesis for ${kind}`);
  }
});
test("selectTargets ranks failure kinds by count (highest first)", () => {
  const [target] = selectTargets({ spurious: 3, mistyped: 40 }, [], [], 1);
  assert.equal(target.targetKind, "mistyped");
});
test("selectTargets excludes hypotheses the ledger already rejected", () => {
  const rejected = SEED_BACKLOG.filter((h) => h.kinds.includes("mistyped")).map((h) => h.id);
  const targets = selectTargets({ mistyped: 40 }, rejected, [], 2);
  for (const t of targets) assert.ok(!rejected.includes(t.id), `${t.id} was rejected`);
});
test("selectTargets excludes hypotheses the ledger already accepted (merged into the incumbent)", () => {
  const accepted = ["full_class_catalog"];
  const targets = selectTargets({ mistyped: 40 }, [], accepted, SEED_BACKLOG.length);
  assert.ok(!targets.some((t) => t.id === "full_class_catalog"));
});
test("selectTargets returns nothing once every seeded hypothesis is decided", () => {
  const all = SEED_BACKLOG.map((h) => h.id);
  assert.equal(selectTargets({ mistyped: 40 }, all, [], 3).length, 0);
  assert.equal(selectTargets({ mistyped: 40 }, [], all, 3).length, 0);
});
test("selectTargets never selects a hypothesis marked blocked or done", () => {
  const first = SEED_BACKLOG.find((h) => h.kinds.includes("mistyped"));
  for (const flag of ["blocked", "done"]) {
    first[flag] = true;
    try {
      const targets = selectTargets({ mistyped: 40 }, [], [], SEED_BACKLOG.length);
      assert.ok(!targets.some((t) => t.id === first.id), `${first.id} is ${flag}`);
    } finally {
      delete first[flag];
    }
  }
});
test("selectTargets never selects the same hypothesis twice and backfills to the requested count", () => {
  const targets = selectTargets({ mistyped: 40, missed_core: 30 }, [], [], 4);
  assert.equal(targets.length, 4);
  assert.equal(new Set(targets.map((t) => t.id)).size, 4);
});
test("selectTargets backfills a kind-less hypothesis only after the ranked kinds are used up", () => {
  const targets = selectTargets({}, [], [], SEED_BACKLOG.length);
  assert.ok(targets.some((t) => t.id === "per_source_confidence_bands" && t.targetKind === "general"));
});

// -- prompts: the measurement layer stays frozen ---------------------------

const EVALUATION = {
  errorReportPath: "experiments/reports/tournament_x_benchmark.json",
  dev: { typed_f1: 0.2, f1: 0.4 },
  holdout: { typed_f1: 0.1 },
  guard: { strict_f1: 0.9 },
};
const CANDIDATE = {
  hypothesisId: "full_class_catalog",
  summary: "offer every class",
  worktreePath: "/tmp/wt",
  branchName: "wt-1",
  baseCommit: "abc",
  changedFiles: [],
  diffStat: "",
  testsPassed: true,
  dev: { typed_f1: 0.3, f1: 0.4 },
  holdout: { typed_f1: 0.1 },
  guard: { strict_f1: 0.9 },
};

test("the experimenter and the verifier are both given every frozen path", () => {
  const experiment = experimentPrompt({ id: "x", summary: "y", targetKind: "mistyped" }, EVALUATION);
  const verify = verifyPrompt(CANDIDATE);
  for (const frozen of FROZEN_PATHS) {
    assert.ok(experiment.includes(frozen), `experiment prompt lacks ${frozen}`);
    assert.ok(verify.includes(frozen), `verify prompt lacks ${frozen}`);
  }
});
test("the frozen paths cover the gold extractions, the harness, the scorer scripts and the ledger", () => {
  for (const needle of ["extraction_benchmark/", "_harness/", "quality_tournament.py", "benchmark_replay.py", "ledger.jsonl", "fixtures/dr_spec/"]) {
    assert.ok(FROZEN_PATHS.some((p) => p.includes(needle)), `nothing freezes ${needle}`);
  }
});
test("the cassette directories are not frozen: an experiment that changes a prompt must re-record them", () => {
  assert.ok(!FROZEN_PATHS.some((p) => p.includes("cassettes")));
  const experiment = experimentPrompt({ id: "x", summary: "y", targetKind: "mistyped" }, EVALUATION);
  assert.ok(experiment.includes("scripts/record_default_cassettes.py --record"));
  assert.ok(experiment.includes("scripts/benchmark_replay.py --record --spend"));
});
test("the incumbent and each candidate are measured by the same steps", () => {
  const evaluate = evaluatePrompt();
  const experiment = experimentPrompt({ id: "x", summary: "y", targetKind: "mistyped" }, EVALUATION);
  const step = "python scripts/quality_tournament.py --pipeline individual --passes 1 --restarts 1";
  assert.ok(evaluate.includes(step) && experiment.includes(step));
  assert.ok(evaluate.includes("STALE CASSETTES") && experiment.includes("STALE CASSETTES"));
});

console.log(`\n${passCount} passed, ${failCount} failed`);
if (failCount > 0) {
  process.exit(1);
}
