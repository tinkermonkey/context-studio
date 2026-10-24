import { describe, it, expect } from "vitest";
import { countDecisions, drLayerOf, locateMention, pct, segmentText } from "../reviewUtils";
import { planReviewApply } from "@/api/hooks/pipeline/useApplyReviewedRun";

describe("segmentText", () => {
  const text = "abcdefghij";

  it("splits at every span boundary and records covering spans", () => {
    const segs = segmentText(text, [
      { key: "a", start: 2, end: 6 },
      { key: "b", start: 4, end: 8 },
    ]);
    expect(segs.map((s) => text.slice(s.start, s.end))).toEqual(["ab", "cd", "ef", "gh", "ij"]);
    expect(segs.map((s) => s.covering.map((c) => c.key))).toEqual([
      [],
      ["a"],
      ["a", "b"],
      ["b"],
      [],
    ]);
  });

  it("ignores unlocated and out-of-range spans", () => {
    const segs = segmentText(text, [
      { key: "x", quote: "zz", start: null, end: null },
      { key: "y", start: 5, end: 50 },
    ]);
    expect(segs).toHaveLength(1);
    expect(segs[0].covering).toEqual([]);
  });
});

describe("helpers", () => {
  it("formats percentages and null", () => {
    expect(pct(0.914)).toBe("91%");
    expect(pct(null)).toBe("—");
  });

  it("locates mentions or marks them unlocated", () => {
    expect(locateMention("hello world", "world")).toEqual({ quote: "world", start: 6, end: 11 });
    expect(locateMention("hello", "nope")).toEqual({ quote: "nope", start: null, end: null });
  });

  it("counts decisions, defaulting to pending", () => {
    expect(countDecisions({ a: "yes", b: "no" }, ["a", "b", "c"])).toEqual({
      yes: 1,
      no: 1,
      pending: 1,
    });
  });

  it("maps DR class ids to layers", () => {
    expect(drLayerOf("motivation.stakeholder")).toEqual({ layer: "motivation", num: "01" });
    expect(drLayerOf("6313b6e5-26a1")).toBeNull();
    expect(drLayerOf(undefined)).toBeNull();
  });
});

describe("planReviewApply (explicit selections)", () => {
  it("sends accepted candidate ids as the full selection, with schema scope", () => {
    const plan = planReviewApply({
      runId: "r",
      kind: "schema",
      scope: { taxonomy_id: "t", concept_scheme_id: "s" },
      decisions: {
        "class-0": "yes",
        "class-1": "no",
        "connection-0": "yes",
        "property-0": "pending",
      },
    });
    expect(plan.params).toEqual({ taxonomy_id: "t", concept_scheme_id: "s" });
    expect(plan.body).toEqual({ accepted_candidate_ids: ["class-0", "connection-0"] });
  });

  it("sends an empty selection when nothing is accepted", () => {
    const plan = planReviewApply({
      runId: "r",
      kind: "schema",
      scope: { taxonomy_id: "t", concept_scheme_id: "s" },
      decisions: { "class-0": "no" },
    });
    expect(plan.body.accepted_candidate_ids).toEqual([]);
  });

  it("maps merge / keep-separate to recognition decisions and leaves pending to recognition", () => {
    const plan = planReviewApply({
      runId: "r",
      kind: "individual",
      scope: { taxonomy_id: "t" },
      decisions: { "triple-0": "yes" },
      mentions: [
        { mention_label: "Portal", individual_id: "ind-1", decision: "yes" },
        { mention_label: "Adjuster", individual_id: "ind-2", decision: "no" },
        { mention_label: "Service", individual_id: "ind-3", decision: "pending" },
        { mention_label: " portal ", individual_id: "ind-9", decision: "no" },
      ],
    });
    expect(plan.params).toEqual({ taxonomy_id: "t", recognition_threshold: 0.9 });
    expect(plan.body).toEqual({
      accepted_candidate_ids: ["triple-0"],
      recognition_decisions: [
        { mention_label: "Portal", decision: "merge", individual_id: "ind-1" },
        { mention_label: "Adjuster", decision: "separate" },
      ],
    });
  });

  it("omits recognition_decisions when every mention is undecided", () => {
    const plan = planReviewApply({
      runId: "r",
      kind: "individual",
      scope: { taxonomy_id: "t" },
      decisions: {},
      mentions: [{ mention_label: "Portal", individual_id: "ind-1", decision: "pending" }],
    });
    expect(plan.body).toEqual({ accepted_candidate_ids: [] });
  });
});
