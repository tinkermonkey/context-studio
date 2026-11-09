import { describe, it, expect } from "vitest";
import { createProposedOperation } from "@/api/services/__tests__/fixtures/proposals.fixtures";
import { reflectionProposal, retargetReflection } from "@/test/reflectionFixtures";
import {
  bestAlternative,
  conflictClusters,
  conflictedIds,
  contradicts,
  defaultGroupBy,
  isBulkEligible,
  isPickable,
  kindOf,
  mechanicalAtOrAbove,
  offersGroupBy,
  pRangeLabel,
  optionDefinition,
  pickOutcome,
  tieredOrder,
} from "../tieredModel";

const ops = () => reflectionProposal().operations;
const byId = (id: string) => ops().find((o) => o.id === id)!;

describe("kinds", () => {
  it("reads the reflection's kind, else the rationale's", () => {
    expect(kindOf(byId("j-compound"))).toBe("compound");
    const legacy = createProposedOperation({ rationale: "Plan kind reverse, p 0.4." });
    expect(kindOf(legacy)).toBe("reverse");
    expect(kindOf(createProposedOperation())).toBeUndefined();
  });

  it("never bulk-decides judgment or conflict kinds", () => {
    expect(
      ops()
        .filter((o) => isBulkEligible(o))
        .map((o) => o.id),
    ).toEqual(["m-dup", "m-rename", "m-reverse", "m-stale", "m-blocked"]);
    expect(isBulkEligible(createProposedOperation())).toBe(true);
  });

  it("defaults to change kind only with reflection data", () => {
    expect(defaultGroupBy(ops())).toBe("kind");
    const legacy = createProposedOperation({ rationale: "Plan kind reverse, p 0.4." });
    expect(defaultGroupBy([legacy])).toBe("sequence");
    expect(offersGroupBy([legacy])).toBe(true);
    expect(offersGroupBy([createProposedOperation()])).toBe(false);
  });

  it("thresholds mechanical, fresh, unblocked operations only", () => {
    expect(mechanicalAtOrAbove(ops(), 0).map((o) => o.id)).toEqual([
      "m-dup",
      "m-rename",
      "m-reverse",
    ]);
  });

  it("labels a p range", () => {
    expect(pRangeLabel([byId("m-reverse"), byId("m-stale")])).toBe("p 0.50–0.95");
    expect(pRangeLabel([createProposedOperation({ probability: null })])).toBe("p —");
  });
});

describe("conflictClusters", () => {
  it("clusters a conflict with the operation whose type its change lands on", () => {
    const clusters = conflictClusters(ops());
    expect(clusters.map((c) => c.operations.map((o) => o.id))).toEqual([["c-rename", "c-delete"]]);
  });

  it("leaves out a delete that only names a conflict's type as its replacement", () => {
    const dependent = createProposedOperation({
      id: "x",
      seq: 10,
      op: "delete",
      kind: "property",
      target_id: "prop-x",
      proposed_replacement_id: "prop-c-delete",
    });
    const clusters = conflictClusters([...ops(), dependent]);
    expect(clusters[0].operations.map((o) => o.id)).toEqual(["c-rename", "c-delete"]);
    expect(conflictedIds([...ops(), dependent])).toEqual(new Set(["c-rename", "c-delete"]));
  });

  it("pulls in a mechanical change whose replacement is a conflict's current triple", () => {
    const linked = { ...byId("m-rename"), id: "m-linked" };
    linked.reflection = {
      ...linked.reflection!,
      current: { source: "task", predicate: "employs", target: "tool" },
      replacement: "task uses tool",
    };
    const conflicted = conflictedIds([...ops(), linked]);
    expect(conflicted.has("m-linked")).toBe(true);
    expect(isBulkEligible(linked, conflicted)).toBe(false);
    expect(mechanicalAtOrAbove([linked], 0, conflicted)).toEqual([]);
  });

  it("keeps a lone conflict as its own cluster", () => {
    expect(conflictClusters([byId("c-delete")]).map((c) => c.id)).toEqual(["c-delete"]);
  });
});

describe("pickOutcome", () => {
  it("is a plain accept without picks", () => {
    expect(pickOutcome(retargetReflection)).toMatchObject({
      triple: "project located_in room",
      changed: false,
      keepsCurrent: false,
      fields: undefined,
      chosenAlternative: undefined,
    });
  });

  it("makes no edit when a class option has no class id (older proposals)", () => {
    const legacy = {
      ...retargetReflection,
      questions: retargetReflection.questions.map((q) => ({
        ...q,
        options: q.options.map((o) => ({ ...o, class_id: null })),
      })),
    };
    const outcome = pickOutcome(legacy, { predicate_for: "reverse:holds" });
    expect(outcome?.changed).toBe(true);
    expect(outcome?.fields).toBeUndefined();
  });
});

describe("bestAlternative", () => {
  it("is the runner-up of a question the plan changed", () => {
    expect(bestAlternative(retargetReflection)).toEqual({
      question: "source_for",
      option: "task",
      probability: 0.15,
      current: true,
    });
  });

  it("is the current answer a renamed predicate replaced", () => {
    expect(bestAlternative(byId("m-dup").reflection!)).toEqual({
      question: "predicate_for",
      option: "needs",
      probability: expect.closeTo(0.1, 5),
      current: true,
    });
  });
});

