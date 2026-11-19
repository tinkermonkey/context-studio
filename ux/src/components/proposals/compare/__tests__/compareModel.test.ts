import { describe, it, expect } from "vitest";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type { ComparedOperation, ComparisonPair } from "@/api/services/proposals";
import {
  choicesFor,
  comparableProposals,
  decisionRequest,
  failureOf,
  filterPairs,
  originModel,
  outcomeText,
  pairTitle,
  proposalSize,
  takesDecision,
} from "../compareModel";

const copy = (id: string, overrides: Partial<ComparedOperation> = {}) =>
  ({
    operation_id: id,
    seq: 1,
    title: id.toUpperCase(),
    classes: [{ id: `cls-${id}`, title: id }],
    status: "pending",
    evidence: [],
    alternatives: [],
    lacks_passage: false,
    ...overrides,
  }) as ComparedOperation;

const pair = (
  id: string,
  group: ComparisonPair["group"],
  a: ComparedOperation | null,
  b: ComparedOperation | null,
  in_sample = false,
): ComparisonPair => ({ pair_id: id, group, in_sample, state: "open", a, b });

const PAIRS = [
  pair("s1", "same_class", copy("a1"), copy("b1"), true),
  pair("s2", "same_class", copy("a2"), copy("b2")),
  pair("d", "class_differs", copy("a3"), copy("b3")),
  pair("oa", "only_a", copy("a4"), null),
  pair("ob", "only_b", null, copy("b5")),
];

describe("pairs", () => {
  it("filters to differences, agreements, the sample or all", () => {
    const ids = (f: Parameters<typeof filterPairs>[1]) =>
      filterPairs(PAIRS, f).map((p) => p.pair_id);
    expect(ids("differences")).toEqual(["d", "oa", "ob"]);
    expect(ids("agreements")).toEqual(["s1", "s2"]);
    expect(ids("sample")).toEqual(["s1"]);
    expect(ids("all")).toHaveLength(5);
  });

  it("offers a class choice when the classes differ, else keep or reject", () => {
    expect(choicesFor(PAIRS[2]).map((c) => c.verdict)).toEqual([
      "a_class",
      "b_class",
      "not_element",
    ]);
    expect(choicesFor(PAIRS[3]).map((c) => c.label)).toEqual(["Keep", "Not an element"]);
    expect(pairTitle(PAIRS[4])).toBe("B5");
  });

  it("names every copy still awaiting a decision, with the reason and time", () => {
    expect(decisionRequest(PAIRS[2], "a_class", { reviewMs: 1200 })).toEqual({
      a_operation_id: "a3",
      b_operation_id: "b3",
      verdict: "a_class",
      review_ms: 1200,
    });
    expect(decisionRequest(PAIRS[4], "not_element", { reasonCode: "too_generic" })).toEqual({
      b_operation_id: "b5",
      verdict: "not_element",
      reason_code: "too_generic",
    });
    // A partly decided pair: only its open copy.
    const partly = pair("p", "same_class", copy("a6", { status: "applied" }), copy("b6"));
    expect(decisionRequest(partly, "keep")).toEqual({ b_operation_id: "b6", verdict: "keep" });
    // A reason goes only with not_element.
    expect(decisionRequest(PAIRS[3], "keep", { reasonCode: "other" })).toEqual({
      a_operation_id: "a4",
      verdict: "keep",
    });
  });

  it("reads a decided pair, and a failed one's reason", () => {
    const label = (id?: string) => `label:${id}`;
    const bLanded = pair(
      "x",
      "class_differs",
      copy("a", { status: "rejected" }),
      copy("b", { status: "applied" }),
    );
    expect(takesDecision(bLanded)).toBe(false);
    expect(outcomeText(bLanded, label)).toBe("B class: label:cls-b");
    const kept = pair("k", "only_a", copy("a", { status: "applied" }), null);
    expect(outcomeText(kept, label)).toBe("Kept as label:cls-a");
    const rejected = pair(
      "r",
      "only_b",
      null,
      copy("b", { status: "rejected", reason_code: "mentioned_only" }),
    );
    expect(outcomeText(rejected, label)).toBe("Not an element: Mentioned only");
    const failed = pair(
      "f",
      "only_b",
      null,
      copy("b", { status: "failed", reason: "title_conflict" }),
    );
    expect(takesDecision(failed)).toBe(true);
    expect(failureOf(failed)).toBe("title_conflict");
    expect(failureOf(PAIRS[0])).toBeUndefined();
  });
});

describe("proposals to compare with", () => {
  const origin = (implementation_id: string) => ({
    pipeline_type: "individual_extraction",
    implementation_id,
    configuration_ref: "c",
    configuration_version: 1,
    digest: "d",
  });
  const extraction = (id: string, implementation: string, overrides = {}) =>
    createChangeProposal({
      id,
      source: "pipeline",
      dataset_id: "ds-1",
      origin: origin(implementation),
      client_metadata: { source_id: "src-1" },
      ...overrides,
    });

  it("lists other open extractions of the same source and dataset by another implementation", () => {
    const mine = extraction("p1", "single_call");
    const candidates = [
      mine,
      extraction("p2", "find_then_type"),
      extraction("p3", "single_call"),
      extraction("p4", "find_then_type", { client_metadata: { source_id: "src-2" } }),
      extraction("p5", "find_then_type", { dataset_id: "ds-2" }),
      extraction("p6", "find_then_type", { status: "done" }),
      extraction("p7", "find_then_type", { origin: null }),
    ];
    expect(comparableProposals(mine, candidates).map((p) => p.id)).toEqual(["p2"]);
    expect(comparableProposals({ ...mine, status: "done" }, candidates)).toEqual([]);
    expect(comparableProposals(undefined, candidates)).toEqual([]);
  });

  it("reads a proposal's model and size", () => {
    const proposal = extraction("p1", "single_call", {
      client_metadata: { source_id: "src-1", origin: { model: "Opus 5.5" } },
      operations: [
        createProposedOperation({ op: "create", kind: "individual" }),
        createProposedOperation({ op: "create", kind: "relationship" }),
        createProposedOperation({ op: "create", kind: "individual" }),
      ],
    });
    expect(originModel(proposal)).toBe("Opus 5.5");
    expect(originModel(extraction("p2", "x"))).toBeUndefined();
    expect(proposalSize(proposal)).toEqual({ individuals: 2, relationships: 1 });
  });
});
