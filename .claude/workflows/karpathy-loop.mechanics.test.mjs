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
    `${declarations}\nglobalThis.__mechanics = { clamp, meetsFloors, selectTargets, acceptGate, SEED_BACKLOG, EPSILON, HOLDOUT_SLACK, SOFT_SLACK, DEFAULT_HOLDOUT_FLOORS, hypothesisPipeline, incumbentPipelineOf };`,
    sandbox,
    { filename: SOURCE_PATH },
  );
  return sandbox.__mechanics;
}

const { clamp, meetsFloors, selectTargets, acceptGate, SEED_BACKLOG, EPSILON, HOLDOUT_SLACK, SOFT_SLACK, DEFAULT_HOLDOUT_FLOORS, hypothesisPipeline, incumbentPipelineOf } =
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
test("meetsFloors never triggers while holdout GT review is pending, even at perfect floors", () => {
  const holdout = { strict_precision: 1, strict_recall: 1, strict_f1: 1 };
  assert.equal(meetsFloors(holdout, DEFAULT_HOLDOUT_FLOORS, true), false);
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
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK, false, SOFT_SLACK);
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("neither dev soft-F1")));
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
test("acceptGate does not block on a holdout collapse while GT review is pending -- surfaces it as an advisory instead", () => {
  const incumbentDev = { soft_f1: 0, strict_f1: 0.3 };
  const incumbentHoldout = { strict_f1: 0.28 };
  const candidate = {
    dev: { soft_f1: 0.6, strict_f1: 0.31 },
    holdout: { strict_f1: incumbentHoldout.strict_f1 - HOLDOUT_SLACK - 0.1 },
  };
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK, true);
  assert.equal(result.passes, true);
  assert.equal(result.reasons.length, 0);
  assert.ok(result.advisories.some((a) => a.includes("pending human review")));
});

// -- symmetric gate: strict-F1-driven acceptance (§6) ---------------------
// A candidate may earn acceptance by improving exactness (strict-F1) even when
// soft-F1 (coverage) dips within SOFT_SLACK — the two_pass-v2 case.
test("acceptGate accepts a strict-F1 improvement that dips soft-F1 within softSlack (the two_pass-v2 trade)", () => {
  const incumbentDev = { soft_f1: 0.412, strict_f1: 0.324 };
  const incumbentHoldout = { strict_f1: 0.321 };
  // two_pass v2: strict +0.035, soft -0.033 (< SOFT_SLACK), holdout steady.
  const candidate = { dev: { soft_f1: 0.379, strict_f1: 0.359 }, holdout: { strict_f1: 0.322 } };
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK, false, SOFT_SLACK);
  assert.equal(result.passes, true);
  assert.equal(result.reasons.length, 0);
});
test("acceptGate rejects a strict-F1 improvement when soft-F1 collapses beyond softSlack", () => {
  const incumbentDev = { soft_f1: 0.412, strict_f1: 0.324 };
  const incumbentHoldout = { strict_f1: 0.321 };
  // strict improves, but soft drops 0.10 (> SOFT_SLACK=0.05): a real coverage collapse, not a trade.
  const candidate = { dev: { soft_f1: 0.312, strict_f1: 0.359 }, holdout: { strict_f1: 0.322 } };
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK, false, SOFT_SLACK);
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("collapses more than softSlack")));
});
test("acceptGate still keeps a hard strict-F1 floor for soft-driven acceptance (no slack there)", () => {
  const incumbentDev = { soft_f1: 0.40, strict_f1: 0.30 };
  const incumbentHoldout = { strict_f1: 0.28 };
  // soft improves hugely but strict regresses even slightly: soft-driven path
  // keeps the hard floor, so this is rejected (exactness is never traded away
  // when coverage drives acceptance).
  const candidate = { dev: { soft_f1: 0.60, strict_f1: 0.299 }, holdout: { strict_f1: 0.28 } };
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK, false, SOFT_SLACK);
  assert.equal(result.passes, false);
  assert.ok(result.reasons.some((r) => r.includes("regresses below incumbent floor")));
});

// -- acceptGate bootstrap immunity (karpathy_loop_dr_ontology_design.md §5
// Must-Fix 2 / ADR-7: Wave 1 DR bootstrap scenarios are diagnostic-only and
// must never, alone, be sufficient grounds for an accept/reject decision) ---

test("acceptGate's signature has no bootstrap parameter -- structurally cannot gate on it", () => {
  assert.equal(acceptGate.length, 7); // candidate, incumbentDev, incumbentHoldout, epsilon, holdoutSlack, holdoutReviewPending, softSlack
});

