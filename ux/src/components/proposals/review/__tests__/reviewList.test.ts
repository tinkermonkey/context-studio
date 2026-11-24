import { describe, it, expect } from "vitest";
import { createProposedOperation } from "@/api/services/__tests__/fixtures/proposals.fixtures";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  defaultListGroupBy,
  groupByOptions,
  listOrder,
  listSections,
  rowStatus,
} from "../reviewList";

const element = (id: string, seq: number, classId: string) =>
  createProposedOperation({
    id,
    seq,
    op: "create",
    kind: "individual",
    target_id: null,
    fields: { title: id, class_ids: [classId] },
  });
const relationship = createProposedOperation({
  id: "rel",
  seq: 9,
  op: "create",
  kind: "relationship",
  target_id: null,
  fields: { property_definition_id: "p", source_id: "$a", target_id: "$b" },
});
const classUpdate = createProposedOperation({
  id: "cls",
  seq: 3,
  op: "update",
  kind: "class",
  target_id: "class-1",
  base: { title: "A" },
  fields: { title: "B" },
});
const reflected = (id: string, seq: number, kind: string, extra: Partial<ProposedOperation> = {}) =>
  createProposedOperation({
    id,
    seq,
    op: "update",
    kind: "property",
    target_id: `prop-${id}`,
    fields: { canonical_predicate: "serves" },
    reflection: { plan_kind: kind, questions: [] } as unknown as ProposedOperation["reflection"],
    ...extra,
  });

const layers: Record<string, { key: string; label: string }> = {
  "cls-feature": { key: "scheme-product", label: "Product" },
  "cls-goal": { key: "scheme-motivation", label: "Motivation" },
};
const layerOf = (o: ProposedOperation) =>
  layers[(o.fields?.class_ids as string[] | undefined)?.[0] ?? ""] ?? {
    key: "other",
    label: "Other",
  };

describe("the groupings offered", () => {
  it("offers Layer for an extraction and Sequence always", () => {
    const ops = [element("a", 1, "cls-feature"), relationship];
    expect(groupByOptions(ops)).toEqual(["layer", "sequence"]);
    expect(defaultListGroupBy(ops)).toBe("layer");
  });

  it("offers Change kind when operations carry plan kinds, and opens a reflected plan on it", () => {
    const ops = [reflected("r1", 1, "rename-predicate"), classUpdate];
    expect(groupByOptions(ops)).toEqual(["kind", "sequence"]);
    expect(defaultListGroupBy(ops)).toBe("kind");
  });

  it("opens anything else on Sequence", () => {
    expect(groupByOptions([classUpdate])).toEqual(["sequence"]);
    expect(defaultListGroupBy([classUpdate])).toBe("sequence");
  });
});

describe("the sections", () => {
  it("by layer: elements by layer in first-seen order, then relationships, then other kinds", () => {
    const ops = [
      element("a", 1, "cls-goal"),
      element("b", 2, "cls-feature"),
      element("c", 4, "cls-goal"),
      relationship,
      classUpdate,
    ];
    const sections = listSections(ops, ops, "layer", layerOf);
    expect(sections.map((s) => [s.key, s.label])).toEqual([
      ["scheme-motivation", "Motivation"],
      ["scheme-product", "Product"],
      ["relationships", "Relationships"],
      ["kind-class", "Classes"],
    ]);
    expect(listOrder(sections, new Set(ops.map((o) => o.id)))).toEqual([
      "a",
      "c",
      "b",
      "rel",
      "cls",
    ]);
  });

  it("by sequence: one section in seq order", () => {
    const ops = [classUpdate, element("a", 1, "cls-goal"), relationship];
    const sections = listSections(ops, ops, "sequence", layerOf);
    expect(sections).toHaveLength(1);
    expect(listOrder(sections, new Set(ops.map((o) => o.id)))).toEqual(["a", "cls", "rel"]);
  });

  it("by change kind: mechanical, judgment, a card per conflict, then the rest", () => {
    const ops = [reflected("m", 1, "rename-predicate"), reflected("j", 2, "retarget"), classUpdate];
    const sections = listSections(ops, ops, "kind", layerOf);
    expect(sections.map((s) => s.key)).toEqual([
      "kind-rename-predicate",
      "kind-retarget",
      "kind-other",
    ]);
    expect(sections[0].label).toBe("rename-predicate · mechanical");
    expect(sections[1].label).toBe("retarget · judgment");
  });

  it("is empty when the filters leave nothing", () => {
    expect(listSections([], [classUpdate], "sequence", layerOf)).toEqual([]);
    expect(listSections([], [classUpdate], "layer", layerOf)).toEqual([]);
  });
});

describe("a row's status", () => {
  it("reads an element by its verdict and a change by its decision state", () => {
    expect(rowStatus(element("a", 1, "cls-goal"))).toMatchObject({
      state: "awaiting",
      label: "awaiting",
    });
    expect(rowStatus(classUpdate)).toMatchObject({
      state: "needs_decision",
      label: "needs decision",
      variant: "amber",
    });
  });

  it("reads a failed apply as failed, an element's or relationship's too", () => {
    const failed = { ...relationship, status: "failed" as const };
    expect(rowStatus(failed)).toMatchObject({ state: "failed", label: "failed", variant: "rose" });
  });

  it("reads a withdrawn operation as withdrawn, whatever it is (#1624)", () => {
    const gone = { ...element("a", 1, "cls-goal"), status: "withdrawn" as const };
    expect(rowStatus(gone)).toEqual({ state: "withdrawn", label: "withdrawn", variant: "neutral" });
    expect(rowStatus({ ...classUpdate, status: "withdrawn" })).toMatchObject({
      state: "withdrawn",
    });
  });

  it("reads an applied element of a reverted proposal as reverted", () => {
    const applied = { ...element("a", 1, "cls-goal"), status: "applied" as const };
    expect(rowStatus(applied, true)).toMatchObject({ state: "reverted", label: "reverted" });
  });
});
