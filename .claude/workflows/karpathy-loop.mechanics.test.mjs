#!/usr/bin/env node
/**
 * Standalone mechanics check for karpathy-loop.js's pure decision-logic
 * functions (documentation/karpathy_loop_design.md §4.3/§6): `clamp`,
 * `meetsFloors`, `selectTargets`, `acceptGate`, `isMeasured`, `gateCandidates`
 * and `stopAfter`, the per-implementation backlogs and gate margins, and the
 * prompts the agents are given.
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
    `${declarations}\nglobalThis.__mechanics = { clamp, meetsFloors, selectTargets, acceptGate, BACKLOGS, GATE_MARGINS, TARGET_NAME, FAILURE_KINDS, FROZEN_PATHS, DEFAULT_HOLDOUT_FLOORS, evaluatePrompt, experimentPrompt, verifyPrompt, decidePrompt, ledgerReadPrompt, isMeasured, hasGuard, guardAgreesWithMargins, gateCandidates, stopAfter };`,
    sandbox,
    { filename: SOURCE_PATH },
  );
  return sandbox.__mechanics;
}

const { clamp, meetsFloors, selectTargets, acceptGate, BACKLOGS, GATE_MARGINS, TARGET_NAME, FAILURE_KINDS, FROZEN_PATHS, DEFAULT_HOLDOUT_FLOORS, evaluatePrompt, experimentPrompt, verifyPrompt, decidePrompt, ledgerReadPrompt, isMeasured, hasGuard, guardAgreesWithMargins, gateCandidates, stopAfter } =
  loadPureDeclarations();

// The measured margins of the `default` implementation: the gate tests below
// are written against them.
const DEFAULT_MARGINS = GATE_MARGINS.default;
const { epsilon: EPSILON, holdoutSlack: HOLDOUT_SLACK, coverageSlack: COVERAGE_SLACK, guardSlack: GUARD_SLACK } = DEFAULT_MARGINS;
const SEED_BACKLOG = BACKLOGS.default;
const NOT_APPLICABLE = { applies: false, reason: "the triple corpus has no recordings of the find_then_type implementation" };

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
function gate(candidate, incumbent, margins = DEFAULT_MARGINS) {
  return acceptGate(candidate, incumbent, margins);
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
  // incumbent HOLDOUT_SLACK and candidate 0: the gate computes 0 < slack - slack, which is false.
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
  assert.equal(acceptGate.length, 3);
});

test("acceptGate accepts a typed F1 gain just over epsilon and rejects one exactly at it", () => {
  assert.equal(gate(candidateAt({ typed_f1: EPSILON + 0.001 }), incumbentAt({ typed_f1: 0 })).passes, true);
  assert.equal(gate(candidateAt({ typed_f1: EPSILON }), incumbentAt({ typed_f1: 0 })).passes, false);
});
test("acceptGate tolerates a found F1 dip exactly at coverageSlack and a guard drop exactly at its slack", () => {
  const dip = gate(candidateAt({ f1: 0, typed_f1: 0.4 }), incumbentAt({ f1: COVERAGE_SLACK, typed_f1: 0.3 }));
  assert.equal(dip.passes, true);
  const guard = gate(candidateAt({ f1: 0.6, guard: 0 }), incumbentAt({ guard: GUARD_SLACK }));
  assert.equal(guard.passes, true);
});
test("acceptGate fails closed when any number it reads is missing on either side", () => {
  const good = candidateAt({ f1: 0.6 });
  for (const [group, key] of [["dev", "f1"], ["dev", "typed_f1"], ["holdout", "typed_f1"], ["guard", "strict_f1"]]) {
    for (const side of ["candidate", "incumbent"]) {
      const broken = side === "candidate" ? candidateAt({ f1: 0.6 }) : incumbentAt();
      delete broken[group][key];
      const result = side === "candidate" ? gate(broken, incumbentAt()) : gate(good, broken);
      assert.equal(result.passes, false, `${side} without ${group}.${key} passed`);
      assert.ok(result.reasons[0].includes(`${side} ${group}.${key}`));
    }
  }
  const noGuard = candidateAt({ f1: 0.6 });
  delete noGuard.guard;
  assert.equal(gate(noGuard, incumbentAt()).passes, false);
  assert.equal(gate(candidateAt({ f1: Number.NaN }), incumbentAt()).passes, false);
});

// -- per-implementation margins and the guard that may not apply -----------

test("every implementation the loop can refine has both a backlog and gate margins", () => {
  assert.deepEqual(Object.keys(BACKLOGS).sort(), Object.keys(GATE_MARGINS).sort());
  for (const name of Object.keys(BACKLOGS)) assert.ok(TARGET_NAME.test(name), `${name} is not a registry name`);
});
test("every set of margins says what it was measured from; a provisional one names the measurement it lacks", () => {
  for (const [name, margins] of Object.entries(GATE_MARGINS)) {
    for (const key of ["epsilon", "holdoutSlack", "coverageSlack"]) {
      assert.ok(Number.isFinite(margins[key]) && margins[key] > 0, `${name}.${key}`);
    }
    assert.ok(margins.basis, `${name} margins have no basis`);
    assert.equal(typeof margins.provisional, "boolean");
    if (margins.provisional) assert.ok(margins.missing, `${name} margins are provisional but name no missing measurement`);
  }
});
test("the default margins are the measured ones; find_then_type's are provisional and no narrower", () => {
  assert.equal(DEFAULT_MARGINS.provisional, false);
  assert.deepEqual([EPSILON, HOLDOUT_SLACK, COVERAGE_SLACK, GUARD_SLACK], [0.02, 0.04, 0.05, 0.02]);
  const provisional = GATE_MARGINS.find_then_type;
  assert.equal(provisional.provisional, true);
  assert.ok(provisional.missing.includes("re-recording"));
  // Above the typing-only spreads they were set from (0.011 on dev, 0.039 on holdout).
  assert.ok(provisional.epsilon > 0.011 && provisional.epsilon >= EPSILON);
  assert.ok(provisional.holdoutSlack > 0.039 && provisional.holdoutSlack >= HOLDOUT_SLACK);
  assert.equal(provisional.guardSlack, null);
});
test("acceptGate reads no guard number when the guard does not apply to the implementation", () => {
  const margins = GATE_MARGINS.find_then_type;
  const incumbent = { ...incumbentAt({ f1: 0.5, typed_f1: 0.46, holdout: 0.48 }), guard: NOT_APPLICABLE };
  const better = { ...candidateAt({ f1: 0.5, typed_f1: 0.46 + margins.epsilon + 0.001, holdout: 0.48 }), guard: NOT_APPLICABLE };
  const result = gate(better, incumbent, margins);
  assert.equal(result.passes, true);
  assert.equal(result.reasons.length, 0);
  // The benchmark rules still hold.
  const flat = { ...candidateAt({ f1: 0.5, typed_f1: 0.46 + margins.epsilon, holdout: 0.48 }), guard: NOT_APPLICABLE };
  assert.equal(gate(flat, incumbent, margins).passes, false);
  const collapsed = { ...better, holdout: { typed_f1: 0.48 - margins.holdoutSlack - 0.01 } };
  assert.equal(gate(collapsed, incumbent, margins).passes, false);
});
test("acceptGate fails a candidate that reports a guard the incumbent's measurement says does not apply", () => {
  const margins = GATE_MARGINS.find_then_type;
  const incumbent = { ...incumbentAt({ typed_f1: 0.3 }), guard: NOT_APPLICABLE };
  const borrowed = candidateAt({ typed_f1: 0.5, guard: 0.93 });
  const result = gate(borrowed, incumbent, margins);
  assert.equal(result.passes, false);
  assert.ok(result.reasons[0].includes("not measured the same way"));
  const none = candidateAt({ typed_f1: 0.5 });
  delete none.guard;
  assert.equal(gate(none, incumbent, margins).passes, false);
});
test("acceptGate never treats a guard as not applicable on the candidate's word alone", () => {
  const dodged = { ...candidateAt({ f1: 0.6 }), guard: NOT_APPLICABLE };
  const result = gate(dodged, incumbentAt());
  assert.equal(result.passes, false);
  assert.ok(result.reasons[0].includes("candidate guard.strict_f1"));
});
test("acceptGate fails closed without margins, and without a guard margin where the guard applies", () => {
  assert.equal(acceptGate(candidateAt({ f1: 0.6 }), incumbentAt(), undefined).passes, false);
  const result = acceptGate(candidateAt({ f1: 0.6 }), incumbentAt(), GATE_MARGINS.find_then_type);
  assert.equal(result.passes, false);
  assert.ok(result.reasons[0].includes("guardSlack"));
});

// -- gateCandidates (§4.3 step 5) and what follows a decision ---------------

function verifiedAt(hypothesisId, measures) {
  return { candidate: { hypothesisId, ...candidateAt(measures) }, verdict: { verdict: "pass" } };
}

test("gateCandidates gates every verified candidate: a passing one is not lost to a higher-typed one that fails", () => {
  const incumbent = incumbentAt({ f1: 0.5, typed_f1: 0.3 });
  // A: typed +0.03 but found -0.06 (beyond coverageSlack). B: found +0.05, typed +0.01.
  const a = verifiedAt("a", { f1: 0.44, typed_f1: 0.33 });
  const b = verifiedAt("b", { f1: 0.55, typed_f1: 0.31 });
  const { gated, best } = gateCandidates([a, b], incumbent, DEFAULT_MARGINS);
  assert.equal(gated.length, 2);
  assert.equal(gated[0].gate.passes, false);
  assert.equal(best.candidate.hypothesisId, "b");
});
test("gateCandidates accepts the highest dev typed F1 among those that pass, then the highest found F1", () => {
  const incumbent = incumbentAt({ f1: 0.5, typed_f1: 0.3 });
  const low = verifiedAt("low", { f1: 0.6, typed_f1: 0.35 });
  const high = verifiedAt("high", { f1: 0.55, typed_f1: 0.4 });
  const tie = verifiedAt("tie", { f1: 0.6, typed_f1: 0.4 });
  assert.equal(gateCandidates([low, high], incumbent, DEFAULT_MARGINS).best.candidate.hypothesisId, "high");
  assert.equal(gateCandidates([high, tie, low], incumbent, DEFAULT_MARGINS).best.candidate.hypothesisId, "tie");
});
test("gateCandidates accepts nothing when no candidate passes, or none was verified", () => {
  const incumbent = incumbentAt({ f1: 0.5, typed_f1: 0.3 });
  assert.equal(gateCandidates([verifiedAt("flat", { f1: 0.5, typed_f1: 0.3 })], incumbent, DEFAULT_MARGINS).best, null);
  assert.equal(gateCandidates([], incumbent, DEFAULT_MARGINS).best, null);
});
test("gateCandidates judges by the margins it is given: a gain inside the provisional epsilon is not accepted", () => {
  const incumbent = incumbentAt({ f1: 0.5, typed_f1: 0.3 });
  const gain = verifiedAt("gain", { f1: 0.5, typed_f1: 0.3 + EPSILON + 0.005 });
  assert.equal(gateCandidates([gain], incumbent, DEFAULT_MARGINS).best.candidate.hypothesisId, "gain");
  const wider = { ...GATE_MARGINS.find_then_type, guardSlack: GUARD_SLACK };
  assert.equal(gateCandidates([gain], incumbent, wider).best, null);
});
test("isMeasured needs a scored status and all three measurements", () => {
  const scored = { measurementStatus: "scored", ...candidateAt() };
  assert.equal(isMeasured(scored), true);
  assert.equal(isMeasured({ ...scored, measurementStatus: "stale" }), false);
  for (const group of ["dev", "holdout", "guard"]) {
    const partial = { ...scored };
    delete partial[group];
    assert.equal(isMeasured(partial), false, `measured without ${group}`);
  }
  assert.equal(isMeasured(null), false);
  assert.equal(isMeasured({ ...scored, guard: NOT_APPLICABLE }), true, "a guard that does not apply is still a measurement");
});
test("a guard that applies but carries no number is not a measurement", () => {
  const scored = { measurementStatus: "scored", ...candidateAt() };
  assert.equal(isMeasured({ ...scored, guard: { applies: true } }), false);
  assert.equal(hasGuard({ applies: true }), false);
  assert.equal(hasGuard({ applies: true, strict_f1: 0.9 }), true);
  assert.equal(hasGuard({ strict_f1: 0.9 }), true);
  assert.equal(hasGuard(NOT_APPLICABLE), true);
  assert.equal(hasGuard(undefined), false);
});
test("whether the guard applies is the implementation's fact: a report cannot switch it off or on", () => {
  assert.equal(guardAgreesWithMargins({ applies: true, strict_f1: 0.9 }, GATE_MARGINS.default), true);
  assert.equal(guardAgreesWithMargins(NOT_APPLICABLE, GATE_MARGINS.default), false);
  assert.equal(guardAgreesWithMargins(NOT_APPLICABLE, GATE_MARGINS.find_then_type), true);
  assert.equal(guardAgreesWithMargins({ applies: true, strict_f1: 0.9 }, GATE_MARGINS.find_then_type), false);
});
test("stopAfter stops on an accept (promote to main first) and on a plateau, and not otherwise", () => {
  assert.ok(stopAfter(true, 0, 3, "experiment/x").reason.includes("promote experiment/x to main"));
  assert.ok(stopAfter(false, 3, 3, "experiment/x").reason.includes("plateau"));
  assert.equal(stopAfter(false, 2, 3, "experiment/x"), null);
});

// -- selectTargets (§4.3 step 2) -----------------------------------------

test("every backlog hypothesis names only failure kinds the benchmark reports", () => {
  for (const [implementation, backlog] of Object.entries(BACKLOGS)) {
    for (const hyp of backlog) {
      assert.ok(hyp.id && hyp.summary, `${implementation}: a hypothesis needs an id and a summary`);
      for (const kind of hyp.kinds) {
        assert.ok(FAILURE_KINDS.includes(kind), `${implementation}/${hyp.id}: unknown failure kind ${kind}`);
      }
    }
    const ids = backlog.map((h) => h.id);
    assert.equal(new Set(ids).size, ids.length, `${implementation}: hypothesis ids are unique`);
  }
});
test("every benchmark failure kind has at least one hypothesis in every backlog", () => {
  for (const [implementation, backlog] of Object.entries(BACKLOGS)) {
    for (const kind of FAILURE_KINDS) {
      assert.ok(backlog.some((h) => h.kinds.includes(kind)), `${implementation}: no hypothesis for ${kind}`);
    }
  }
});
test("the find_then_type backlog does not re-list what that implementation does by design, or what was tried", () => {
  const ids = BACKLOGS.find_then_type.map((h) => h.id);
  for (const done of ["full_class_catalog", "class_definitions_in_prompt", "statement_individuals", "one_class_per_individual_at_merge"]) {
    assert.ok(!ids.includes(done), `${done} is what find_then_type already does`);
  }
  assert.ok(ids.includes("type_from_all_occurrences"));
  for (const hyp of BACKLOGS.find_then_type) {
    assert.ok(!/whole (class )?definition/i.test(hyp.summary), `${hyp.id} re-lists whole definitions`);
  }
});
test("selectTargets draws from the backlog it is given and from no other", () => {
  const counts = { missed_supporting: 67, spurious: 93, missed_core: 18, mistyped: 15 };
  const own = new Set(BACKLOGS.find_then_type.map((h) => h.id));
  const targets = selectTargets(counts, [], [], 4, BACKLOGS.find_then_type);
  assert.ok(targets.length > 0);
  for (const t of targets) assert.ok(own.has(t.id), `${t.id} is not a find_then_type hypothesis`);
});
test("selectTargets on find_then_type's own failure counts starts with what the gate can credit", () => {
  // The committed recording's dev counts: relationships are the largest, and
  // every relationship hypothesis is blocked.
  const counts = { relationship_missed: 109, spurious: 93, missed_supporting: 67, missed_core: 18, mistyped: 15, excluded_extracted: 9 };
  const targets = selectTargets(counts, [], [], 3, BACKLOGS.find_then_type);
  assert.equal(targets.length, 3);
  assert.equal(targets[0].targetKind, "spurious");
  assert.ok(targets.some((t) => t.id === "type_from_all_occurrences"));
  for (const t of targets) assert.ok(!BACKLOGS.find_then_type.find((h) => h.id === t.id).blocked);
});
test("selectTargets ranks failure kinds by count (highest first)", () => {
  const [target] = selectTargets({ spurious: 3, mistyped: 40 }, [], [], 1, SEED_BACKLOG);
  assert.equal(target.targetKind, "mistyped");
});
test("selectTargets excludes hypotheses the ledger already rejected", () => {
  const rejected = SEED_BACKLOG.filter((h) => h.kinds.includes("mistyped")).map((h) => h.id);
  const targets = selectTargets({ mistyped: 40 }, rejected, [], 2, SEED_BACKLOG);
  for (const t of targets) assert.ok(!rejected.includes(t.id), `${t.id} was rejected`);
});
test("selectTargets excludes hypotheses the ledger already accepted (merged into the incumbent)", () => {
  const accepted = ["full_class_catalog"];
  const targets = selectTargets({ mistyped: 40 }, [], accepted, SEED_BACKLOG.length, SEED_BACKLOG);
  assert.ok(!targets.some((t) => t.id === "full_class_catalog"));
});
test("selectTargets returns nothing once every seeded hypothesis is decided", () => {
  const all = SEED_BACKLOG.map((h) => h.id);
  assert.equal(selectTargets({ mistyped: 40 }, all, [], 3, SEED_BACKLOG).length, 0);
  assert.equal(selectTargets({ mistyped: 40 }, [], all, 3, SEED_BACKLOG).length, 0);
});
test("selectTargets never selects a hypothesis marked blocked or done", () => {
  const first = SEED_BACKLOG.find((h) => h.kinds.includes("mistyped"));
  for (const flag of ["blocked", "done"]) {
    first[flag] = true;
    try {
      const targets = selectTargets({ mistyped: 40 }, [], [], SEED_BACKLOG.length, SEED_BACKLOG);
      assert.ok(!targets.some((t) => t.id === first.id), `${first.id} is ${flag}`);
    } finally {
      delete first[flag];
    }
  }
});
test("selectTargets never selects the same hypothesis twice and backfills to the requested count", () => {
  const targets = selectTargets({ mistyped: 40, missed_core: 30 }, [], [], 4, SEED_BACKLOG);
  assert.equal(targets.length, 4);
  assert.equal(new Set(targets.map((t) => t.id)).size, 4);
});
test("selectTargets backfills from the rest of the backlog when the failure counts name nothing", () => {
  const open = SEED_BACKLOG.filter((h) => !h.blocked);
  const targets = selectTargets({}, [], [], SEED_BACKLOG.length, SEED_BACKLOG);
  assert.equal(targets.length, open.length);
  for (const t of targets) assert.ok(FAILURE_KINDS.includes(t.targetKind), `${t.id}: ${t.targetKind}`);
});
test("selectTargets never spends a slot on a hypothesis the gate cannot credit", () => {
  // Missing relationships outnumber every individual failure kind at baseline,
  // but the gate reads no relationship measure.
  const counts = { relationship_missed: 133, missed_supporting: 85, spurious: 57, missed_core: 41, mistyped: 36 };
  const targets = selectTargets(counts, [], [], SEED_BACKLOG.length, SEED_BACKLOG);
  assert.equal(targets[0].targetKind, "missed_supporting");
  for (const id of ["cross_chunk_relationships", "per_source_confidence_bands"]) {
    assert.ok(SEED_BACKLOG.find((h) => h.id === id).blocked, `${id} is not blocked`);
    assert.ok(!targets.some((t) => t.id === id), `${id} was selected`);
  }
});

// -- prompts: the measurement layer stays frozen ---------------------------

const DEFAULT_TARGET = { implementation: "default", configuration: "extraction-openrouter-default", model: "google/gemini-3-flash-preview" };
const FTT_TARGET = { implementation: "find_then_type", configuration: "extraction-find-then-type", model: "claude-haiku-5-5" };
const DEFAULT_FLAGS = "--implementation default --configuration extraction-openrouter-default";
const FTT_FLAGS = "--implementation find_then_type --configuration extraction-find-then-type";
const TOURNAMENT = "python scripts/quality_tournament.py --pipeline individual --passes 1 --restarts 1";

const EVALUATION = {
  ...DEFAULT_TARGET,
  errorReportPath: "experiments/reports/tournament_x_benchmark.json",
  dev: { typed_f1: 0.2, f1: 0.4 },
  holdout: { typed_f1: 0.1 },
  guard: { applies: true, variant: "default", strict_f1: 0.9 },
  staleElsewhere: ["open_v1"],
};
const FTT_EVALUATION = { ...EVALUATION, ...FTT_TARGET, guard: NOT_APPLICABLE };
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
  guard: { applies: true, variant: "default", strict_f1: 0.9 },
};
const FTT_CANDIDATE = { ...CANDIDATE, hypothesisId: "type_from_all_occurrences", guard: NOT_APPLICABLE };
const HYPOTHESIS = { id: "x", summary: "y", targetKind: "mistyped" };

// The JSON a decide prompt hands to `ledger.py append --stdin`.
function ledgerEntryOf(prompt) {
  const line = prompt.split("\n").find((l) => l.startsWith('{"experiment_id"'));
  assert.ok(line, "the prompt carries no ledger entry");
  return JSON.parse(line);
}

test("the experimenter and the verifier are both given every frozen path", () => {
  const experiment = experimentPrompt(HYPOTHESIS, EVALUATION);
  const verify = verifyPrompt(CANDIDATE, DEFAULT_TARGET, []);
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
test("a recording may be recorded again but never deleted: the verifier fails a deleted cassette", () => {
  const verify = verifyPrompt(FTT_CANDIDATE, FTT_TARGET, []);
  assert.ok(verify.includes("--diff-filter=D"));
  assert.ok(verify.includes("local-server/tests/integration/fixtures/cassettes/"));
  assert.ok(experimentPrompt(HYPOTHESIS, FTT_EVALUATION).includes("never delete one"));
});
test("the cassette directories are not frozen: an experiment that changes a prompt must re-record them", () => {
  assert.ok(!FROZEN_PATHS.some((p) => p.includes("cassettes")));
  const experiment = experimentPrompt(HYPOTHESIS, EVALUATION);
  assert.ok(experiment.includes("scripts/record_default_cassettes.py --record"));
  assert.ok(experiment.includes(`scripts/benchmark_replay.py --record --spend ${DEFAULT_FLAGS}`));
});
test("the incumbent and each candidate are measured by the same steps", () => {
  const evaluate = evaluatePrompt(DEFAULT_TARGET);
  const experiment = experimentPrompt(HYPOTHESIS, EVALUATION);
  const step = `${TOURNAMENT} ${DEFAULT_FLAGS}`;
  assert.ok(evaluate.includes(step) && experiment.includes(step));
  assert.ok(evaluate.includes("STALE CASSETTES") && experiment.includes("STALE CASSETTES"));
});

// -- prompts: what is measured is the chosen implementation and configuration --

test("with no target in args the evaluate step names none: the scripts resolve the registry's defaults", () => {
  const evaluate = evaluatePrompt({ implementation: null, configuration: null });
  assert.ok(evaluate.includes(`\`${TOURNAMENT}\``), "the tournament command carries a flag nobody asked for");
  assert.ok(!evaluate.includes("--implementation") && !evaluate.includes("--configuration"));
  assert.ok(evaluate.includes("the pipeline registry's default implementation"));
  assert.ok(!evaluate.includes("`default` pipeline"), "the prompt spells a default itself");
  // What was resolved comes back from the benchmark report, not from the prompt.
  assert.ok(evaluate.includes("Set `implementation`, `configuration` and `model` to the benchmark JSON's fields"));
});
test("an implementation named in args is the one every step measures, records and verifies", () => {
  const evaluate = evaluatePrompt({ implementation: "find_then_type", configuration: null });
  assert.ok(evaluate.includes(`${TOURNAMENT} --implementation find_then_type\``));
  assert.ok(evaluate.includes("the `find_then_type` implementation"));

  const experiment = experimentPrompt(HYPOTHESIS, FTT_EVALUATION);
  assert.ok(experiment.includes("refining the `find_then_type`"));
  assert.ok(experiment.includes("`extraction-find-then-type` configuration"));
  assert.ok(experiment.includes("claude-haiku-5-5"));
  assert.ok(experiment.includes(`${TOURNAMENT} ${FTT_FLAGS}`));
  assert.ok(experiment.includes(`scripts/benchmark_replay.py --record --spend ${FTT_FLAGS}`));
  assert.ok(!experiment.includes("refining the default"));

  const verify = verifyPrompt(FTT_CANDIDATE, FTT_TARGET, []);
  assert.ok(verify.includes(`${TOURNAMENT} ${FTT_FLAGS}`));
  assert.ok(verify.includes('"find_then_type"') && verify.includes('"extraction-find-then-type"'));
});
test("the guard is read from the benchmark report's guard object, never from another implementation's row", () => {
  for (const prompt of [evaluatePrompt(FTT_TARGET), experimentPrompt(HYPOTHESIS, FTT_EVALUATION)]) {
    assert.ok(prompt.includes("benchmark JSON's `guard` object"));
    assert.ok(prompt.includes("no row of the scoreboard"));
    assert.ok(!prompt.includes("`default` row"));
  }
  const experiment = experimentPrompt(HYPOTHESIS, FTT_EVALUATION);
  assert.ok(experiment.includes("triple-corpus guard not applicable"));
  assert.ok(!experiment.includes("guard strict-F1 undefined"));
  const verify = verifyPrompt(FTT_CANDIDATE, FTT_TARGET, []);
  assert.ok(verify.includes("guard not applicable"));
  assert.ok(verify.includes("have `applies` false"));
  assert.ok(!verify.includes("undefined"));
});
test("an experiment that touches a shared part owes every recording it made stale, and the verifier replays them all", () => {
  const experiment = experimentPrompt(HYPOTHESIS, FTT_EVALUATION);
  assert.ok(experiment.includes("python scripts/benchmark_replay.py --all"));
  assert.ok(experiment.includes("each other benchmark target that went stale"));
  assert.ok(experiment.includes("scripts/record_default_cassettes.py --record"));
  for (const [candidate, target] of [[CANDIDATE, DEFAULT_TARGET], [FTT_CANDIDATE, FTT_TARGET]]) {
    const verify = verifyPrompt(candidate, target, []);
    assert.ok(verify.includes("python scripts/benchmark_replay.py --all --json"));
    assert.ok(verify.includes("every benchmark target that has recordings, not only this one"));
    assert.ok(verify.includes("otherTargets"));
  }
});
test("recordings already stale on main are named, and a candidate may add none", () => {
  const experiment = experimentPrompt(HYPOTHESIS, EVALUATION);
  assert.ok(experiment.includes("Already stale on `main`, before your change, and not yours to record: open_v1."));
  const verify = verifyPrompt(CANDIDATE, DEFAULT_TARGET, ["open_v1"]);
  assert.ok(verify.includes("may name nothing but what was already stale"));
  assert.ok(verify.includes("(open_v1)"));
  assert.ok(verifyPrompt(CANDIDATE, DEFAULT_TARGET, []).includes("(nothing)"));
  assert.ok(verifyPrompt(CANDIDATE, DEFAULT_TARGET, undefined).includes("(nothing)"));
});
test("the ledger is read for the implementation being refined", () => {
  const prompt = ledgerReadPrompt("find_then_type");
  assert.ok(prompt.includes("ledger.py rejected-hypotheses --implementation find_then_type"));
  assert.ok(prompt.includes("ledger.py accepted-hypotheses --implementation find_then_type"));
});

test("the verifier reproduces every number the gate reads", () => {
  const verify = verifyPrompt({ ...CANDIDATE, guard: { applies: true, strict_f1: 0.9, soft_f1: 0.95 } }, DEFAULT_TARGET, []);
  assert.ok(verify.includes("holdout typed_f1"));
  assert.ok(verify.includes(`${TOURNAMENT} ${DEFAULT_FLAGS}`));
  assert.ok(verify.includes("claimed guard strict-F1 as its `strict_f1`"));
  assert.ok(verify.includes("guard strict-F1 0.9, guard soft-F1 0.95"));
});
test("an accepted candidate is merged without checking a branch out in the repository root", () => {
  const decide = decidePrompt(CANDIDATE, "accepted", "ok", 1, "experiment/x", DEFAULT_TARGET, DEFAULT_MARGINS, []);
  assert.ok(decide.includes("git worktree add"));
  assert.ok(!decide.includes("git checkout experiment/x"));
  assert.ok(decide.includes("ledger.py append --stdin"));
});
test("a ledger entry records what was refined, the margins it was judged by, and a guard that did not apply", () => {
  const others = [{ implementation: "default", configuration: "extraction-openrouter-default", status: "scored", devTypedF1: 0.114, devFoundF1: 0.411 }];
  const entry = ledgerEntryOf(decidePrompt(FTT_CANDIDATE, "rejected", "no gain", 2, "experiment/x", FTT_TARGET, GATE_MARGINS.find_then_type, others));
  assert.equal(entry.experiment_id, "2-find_then_type-type_from_all_occurrences");
  assert.equal(entry.implementation, "find_then_type");
  assert.equal(entry.configuration, "extraction-find-then-type");
  assert.equal(entry.model, "claude-haiku-5-5");
  assert.equal(entry.variant, "find_then_type+type_from_all_occurrences");
  assert.equal(entry.guard.applies, false);
  assert.ok(entry.guard.reason);
  assert.equal(entry.margins.provisional, true);
  assert.equal(entry.margins.epsilon, GATE_MARGINS.find_then_type.epsilon);
  assert.equal(entry.margins.guard_slack, null);
  assert.equal(entry.other_targets[0].implementation, "default");

  const measured = ledgerEntryOf(decidePrompt(CANDIDATE, "accepted", "ok", 1, "experiment/x", DEFAULT_TARGET, DEFAULT_MARGINS, []));
  assert.equal(measured.implementation, "default");
  assert.equal(measured.configuration, "extraction-openrouter-default");
  assert.equal(measured.guard.strict_f1, 0.9);
  assert.equal(measured.margins.provisional, false);
});
test("a deferred candidate is discarded without a ledger entry; an unmeasured one is recorded with null measures", () => {
  const deferred = decidePrompt(CANDIDATE, "deferred", "another scored higher", 1, "experiment/x", DEFAULT_TARGET, DEFAULT_MARGINS, []);
  assert.ok(!deferred.includes("ledger.py append"));
  assert.ok(deferred.includes("git worktree remove --force /tmp/wt"));
  const unmeasured = { ...CANDIDATE, measurementStatus: "stale" };
  for (const group of ["dev", "holdout", "guard"]) delete unmeasured[group];
  const recorded = decidePrompt(unmeasured, "unmeasured", "not measured (stale)", 1, "experiment/x", DEFAULT_TARGET, DEFAULT_MARGINS, []);
  assert.ok(recorded.includes('"dev":null,"holdout":null'));
  assert.ok(recorded.includes('"decision":"unmeasured"'));
  assert.ok(recorded.includes("ledger.py append --stdin"));
  assert.ok(recorded.includes("git worktree remove --force /tmp/wt"));
  const entry = ledgerEntryOf(recorded);
  assert.equal(entry.guard, null);
  assert.equal(entry.implementation, "default");
});

console.log(`\n${passCount} passed, ${failCount} failed`);
if (failCount > 0) {
  process.exit(1);
}