test("acceptGate's decision is identical whether the candidate carries glowing, terrible, or no bootstrap diagnostics", () => {
  const incumbentDev = { soft_f1: 0, strict_f1: 0.3 };
  const incumbentHoldout = { strict_f1: 0.28 };
  const baseCandidate = { dev: { soft_f1: 0.6, strict_f1: 0.31 }, holdout: { strict_f1: 0.28 } };

  const noBootstrap = acceptGate(baseCandidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK);
  const glowingBootstrap = acceptGate(
    { ...baseCandidate, bootstrap: { strict_f1: 1, soft_f1: 1 } },
    incumbentDev,
    incumbentHoldout,
    EPSILON,
    HOLDOUT_SLACK,
  );
  const terribleBootstrap = acceptGate(
    { ...baseCandidate, bootstrap: { strict_f1: 0, soft_f1: 0 } },
    incumbentDev,
    incumbentHoldout,
    EPSILON,
    HOLDOUT_SLACK,
  );

  assert.equal(noBootstrap.passes, true);
  assert.equal(glowingBootstrap.passes, noBootstrap.passes);
  assert.equal(terribleBootstrap.passes, noBootstrap.passes);
  // Compare by content (JSON.stringify), not assert.deepEqual -- these arrays
  // cross the vm sandbox realm boundary and never share a prototype.
  assert.equal(JSON.stringify(glowingBootstrap.reasons), JSON.stringify(noBootstrap.reasons));
  assert.equal(JSON.stringify(terribleBootstrap.reasons), JSON.stringify(noBootstrap.reasons));
});

test("acceptGate rejects on a genuine dev regression even when bootstrap diagnostics are perfect -- bootstrap alone cannot rescue a bad candidate", () => {
  const incumbentDev = { soft_f1: 0, strict_f1: 0.3 };
  const incumbentHoldout = { strict_f1: 0.28 };
  const candidate = {
    dev: { soft_f1: EPSILON, strict_f1: 0.3 }, // fails to beat incumbent by > epsilon
    holdout: { strict_f1: 0.28 },
    bootstrap: { strict_f1: 1, soft_f1: 1 },
  };
  const result = acceptGate(candidate, incumbentDev, incumbentHoldout, EPSILON, HOLDOUT_SLACK);
  assert.equal(result.passes, false);
});

// -- selectTargets (§4.3 step 2) -----------------------------------------

test("selectTargets ranks failure classes by GT-triple count (highest first)", () => {
  const failureStageCounts = { label_mismatch: 3, candidate_missing: 40 };
  const [target] = selectTargets(failureStageCounts, [], [], 1, "open_v1");
  assert.equal(target.targetStage, "candidate_missing");
});
test("selectTargets excludes hypotheses the ledger already rejected", () => {
  const failureStageCounts = { candidate_missing: 40 };
  const rejected = SEED_BACKLOG.filter((h) => h.stages.includes("candidate_missing")).map((h) => h.id);
  assert.ok(rejected.length > 0, "fixture assumption: at least one seeded hypothesis targets candidate_missing");
  const targets = selectTargets(failureStageCounts, rejected, [], 3, "open_v1");
  for (const target of targets) {
    assert.ok(!rejected.includes(target.id), `expected ${target.id} to be excluded as already rejected`);
  }
});
test("selectTargets excludes hypotheses the ledger already accepted (merged into the incumbent)", () => {
  const failureStageCounts = { candidate_missing: 40 };
  const accepted = SEED_BACKLOG.filter((h) => h.stages.includes("candidate_missing")).map((h) => h.id);
  assert.ok(accepted.length > 0, "fixture assumption: at least one seeded hypothesis targets candidate_missing");
  const targets = selectTargets(failureStageCounts, [], accepted, 3, "open_v1");
  for (const target of targets) {
    assert.ok(!accepted.includes(target.id), `expected ${target.id} to be excluded as already accepted/merged`);
  }
});
test("selectTargets returns nothing once every seeded hypothesis is rejected", () => {
  const failureStageCounts = { candidate_missing: 40 };
  const allIds = SEED_BACKLOG.map((h) => h.id);
  const targets = selectTargets(failureStageCounts, allIds, [], 3, "open_v1");
  assert.equal(targets.length, 0);
});
test("selectTargets returns nothing once every seeded hypothesis is accepted", () => {
  const failureStageCounts = { candidate_missing: 40 };
  const allIds = SEED_BACKLOG.map((h) => h.id);
  const targets = selectTargets(failureStageCounts, [], allIds, 3, "open_v1");
  assert.equal(targets.length, 0);
});
// These inject a synthetic entry rather than depend on the live backlog
// containing a blocked/done hypothesis (the set flips as hypotheses land), so
// they exercise the filter itself regardless of current backlog state.
test("selectTargets never selects a hypothesis marked blocked, even when its stage is top-ranked", () => {
  const synthetic = { id: "__synthetic_blocked__", stages: ["candidate_missing"], summary: "x", blocked: true };
  SEED_BACKLOG.push(synthetic);
  try {
    const targets = selectTargets({ candidate_missing: 1000 }, [], [], SEED_BACKLOG.length, "open_v1");
    assert.ok(!targets.some((t) => t.id === synthetic.id), "expected blocked hypothesis to never be selected");
  } finally {
    SEED_BACKLOG.pop();
  }
});
test("selectTargets never selects a hypothesis marked done (implemented outside the loop)", () => {
  const synthetic = { id: "__synthetic_done__", stages: ["candidate_missing"], summary: "x", done: true };
  SEED_BACKLOG.push(synthetic);
  try {
    const targets = selectTargets({ candidate_missing: 1000 }, [], [], SEED_BACKLOG.length, "open_v1");
    assert.ok(!targets.some((t) => t.id === synthetic.id), "expected done hypothesis to never be selected");
  } finally {
    SEED_BACKLOG.pop();
  }
});

