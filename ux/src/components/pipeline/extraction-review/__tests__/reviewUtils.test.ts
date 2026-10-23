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

describe("planReviewApply (threshold-based apply)", () => {
  const items = [
    { key: "a", confidence: 0.9 },
    { key: "b", confidence: 0.7 },
    { key: "c", confidence: 0.8 },
    { key: "d", confidence: 0.5 },
  ];

  it("uses the lowest accepted confidence and reports rejected items at or above it", () => {
    const plan = planReviewApply({
      runId: "r",
      kind: "schema",
      scope: { taxonomy_id: "t", concept_scheme_id: "s" },
      items,
      decisions: { a: "yes", b: "yes", c: "no", d: "no" },
    });
    expect(plan.minConfidence).toBe(0.7);
    expect(plan.leakedKeys).toEqual(["c"]);
    expect(plan.params).toEqual({
      confidence_threshold: 0.7,
      taxonomy_id: "t",
      concept_scheme_id: "s",
    });
  });

  it("sends the recognition threshold and counts keep-separate choices for individuals", () => {
    const plan = planReviewApply({
      runId: "r",
      kind: "individual",
      scope: { taxonomy_id: "t" },
      items,
      decisions: { a: "yes" },
      merges: { h1: "no", h2: "yes", h3: "no" },
    });
    expect(plan.params).toMatchObject({ confidence_threshold: 0.9, recognition_threshold: 0.9 });
    expect(plan.params.concept_scheme_id).toBeUndefined();
    expect(plan.ignoredSeparateCount).toBe(2);
  });
});
