import { describe, it, expect } from "vitest";
import { createProposedOperation } from "@/api/services/__tests__/fixtures/proposals.fixtures";
import { reflectionProposal, retargetReflection } from "@/test/reflectionFixtures";
import {
  bestAlternative,
  conflictClusters,
  defaultGroupBy,
  isBulkEligible,
  kindOf,
  mechanicalAtOrAbove,
  offersGroupBy,
  pRangeLabel,
  pickOutcome,
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
        .filter(isBulkEligible)
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

  it("pulls in a non-conflict delete naming a conflict's type as replacement", () => {
    const extra = createProposedOperation({
      id: "x",
      seq: 10,
      op: "delete",
      kind: "property",
      target_id: "prop-x",
      proposed_replacement_id: "prop-c-delete",
    });
    const clusters = conflictClusters([...ops(), extra]);
    expect(clusters[0].operations.map((o) => o.id)).toEqual(["c-rename", "c-delete", "x"]);
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
