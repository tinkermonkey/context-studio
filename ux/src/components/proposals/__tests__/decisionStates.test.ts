/**
 * Colour means you have something to decide: each operation's decision state,
 * its flags' tone, the summary banner's counts and the table's default filter.
 */
import { describe, it, expect } from "vitest";
import { createProposedOperation } from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  decidedByLabel,
  decidedRecord,
  decisionHeadline,
  decisionProgress,
  decisionState,
  defaultOperationFilter,
  filterOperations,
  linksToDecided,
  flagVariant,
  progressPills,
  resolutionChip,
} from "../decisionModel";

const op = createProposedOperation;

const edge = (n: number) => ({
  relationship_id: `rel-${n}`,
  source: { id: `s-${n}`, title: `S${n}`, class_ids: [], class_titles: [] },
  target: { id: `t-${n}`, title: `T${n}`, class_ids: [], class_titles: [] },
  attributes: {},
});
const blockers = { edges: [edge(1), edge(2)], replacements: [] };

const resolved = (strategy: "move" | "delete", edges = 2, reversed = false) => ({
  strategy,
  replacement_identifier: strategy === "move" ? "uses" : null,
  reversed,
  edges: Array.from({ length: edges }, (_, i) => ({
    relationship_id: `rel-${i}`,
    source_id: "a",
    target_id: "b",
    source_title: "A",
    target_title: "B",
  })),
});

function replacementCheck(pair: "same" | "reversed" | "different" | "missing") {
  return {
    replacement_id: "prop-twin",
    pair,
    deleted_domain: { id: "class-1" },
    deleted_range: { id: "class-2" },
    domain: { id: "class-2" },
    range: { id: "class-1" },
  } as unknown as ProposedOperation["replacement_check"];
}

describe("decisionState", () => {
  it.each([
    ["pending", {}, "needs_decision", "needs decision", "amber"],
    ["pending", { stale: true }, "needs_decision", "needs decision", "amber"],
    ["pending", { blockers }, "needs_choice", "needs a choice", "amber"],
    ["failed", { blockers }, "needs_choice", "needs a choice", "amber"],
    ["failed", {}, "failed", "failed", "rose"],
    ["applied", {}, "applied", "applied", "emerald"],
    [
      "applied",
      { applied_fields: { title: "x" } },
      "applied_with_edits",
      "applied with edits",
      "emerald",
    ],
    ["rejected", {}, "rejected", "rejected", "neutral"],
    // Blockers on a decided operation no longer count.
    ["applied", { blockers }, "applied", "applied", "emerald"],
  ] as const)("%s %o reads %s", (status, extra, state, label, variant) => {
    expect(decisionState(op({ status, ...extra } as Partial<ProposedOperation>))).toEqual({
      state,
      label,
      variant,
    });
  });

  it("reads a reverted proposal's applied operations as reverted, in neutral", () => {
    const reverted = { state: "reverted", label: "reverted", variant: "neutral" };
    expect(decisionState(op({ status: "applied" }), true)).toEqual(reverted);
    expect(decisionState(op({ status: "applied", applied_fields: { a: 1 } }), true)).toEqual(
      reverted,
    );
    // A revert rejects what was still open, and rejections stand.
    expect(decisionState(op({ status: "rejected" }), true).state).toBe("rejected");
  });
});

describe("flags", () => {
  it("keep their colour while awaiting and turn neutral once decided", () => {
    for (const status of ["pending", "failed"] as const) {
      expect(flagVariant(op({ status }), "rose")).toBe("rose");
      expect(flagVariant(op({ status }), "amber")).toBe("amber");
    }
    for (const status of ["applied", "rejected"] as const) {
      expect(flagVariant(op({ status }), "rose")).toBe("neutral");
      expect(flagVariant(op({ status }), "amber")).toBe("neutral");
    }
  });

  it("record a decided delete's resolution, with the count when known", () => {
    expect(resolutionChip(op({ status: "applied", resolution: resolved("move") }))).toBe(
      "moved 2 relationships",
    );
    expect(resolutionChip(op({ status: "applied", resolution: resolved("delete", 1) }))).toBe(
      "dropped 1 relationship",
    );
    expect(resolutionChip(op({ status: "applied", resolution: resolved("move", 0) }))).toBe(
      "moved relationships",
    );
    expect(resolutionChip(op({ status: "failed", resolution: resolved("move") }))).toBeUndefined();
    expect(resolutionChip(op({ status: "applied" }))).toBeUndefined();
  });
});

