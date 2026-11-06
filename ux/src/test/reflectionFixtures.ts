/**
 * A schema relationship reflection proposal (#1411) on taxonomy "tax-1": every
 * change kind, with the reflection plan row the backend reads from each
 * operation's evidence.
 *
 * Mechanical: m-dup (remove-duplicate, p 0.9), m-rename (rename-predicate,
 * p 0.7), m-reverse (reverse, p 0.5), m-stale (reverse, p 0.95, stale),
 * m-blocked (rename-predicate, p 0.8, in use). Judgment: j-retarget (p 0.75),
 * j-compound (p 0.9). Conflict: c-rename (seq 8) renames "task needs tool" to
 * "task uses tool", which c-delete (seq 9) wants changed.
 */
import type { ProposedOperation } from "@/api/services/proposals";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";

type Reflection = NonNullable<ProposedOperation["reflection"]>;
type Option = Reflection["questions"][number]["options"][number];

/** Class labels the answers name, by class id. */
export const CLASS_IDS: Record<string, string> = {
  task: "class-task",
  tool: "class-tool",
  room: "class-room",
  project: "class-project",
};

function option(name: string, probability: number, marks: Partial<Option> = {}): Option {
  return {
    option: name,
    probability,
    class_id: CLASS_IDS[name] ?? null,
    current: false,
    plan: false,
    ...marks,
  };
}

function predicateOption(name: string, probability: number, marks: Partial<Option> = {}): Option {
  return { ...option(name, probability, marks), class_id: null };
}

function reflection(
  plan_kind: string,
  p: number,
  current: [string, string, string],
  replacement: string,
  questions: Record<string, Option[]>,
): Reflection {
  return {
    plan_kind,
    p,
    current: { source: current[0], predicate: current[1], target: current[2] },
    replacement,
    questions: Object.entries(questions).map(([question, options]) => ({ question, options })),
    evidence_pack: [
      "Design intent:\n  Tasks are filed in projects.",
      "Relationship types between task, tool",
    ],
  };
}

/** Answers that keep source and target and change the predicate. */
function predicateAnswers(
  source: string,
  current: string,
  plan: string,
  target: string,
  p: number,
) {
  return {
    source_for: [option(source, 0.95, { current: true, plan: true })],
    target_for: [option(target, 0.9, { current: true, plan: true })],
    predicate_for: [
      predicateOption(plan, p, { plan: true }),
      predicateOption(current, 1 - p, { current: true }),
    ],
  };
}

function reflectionOperation(
  id: string,
  seq: number,
  op: "update" | "delete",
  probability: number,
  refl: Reflection,
  overrides: Partial<ProposedOperation> = {},
): ProposedOperation {
  return createProposedOperation({
    id,
    seq,
    op,
    kind: "property",
    target_id: `prop-${id}`,
    fields: op === "update" ? { canonical_predicate: "uses" } : {},
    base:
      op === "delete"
        ? {
            id: `prop-${id}`,
            identifier: `${id}_type`,
            canonical_predicate: refl.current!.predicate,
            domain_class_id: CLASS_IDS[refl.current!.source],
            range_class_id: CLASS_IDS[refl.current!.target],
          }
        : { canonical_predicate: refl.current!.predicate },
    rationale: `Change ${seq}. Plan kind ${refl.plan_kind}, p ${probability.toFixed(2)}.`,
    evidence: [{ quote: "Sorting answers", plan_kind: refl.plan_kind }],
    probability,
    scope: "breaking",
    status: "pending",
    reflection: refl,
    ...overrides,
  });
}

export const retargetReflection = reflection(
  "retarget",
  0.75,
  ["task", "located_in", "room"],
  "project located_in room",
  {
    source_for: [
      option("project", 0.75, { plan: true }),
      option("task", 0.15, { current: true }),
      option("tool", 0.06),
      option("none", 0.04),
    ],
    target_for: [option("room", 0.9, { current: true, plan: true }), option("tool", 0.1)],
    predicate_for: [
      predicateOption("located_in", 0.8, { current: true, plan: true }),
      predicateOption("reverse:holds", 0.2),
    ],
  },
);

export function reflectionProposal() {
  const blockers = {
    edges: [
      {
        relationship_id: "rel-1",
        source: { id: "a", title: "A", class_ids: [], class_titles: [] },
        target: { id: "b", title: "B", class_ids: [], class_titles: [] },
        attributes: {},
      },
    ],
    replacements: [],
  };
  const operations = [
    reflectionOperation(
      "m-dup",
      1,
      "delete",
      0.9,
      reflection(
        "remove-duplicate",
        0.9,
        ["task", "needs", "tool"],
        "task requires tool",
        predicateAnswers("task", "needs", "requires", "tool", 0.9),
      ),
    ),
    reflectionOperation(
      "m-rename",
      2,
      "update",
      0.7,
      reflection(
        "rename-predicate",
        0.7,
        ["room", "holds", "tool"],
        "room stores tool",
        predicateAnswers("room", "holds", "stores", "tool", 0.7),
      ),
    ),
    reflectionOperation(
      "m-reverse",
      3,
      "delete",
      0.5,
      reflection(
        "reverse",
        0.5,
        ["tool", "in", "room"],
        "room holds tool",
        predicateAnswers("tool", "in", "reverse:holds", "room", 0.5),
      ),
    ),
    reflectionOperation(
      "m-stale",
      4,
      "delete",
      0.95,
      reflection(
        "reverse",
        0.95,
        ["tool", "at", "room"],
        "room has tool",
        predicateAnswers("tool", "at", "reverse:has", "room", 0.95),
      ),
      { stale: true },
    ),
    reflectionOperation(
      "m-blocked",
      5,
      "update",
      0.8,
      reflection(
        "rename-predicate",
        0.8,
        ["project", "has", "task"],
        "project contains task",
        predicateAnswers("project", "has", "contains", "task", 0.8),
      ),
      { blockers },
    ),
    reflectionOperation("j-retarget", 6, "update", 0.75, retargetReflection, {
      fields: { domain_class_id: "class-project" },
      base: { domain_class_id: "class-task" },
    }),
    reflectionOperation(
      "j-compound",
      7,
      "update",
      0.9,
      reflection("compound", 0.9, ["tool", "near", "room"], "room near project", {
        source_for: [option("room", 0.9, { plan: true }), option("tool", 0.1, { current: true })],
        target_for: [
          option("project", 0.92, { plan: true }),
          option("room", 0.08, { current: true }),
        ],
        predicate_for: [predicateOption("near", 1, { current: true, plan: true })],
      }),
    ),
    reflectionOperation(
      "c-rename",
      8,
      "update",
      0.6,
      reflection(
        "conflict",
        0.6,
        ["task", "needs_tool", "tool"],
        "task uses tool",
        predicateAnswers("task", "needs_tool", "uses", "tool", 0.6),
      ),
    ),
    reflectionOperation(
      "c-delete",
      9,
      "delete",
      0.55,
      reflection(
        "conflict",
        0.55,
        ["task", "uses", "tool"],
        "task wields tool",
        predicateAnswers("task", "uses", "wields", "tool", 0.55),
      ),
    ),
  ];
  return createChangeProposal({
    id: "proposal-1",
    taxonomy_id: "tax-1",
    title: "Reflection: Records (9 relationship changes)",
    source: "pipeline",
    status: "open",
    operations,
  });
}
