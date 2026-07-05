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
const ORCHESTRATION_MARKER = "const iteration = (args && args.iteration) || 1";

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
    `${declarations}\nglobalThis.__mechanics = { clamp, meetsFloors, selectTargets, acceptGate, SEED_BACKLOG, EPSILON, HOLDOUT_SLACK, DEFAULT_HOLDOUT_FLOORS };`,
    sandbox,
    { filename: SOURCE_PATH },
  );
  return sandbox.__mechanics;
}

const { clamp, meetsFloors, selectTargets, acceptGate, SEED_BACKLOG, EPSILON, HOLDOUT_SLACK, DEFAULT_HOLDOUT_FLOORS } =
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
  assert.equal(clamp(0, 2, 4), 2);
});
test("clamp bounds a value above the maximum", () => {
  assert.equal(clamp(9, 2, 4), 4);
});
test("clamp passes through an in-range value", () => {
  assert.equal(clamp(3, 2, 4), 3);
});

// -- meetsFloors (§4.3 step 6 success stop-check) -----------------------

test("meetsFloors triggers the success stop-check when every holdout floor is met exactly", () => {
  const holdout = { strict_precision: 0.6, strict_recall: 0.5, strict_f1: 0.5 };
  assert.equal(meetsFloors(holdout, DEFAULT_HOLDOUT_FLOORS), true);
});
test("meetsFloors does not trigger when a single floor is missed", () => {
  const holdout = { strict_precision: 0.59, strict_recall: 0.5, strict_f1: 0.5 };
  assert.equal(meetsFloors(holdout, DEFAULT_HOLDOUT_FLOORS), false);
});

// -- acceptGate (§6 accept gate) -----------------------------------------
// Boundary cases are constructed so the subtraction the gate itself performs
// lands on an exact IEEE-754 value (e.g. diffing against 0) rather than
// relying on decimal literals like `0.5 + 0.005` landing exactly on
// `EPSILON`, which they do not (double-precision rounding pushes the sum
// a hair past 0.005).

test("acceptGate accepts when dev soft-F1 beats incumbent by more than epsilon and nothing else regresses", () => {
  const incumbentDev = { soft_f1: 0, strict_f1: 0.3 };
  const incumbentHoldout = { strict_f1: 0.28 };
  const candidate = { dev: { soft_f1: EPSILON + 0.001, strict_f1: 0.3 }, holdout: { strict_f1: 0.28 } };
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK);
  assert.equal(result.passes, true);
  // `result.reasons` is an array from the vm sandbox realm, so compare by
  // length/content rather than assert.deepEqual (which is prototype-strict
  // and cross-realm arrays never share a prototype).
  assert.equal(result.reasons.length, 0);
});
test("acceptGate rejects exactly at the improvement boundary (diff == epsilon, not > epsilon)", () => {
  const incumbentDev = { soft_f1: 0, strict_f1: 0.3 };
  const incumbentHoldout = { strict_f1: 0.28 };
  const candidate = { dev: { soft_f1: EPSILON, strict_f1: 0.3 }, holdout: { strict_f1: 0.28 } };
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK);
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("does not beat incumbent")));
});
test("acceptGate rejects on dev strict-F1 regression even when soft-F1 improves", () => {
  const incumbentDev = { soft_f1: 0, strict_f1: 0.3 };
  const incumbentHoldout = { strict_f1: 0.28 };
  const candidate = { dev: { soft_f1: 0.6, strict_f1: 0.29 }, holdout: { strict_f1: 0.28 } };
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK);
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("regresses")));
});
test("acceptGate rejects when holdout strict-F1 collapses beyond the slack", () => {
  const incumbentDev = { soft_f1: 0, strict_f1: 0.3 };
  const incumbentHoldout = { strict_f1: 0.28 };
  const candidate = {
    dev: { soft_f1: 0.6, strict_f1: 0.31 },
    holdout: { strict_f1: incumbentHoldout.strict_f1 - HOLDOUT_SLACK - 0.001 },
  };
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK);
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("collapses")));
});
test("acceptGate tolerates a holdout drop exactly at the slack boundary", () => {
  const incumbentDev = { soft_f1: 0, strict_f1: 0.3 };
  const incumbentHoldout = { strict_f1: 0.28 };
  const candidate = {
    dev: { soft_f1: 0.6, strict_f1: 0.31 },
    holdout: { strict_f1: incumbentHoldout.strict_f1 - HOLDOUT_SLACK },
  };
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK);
  assert.equal(result.passes, true);
});

// -- selectTargets (§4.3 step 2) -----------------------------------------

test("selectTargets ranks failure classes by GT-triple count (highest first)", () => {
  const failureStageCounts = { label_mismatch: 3, candidate_missing: 40 };
  const [target] = selectTargets(failureStageCounts, [], 1);
  assert.equal(target.targetStage, "candidate_missing");
});
test("selectTargets excludes hypotheses the ledger already rejected", () => {
  const failureStageCounts = { candidate_missing: 40 };
  const rejected = SEED_BACKLOG.filter((h) => h.stages.includes("candidate_missing")).map((h) => h.id);
  assert.ok(rejected.length > 0, "fixture assumption: at least one seeded hypothesis targets candidate_missing");
  const targets = selectTargets(failureStageCounts, rejected, 3);
  for (const target of targets) {
    assert.ok(!rejected.includes(target.id), `expected ${target.id} to be excluded as already rejected`);
  }
});
test("selectTargets returns nothing once every seeded hypothesis is rejected", () => {
  const failureStageCounts = { candidate_missing: 40 };
  const allIds = SEED_BACKLOG.map((h) => h.id);
  const targets = selectTargets(failureStageCounts, allIds, 3);
  assert.equal(targets.length, 0);
});

console.log(`\n${passCount} passed, ${failCount} failed`);
if (failCount > 0) {
  process.exit(1);
}