describe("decidedRecord", () => {
  it("says how the pair compared and what happened to the relationships", () => {
    expect(
      decidedRecord(
        op({
          status: "applied",
          replacement_check: replacementCheck("reversed"),
          resolution: resolved("move", 2, true),
        }),
      ),
    ).toBe(
      "The replacement linked the pair reversed; 2 relationships moved to uses with their ends swapped.",
    );
    expect(
      decidedRecord(op({ status: "applied", replacement_check: replacementCheck("different") })),
    ).toBe("The replacement linked a different pair.");
    expect(decidedRecord(op({ status: "applied", resolution: resolved("delete", 3) }))).toBe(
      "3 relationships deleted with the type.",
    );
  });

  it("has nothing to add for a plain decision, or while awaiting", () => {
    expect(decidedRecord(op({ status: "applied" }))).toBeUndefined();
    expect(
      decidedRecord(op({ status: "rejected", replacement_check: replacementCheck("same") })),
    ).toBeUndefined();
    expect(
      decidedRecord(op({ status: "pending", replacement_check: replacementCheck("reversed") })),
    ).toBeUndefined();
  });
});

describe("decidedByLabel", () => {
  it("names the user as you, then the date and time", () => {
    expect(decidedByLabel("user", "2026-11-06T12:53:08+00:00", "UTC")).toBe(
      "by you · Nov 6, 12:53",
    );
    expect(decidedByLabel("policy", "2026-11-06T09:05:00+00:00", "UTC")).toBe(
      "by policy · Nov 6, 09:05",
    );
  });

  it("leaves out an unknown decider, and is undefined with nothing recorded", () => {
    expect(decidedByLabel("unknown", "2026-11-06T12:53:08+00:00", "UTC")).toBe("Nov 6, 12:53");
    expect(decidedByLabel(null, null)).toBeUndefined();
    expect(decidedByLabel(undefined, "not a date")).toBeUndefined();
  });
});