// -- pipeline scoping (§4.3 step 2): a hypothesis only helps if it targets the
// incumbent pipeline; an off-pipeline hypothesis is scored as its own variant
// and can never clear the accept gate against a different-pipeline incumbent.
test("incumbentPipelineOf maps default* variants to the default pipeline, else open_v1", () => {
  assert.equal(incumbentPipelineOf("default"), "default");
  assert.equal(incumbentPipelineOf("default+grounding"), "default");
  assert.equal(incumbentPipelineOf("default+two_pass_individual_then_relationship"), "default");
  assert.equal(incumbentPipelineOf("open_v1"), "open_v1");
  assert.equal(incumbentPipelineOf(undefined), "open_v1");
});
test("selectTargets under a default incumbent never selects an open_v1 hypothesis", () => {
  // candidate_missing is dominated by open_v1 hypotheses in the backlog; under a
  // default incumbent none of them are eligible (regression guard for the bug
  // that wasted a whole iteration on open_v1 no-ops).
  const targets = selectTargets({ candidate_missing: 1000, relation_not_derived: 5 }, [], [], 4, "default");
  for (const t of targets) {
    assert.notEqual(hypothesisPipeline(t.id), "open_v1", `expected no open_v1 hypothesis, got ${t.id}`);
  }
});
test("selectTargets under a default incumbent selects a live default-pipeline hypothesis", () => {
  // two_pass is classified 'default' but marked done (landed as the incumbent);
  // temporarily clear its done flag to prove default-pipeline hypotheses ARE
  // selected under a default incumbent (the pipeline-scoping fix), independent
  // of how many default hypotheses remain live in the backlog.
  const twoPass = SEED_BACKLOG.find((h) => h.id === "two_pass_individual_then_relationship");
  assert.ok(twoPass, "fixture assumption: two_pass hypothesis exists in the backlog");
  const savedDone = twoPass.done;
  twoPass.done = false;
  try {
    const targets = selectTargets(
      { candidate_missing: 85, relation_not_derived: 34, predicate_mismatch: 2 },
      [],
      [],
      3,
      "default",
    );
    assert.ok(
      targets.some((t) => t.id === "two_pass_individual_then_relationship"),
      `expected two_pass to be selected under the default incumbent, got ${targets.map((t) => t.id).join(", ")}`,
    );
  } finally {
    twoPass.done = savedDone;
  }
});
test("the live default-pipeline backlog hypothesis is classified default and selected under a default incumbent", () => {
  // rag, two_pass, and default_label_canonicalization landed (done);
  // default_coverage_completion + default_coverage_with_relations are blocked
  // (mechanical surfacing proven dead). The live default hypothesis is
  // default_relationship_object_recall, targeting the incumbent's dominant
  // failure stages (candidate_missing, relation_not_derived).
  const id = "default_relationship_object_recall";
  assert.equal(hypothesisPipeline(id), "default", `${id} should classify as a default-pipeline hypothesis`);
  assert.ok(
    SEED_BACKLOG.some((h) => h.id === id && !h.done && !h.blocked),
    `${id} should be a live (not done/blocked) backlog entry`,
  );
  const targets = selectTargets({ candidate_missing: 96, relation_not_derived: 7 }, [], [], 3, "default");
  const ids = targets.map((t) => t.id);
  assert.ok(ids.includes(id), `expected ${id} selected under the default incumbent, got ${ids.join(", ")}`);
  // the blocked/landed ones must NOT be selected
  assert.ok(!ids.includes("default_coverage_completion"), "blocked default_coverage_completion must not be selected");
  assert.ok(!ids.includes("default_coverage_with_relations"), "blocked default_coverage_with_relations must not be selected");
  assert.ok(!ids.includes("default_label_canonicalization"), "done default_label_canonicalization must not be selected");
});
test("pipeline-agnostic hypotheses are eligible under either incumbent", () => {
  assert.equal(hypothesisPipeline("per_source_confidence_bands"), "both");
  for (const incumbent of ["open_v1", "default"]) {
    const targets = selectTargets({}, [], [], SEED_BACKLOG.length, incumbent);
    assert.ok(
      targets.some((t) => t.id === "per_source_confidence_bands"),
      `expected per_source_confidence_bands eligible under ${incumbent}`,
    );
  }
});

console.log(`\n${passCount} passed, ${failCount} failed`);
if (failCount > 0) {
  process.exit(1);
}