describe("picks without class ids", () => {
  const withoutIds = (reflection: typeof retargetReflection) => ({
    ...reflection,
    questions: reflection.questions.map((q) => ({
      ...q,
      options: q.options.map((o) => ({ ...o, class_id: null })),
    })),
  });

  it("a predicate that keeps the pair is a predicate-only edit", () => {
    const rename = withoutIds(byId("m-rename").reflection!);
    rename.questions[2].options.push({
      option: "keeps",
      probability: 0.05,
      class_id: null,
      current: false,
      plan: false,
    });
    const outcome = pickOutcome(rename, { predicate_for: "keeps" });
    expect(outcome).toMatchObject({ changed: true, pair: "same" });
    expect(outcome?.fields).toEqual({ canonical_predicate: "keeps" });
    expect(isPickable(rename, "predicate_for", rename.questions[2].options[2])).toBe(true);
  });

  it("a predicate that reverses or keeps a retarget can't be picked", () => {
    const retarget = withoutIds(retargetReflection);
    const reverse = retarget.questions[2].options.find((o) => o.option === "reverse:holds")!;
    expect(isPickable(retarget, "predicate_for", reverse)).toBe(false);
    expect(pickOutcome(retarget, { predicate_for: "reverse:holds" })?.fields).toBeUndefined();
  });
});

describe("pair change", () => {
  it("tells a retarget from a rename or reverse", () => {
    expect(pickOutcome(retargetReflection, { source_for: "tool" })?.pair).toBe("different");
    expect(pickOutcome(retargetReflection, { source_for: "task" })?.pair).toBe("same");
    expect(
      pickOutcome(retargetReflection, { source_for: "task", predicate_for: "reverse:holds" })?.pair,
    ).toBe("reversed");
  });
});

describe("contradicts", () => {
  it("links direct contradictions only, not a chain", () => {
    const a = byId("c-rename"); // task needs_tool tool -> task uses tool
    const b = byId("c-delete"); // task uses tool -> task wields tool
    const c = structuredClone(b);
    Object.assign(c, { id: "c-third", seq: 11, target_id: "prop-c-third" });
    c.reflection = {
      ...c.reflection!,
      current: { source: "task", predicate: "wields", target: "tool" },
      replacement: "task grips tool",
    };
    expect(contradicts(a, b)).toBe(true);
    expect(contradicts(b, c)).toBe(true);
    expect(contradicts(a, c)).toBe(false);
    expect(conflictClusters([a, b, c])[0].operations.map((o) => o.id)).toEqual([
      "c-rename",
      "c-delete",
      "c-third",
    ]);
  });
});

describe("no current triple (older proposals)", () => {
  const noCurrent = () => ({ ...retargetReflection, current: null });

  it("only the plan's answers can be picked", () => {
    const reflection = noCurrent();
    for (const q of reflection.questions) {
      for (const o of q.options) expect(isPickable(reflection, q.question, o)).toBe(o.plan);
    }
  });

  it("never makes an edit whose pair change is unknown", () => {
    const outcome = pickOutcome(noCurrent(), { source_for: "tool" });
    expect(outcome?.changed).toBe(true);
    expect(outcome?.pair).toBeUndefined();
    expect(outcome?.fields).toBeUndefined();
  });
});

describe("tieredOrder", () => {
  it("lists mechanical groups, judgment groups, then conflict cards, as the view shows them", () => {
    expect(tieredOrder(ops(), ops())).toEqual([
      "m-dup",
      "m-rename",
      "m-blocked",
      "m-reverse",
      "m-stale",
      "j-retarget",
      "j-compound",
      "c-rename",
      "c-delete",
    ]);
  });
  it("lists only the card members the filter shows", () => {
    const all = ops();
    const shown = all.filter((o) => o.id !== "c-rename");
    expect(tieredOrder(shown, all).slice(-1)).toEqual(["c-delete"]);
    expect(tieredOrder(shown, all)).not.toContain("c-rename");
  });
});

describe("optionDefinition", () => {
  const sources = {
    classDefinition: (id: string) => (id === "class-task" ? "One thing to do." : undefined),
    predicateDefinition: (p: string) => (p === "holds" ? "Keeps it inside." : undefined),
  };
  const opt = (option: string, class_id: string | null = null) => ({
    option,
    probability: 0.5,
    class_id,
    current: false,
    plan: false,
  });

  it("defines a class answer by its class's description", () => {
    expect(optionDefinition("source_for", opt("task", "class-task"), sources)).toEqual({
      term: "task",
      text: "One thing to do.",
    });
  });
  it("defines a predicate answer, marking a reverse one", () => {
    expect(optionDefinition("predicate_for", opt("reverse:holds"), sources)).toEqual({
      term: "holds",
      text: "Keeps it inside.",
      reversed: true,
    });
  });
  it("defines nothing for none or an undefined answer", () => {
    expect(optionDefinition("source_for", opt("none"), sources)).toBeUndefined();
    expect(optionDefinition("source_for", opt("tool", "class-tool"), sources)).toBeUndefined();
    expect(optionDefinition("predicate_for", opt("uses"), sources)).toBeUndefined();
  });
});