describe("decisionProgress", () => {
  it("counts failed blocked deletes as needing a decision (the 0 pending bug)", () => {
    // Every pending op was applied; blocked deletes applied without a resolution failed.
    const ops = [
      op({ id: "a", status: "applied" }),
      op({ id: "b", status: "failed", blockers }),
      op({ id: "c", status: "failed", blockers }),
      op({ id: "d", status: "failed", reason: "boom" }),
    ];
    const progress = decisionProgress(ops);
    expect(progress).toMatchObject({
      total: 4,
      awaiting: 3,
      applied: 1,
      rejected: 0,
      toDecide: 0,
      needChoice: 2,
      failed: 1,
      stale: 0,
      ready: 1,
      percent: 25,
    });
    expect(decisionHeadline(progress)).toBe("3 of 4 need a decision");
    expect(progressPills(progress)).toEqual([
      { key: "need-choice", count: 2, label: "2 need an in-use choice", variant: "amber" },
      { key: "failed", count: 1, label: "1 failed: retry or reject", variant: "rose" },
    ]);
  });

  it("splits awaiting into to-decide, in-use choice, failed and stale", () => {
    const ops = [
      op({ id: "a" }),
      op({ id: "b" }),
      op({ id: "c", stale: true }),
      op({ id: "d", blockers, stale: true }),
      op({ id: "e", status: "failed" }),
      op({ id: "f", status: "rejected" }),
    ];
    const progress = decisionProgress(ops);
    expect(progress).toMatchObject({
      awaiting: 5,
      toDecide: 2,
      needChoice: 1,
      failed: 1,
      stale: 1,
    });
    expect(progress.toDecide + progress.needChoice + progress.failed + progress.stale).toBe(
      progress.awaiting,
    );
    // Accept N ready: awaiting, not stale, not blocked (a failed one applies again).
    expect(progress.ready).toBe(3);
    expect(progressPills(progress).map((p) => p.label)).toEqual([
      "2 to accept or reject",
      "1 need an in-use choice",
      "1 failed: retry or reject",
      "1 stale: apply anyway or reject",
    ]);
  });

  it("counts near matches and low-confidence operations as their own pills (#1555)", () => {
    const near = {
      op: "create" as const,
      kind: "individual" as const,
      target_id: null,
      alternatives: [{ kind: "existing" as const, entity_id: "ind-1", similarity: 0.9 }],
    };
    const ops = [
      op({ id: "a", probability: 0.9 }),
      op({ id: "b", ...near, probability: 0.3 }),
      op({ id: "c", ...near, probability: 0.95 }),
      op({ id: "d", probability: 0.4 }),
      op({ id: "e", probability: 0.4, stale: true }),
    ];
    const progress = decisionProgress(ops);
    expect(progress).toMatchObject({ toDecide: 1, nearMatches: 2, lowConfidence: 1, stale: 1 });
    expect(
      progress.toDecide +
        progress.nearMatches +
        progress.lowConfidence +
        progress.needChoice +
        progress.failed +
        progress.stale,
    ).toBe(progress.awaiting);
    expect(progressPills(progress)).toEqual([
      { key: "to-decide", count: 1, label: "1 to accept or reject", variant: "amber" },
      { key: "near-match", count: 2, label: "2 near matches", variant: "violet" },
      { key: "low-confidence", count: 1, label: "1 low confidence", variant: "amber" },
      { key: "stale", count: 1, label: "1 stale: apply anyway or reject", variant: "rose" },
    ]);
    // Low confidence follows the threshold the reviewer sets.
    expect(decisionProgress(ops, 0.95).lowConfidence).toBe(2);
  });

  it("reads All N decided once nothing awaits", () => {
    const progress = decisionProgress([
      op({ id: "a", status: "applied" }),
      op({ id: "b", status: "rejected" }),
    ]);
    expect(decisionHeadline(progress)).toBe("All 2 decided");
    expect(progress.percent).toBe(100);
    expect(progressPills(progress)).toEqual([]);
    expect(decisionProgress([]).percent).toBe(100);
  });
});

describe("table filter", () => {
  const ops = [
    op({ id: "a" }),
    op({ id: "b", status: "failed" }),
    op({ id: "c", status: "applied" }),
  ];

  it("defaults to Needs decision while anything awaits, else All", () => {
    expect(defaultOperationFilter(decisionProgress(ops))).toBe("needs");
    expect(defaultOperationFilter(decisionProgress([ops[2]]))).toBe("all");
  });

  it("opens on All when deep-linked to a decided operation", () => {
    expect(linksToDecided(ops, "c")).toBe(true);
    expect(linksToDecided(ops, "a")).toBe(false);
    expect(linksToDecided(ops, "gone")).toBe(false);
    expect(linksToDecided(ops)).toBe(false);
    expect(defaultOperationFilter(decisionProgress(ops), true)).toBe("all");
    expect(defaultOperationFilter(decisionProgress(ops), false)).toBe("needs");
  });

  it("filters by awaiting or decided", () => {
    expect(filterOperations(ops, "needs").map((o) => o.id)).toEqual(["a", "b"]);
    expect(filterOperations(ops, "decided").map((o) => o.id)).toEqual(["c"]);
    expect(filterOperations(ops, "all")).toHaveLength(3);
  });
});
