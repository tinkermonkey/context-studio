import { describe, it, expect } from "vitest";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import { createClass } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  RELATIONSHIPS_GROUP,
  REJECTION_REASONS,
  reasonsFor,
  VERDICT_CHIP,
  VERDICT_LABEL,
  classLabel,
  endsToDecide,
  extractedFromSource,
  filterGroups,
  formatDuration,
  groupForReview,
  layerMatesFirst,
  nextAwaiting,
  opensReviewInspector,
  orderOf,
  reasonLabel,
  relationshipsOf,
  RECENT_CLASSES,
  forgetPick,
  rememberPick,
  reviewProgress,
  reviewSourceId,
  reviewSpans,
  seqList,
  shownClassId,
  step,
  suggestedClasses,
  verdictOf,
} from "../reviewModel";

const TEXT = "Edit Check offers feedback. Tone check is new.";

function element(id: string, overrides: Partial<ProposedOperation> = {}): ProposedOperation {
  return createProposedOperation({
    id,
    op: "create",
    kind: "individual",
    target_id: null,
    ref: id,
    fields: { title: id, class_ids: ["class-a"] },
    evidence: [],
    ...overrides,
  });
}

function passage(quote: string, sourceId = "src-1") {
  const start = TEXT.indexOf(quote);
  return { source_id: sourceId, page: null, start, end: start + quote.length, quote };
}

describe("verdicts", () => {
  it("maps each outcome to a verdict, label and chip", () => {
    expect(verdictOf(element("a"))).toBe("awaiting");
    expect(verdictOf(element("a", { status: "failed" }))).toBe("awaiting");
    expect(verdictOf(element("a", { status: "applied" }))).toBe("correct");
    expect(
      verdictOf(
        element("a", {
          status: "applied",
          applied_fields: { title: "a", class_ids: ["class-a"] },
        }),
      ),
    ).toBe("correct");
    const changed = element("a", {
      status: "applied",
      applied_fields: { title: "a", class_ids: ["class-b"] },
    });
    expect(verdictOf(changed)).toBe("changed");
    expect(shownClassId(changed)).toBe("class-b");
    expect(verdictOf(element("a", { status: "rejected" }))).toBe("rejected");
    expect(verdictOf(element("a", { status: "applied", added_by_reviewer: true }))).toBe("added");
    expect(VERDICT_LABEL.changed).toBe("class changed");
    expect(VERDICT_LABEL.rejected).toBe("not an element");
    expect(VERDICT_CHIP).toEqual({
      awaiting: "amber",
      correct: "emerald",
      changed: "violet",
      rejected: "rose",
      added: "cyan",
    });
  });

  it("counts the progress by verdict", () => {
    const progress = reviewProgress([
      element("a"),
      element("b", { status: "applied" }),
      element("c", { status: "applied", applied_fields: { class_ids: ["class-z"] } }),
      element("d", { status: "rejected" }),
      element("e", { status: "applied", added_by_reviewer: true }),
    ]);
    expect(progress).toEqual({
      decided: 4,
      total: 5,
      percent: 80,
      correct: 1,
      changed: 1,
      rejected: 1,
      added: 1,
    });
    expect(reviewProgress([]).percent).toBe(0);
  });
});

describe("the source", () => {
  it("finds the source most passages are in", () => {
    const ops = [
      element("a", { evidence: [passage("Edit Check", "src-2")] }),
      element("b", { evidence: [passage("Tone check"), passage("feedback")] }),
    ];
    expect(reviewSourceId(ops)).toBe("src-1");
    expect(reviewSourceId([element("c")])).toBeUndefined();
  });

  it("says whether a proposal was extracted from a source", () => {
    expect(extractedFromSource(createChangeProposal())).toBe(false);
    expect(
      extractedFromSource(
        createChangeProposal({ operations: [element("a", { evidence: [passage("feedback")] })] }),
      ),
    ).toBe(true);
    expect(extractedFromSource(undefined)).toBe(false);
    // A schema extraction's class operations carry passages too: not reviewed here.
    const classOp = createProposedOperation({
      op: "create",
      kind: "class",
      target_id: null,
      evidence: [passage("feedback")],
    });
    expect(extractedFromSource(createChangeProposal({ operations: [classOp] }))).toBe(false);
  });

  it("opens every operation in the review inspector but a DR relationship type's (#1660)", () => {
    const create = element("a", { evidence: [passage("feedback")] });
    const update = createProposedOperation({ op: "update", kind: "individual" });
    const move = createProposedOperation({ op: "move", kind: "class" });
    const remove = createProposedOperation({ op: "delete", kind: "class" });
    for (const operation of [create, update, move, remove]) {
      expect(opensReviewInspector(operation)).toBe(true);
    }
    // A relationship type's operations keep OperationInspector until #1662.
    expect(opensReviewInspector(createProposedOperation({ op: "update", kind: "property" }))).toBe(
      false,
    );
    expect(
      opensReviewInspector(
        createProposedOperation({
          op: "update",
          kind: "individual",
          reflection: { questions: [], plan: {} } as unknown as ProposedOperation["reflection"],
        }),
      ),
    ).toBe(false);
  });

  it("keys each element's passages in the source's text, leaving out misplaced ones", () => {
    const ops = [
      element("a", { evidence: [passage("Edit Check"), passage("Tone check", "src-2")] }),
      element("b", {
        evidence: [
          passage("feedback"),
          // Its text at these offsets is not its quote.
          { source_id: "src-1", page: null, start: 0, end: 4, quote: "Tone" },
          // Past the end of the text.
          { source_id: "src-1", page: null, start: 40, end: 400, quote: "x" },
        ],
      }),
    ];
    expect(reviewSpans(ops, "src-1", TEXT)).toEqual([
      { key: "a", quote: "Edit Check", start: 0, end: 10 },
      { key: "b", quote: "feedback", start: 18, end: 26 },
    ]);
  });

  it("places passages after an emoji: code-point offsets to UTF-16 spans", () => {
    const text = `😀 ${TEXT}`;
    // "feedback" is at code points 20-28, UTF-16 units 21-29.
    const ops = [
      element("a", {
        evidence: [{ source_id: "src-1", page: null, start: 20, end: 28, quote: "feedback" }],
      }),
    ];
    expect(reviewSpans(ops, "src-1", text)).toEqual([
      { key: "a", quote: "feedback", start: 21, end: 29 },
    ]);
  });

  it("places passages in text that starts later in the whole text", () => {
    const ops = [element("a", { evidence: [{ ...passage("feedback"), start: 118, end: 126 }] })];
    expect(reviewSpans(ops, "src-1", TEXT, 100)).toEqual([
      { key: "a", quote: "feedback", start: 18, end: 26 },
    ]);
  });
});

describe("groups and selection", () => {
  const a = element("a");
  const b = element("b", { status: "applied" });
  const c = element("c");
  const rel = createProposedOperation({
    id: "rel",
    op: "create",
    kind: "relationship",
    target_id: null,
    fields: { source_id: "$a", target_id: "ind-9", property_definition_id: "prop-1" },
  });
  const layers: Record<string, { key: string; label: string }> = {
    a: { key: "product", label: "Product" },
    b: { key: "motivation", label: "Motivation" },
    c: { key: "product", label: "Product" },
  };
  const groups = groupForReview([a, b, c], [rel], (o) => layers[o.id]);

  it("groups elements by layer in first-seen order, then the relationships", () => {
    expect(groups.map((g) => [g.key, g.operations.map((o) => o.id)])).toEqual([
      ["product", ["a", "c"]],
      ["motivation", ["b"]],
      [RELATIONSHIPS_GROUP, ["rel"]],
    ]);
    expect(orderOf(groups)).toEqual(["a", "c", "b", "rel"]);
  });

  it("filters to awaiting elements, keeping the selected one", () => {
    expect(orderOf(filterGroups(groups, "awaiting", undefined))).toEqual(["a", "c", "rel"]);
    expect(orderOf(filterGroups(groups, "awaiting", "b"))).toEqual(["a", "c", "b", "rel"]);
    expect(filterGroups(groups, "all", undefined)).toBe(groups);
  });

  it("steps through the order, staying at either end", () => {
    const order = ["a", "c", "b"];
    expect(step(order, "a", 1)).toBe("c");
    expect(step(order, "a", -1)).toBe("a");
    expect(step(order, "b", 1)).toBe("b");
    expect(step(order, undefined, 1)).toBe("a");
    expect(step([], "a", 1)).toBeUndefined();
  });

  it("moves to the next awaiting element after a decision, wrapping around", () => {
    const order = ["a", "b", "c", "d"];
    expect(nextAwaiting(order, new Set(["a", "d"]), "b")).toBe("d");
    expect(nextAwaiting(order, new Set(["a"]), "c")).toBe("a");
    expect(nextAwaiting(order, new Set(["c"]), "c")).toBeUndefined();
    expect(nextAwaiting(order, new Set(), "c")).toBeUndefined();
  });

  it("finds a relationship's new ends still to decide, or rejected", () => {
    const ops = [element("a", { seq: 1 }), element("c", { seq: 3, status: "rejected" }), rel];
    expect(endsToDecide(rel, ops).undecided.map((e) => e.seq)).toEqual([1]);
    expect(endsToDecide(rel, ops).rejected).toEqual([]);
    const toRejected = { ...rel, fields: { ...rel.fields, target_id: "$c" } };
    const ends = endsToDecide(toRejected, ops);
    expect(seqList(ends.undecided)).toBe("#1");
    expect(seqList(ends.rejected)).toBe("#3");
    expect(endsToDecide(rel, [element("a", { seq: 1, status: "applied" }), rel])).toEqual({
      undecided: [],
      rejected: [],
    });
  });

  it("finds an element's relationships by $ref or result id", () => {
    expect(relationshipsOf(a, [a, b, rel]).map((o) => o.id)).toEqual(["rel"]);
    const made = element("z", { ref: null, result_entity_id: "ind-9", status: "applied" });
    expect(relationshipsOf(made, [rel]).map((o) => o.id)).toEqual(["rel"]);
    expect(relationshipsOf(c, [rel])).toEqual([]);
  });
});

describe("classes and reasons", () => {
  it("names a class by its DR reference, else its title, else its identifier", () => {
    const dr = createClass({
      identifier: "product_feature",
      title: "Feature",
      external_references: [
        { source: "wikidata", identifier: "Q1" },
        { source: "documentation_robotics", identifier: "product.feature" },
      ],
    });
    expect(classLabel(dr)).toBe("product.feature");
    expect(classLabel(createClass({ identifier: "cls_x", title: "Room" }))).toBe("Room");
    expect(classLabel(createClass({ identifier: "cls_x", title: "" }))).toBe("cls_x");
  });

  it("lists a layer's classes first", () => {
    const a = createClass({ id: "a", concept_scheme_id: "p" });
    const b = createClass({ id: "b", concept_scheme_id: "m" });
    const c = createClass({ id: "c", concept_scheme_id: "p" });
    expect(layerMatesFirst([a, b, c], "m").map((x) => x.id)).toEqual(["b", "a", "c"]);
    expect(layerMatesFirst([a, b, c], undefined).map((x) => x.id)).toEqual(["a", "b", "c"]);
  });

  it("suggests up to three classes picked earlier, most recent first, not the current one", () => {
    let recent: string[] = [];
    for (const id of ["c1", "c2", "c3", "c4", "c2"]) recent = rememberPick(recent, id, 4);
    expect(recent).toEqual(["c2", "c4", "c3", "c1"]);
    expect(suggestedClasses(recent, "c4")).toEqual(["c2", "c3", "c1"]);
    expect(suggestedClasses(recent, undefined)).toEqual(["c2", "c4", "c3"]);
  });

  it("keeps two recent classes by default, dropping the oldest, and forgets one", () => {
    let recent: string[] = [];
    for (const id of ["c1", "c2", "c3"]) recent = rememberPick(recent, id);
    expect(RECENT_CLASSES).toBe(2);
    expect(recent).toEqual(["c3", "c2"]);
    expect(rememberPick(recent, "c2")).toEqual(["c2", "c3"]);
    expect(forgetPick(recent, "c3")).toEqual(["c2"]);
  });

  it("labels each reason code", () => {
    expect(REJECTION_REASONS.map((r) => r.label)).toEqual([
      "Not in this text",
      "Too generic",
      "Mentioned only",
      "Out of scope",
      "Duplicate",
      "Wrong",
      "Keep as it is",
      "Out of date",
      "Other",
    ]);
    expect(reasonLabel("mentioned_only")).toBe("Mentioned only");
    expect(reasonLabel(null)).toBeUndefined();
  });

  it("offers the codes for creates, for changes, and for a mix", () => {
    const create = createProposedOperation({ op: "create", kind: "individual" });
    const update = createProposedOperation({ op: "update" });
    const remove = createProposedOperation({ op: "delete" });
    const codes = (ops: ProposedOperation[]) => reasonsFor(ops).map((r) => r.code);

    expect(codes([create])).toEqual([
      "not_in_text",
      "too_generic",
      "mentioned_only",
      "out_of_scope",
      "duplicate",
      "other",
    ]);
    expect(codes([])).toEqual(codes([create]));
    expect(codes([update, remove])).toEqual([
      "out_of_scope",
      "incorrect",
      "keep_current",
      "outdated",
      "other",
    ]);
    // One code for a create and an update is a code that fits both.
    expect(codes([create, update])).toEqual(["out_of_scope", "other"]);
  });

  it("leads with Out of date when an operation is stale", () => {
    const stale = createProposedOperation({ op: "update", stale: true });
    expect(reasonsFor([stale]).map((r) => r.code)).toEqual([
      "outdated",
      "out_of_scope",
      "incorrect",
      "keep_current",
      "other",
    ]);
  });

  it("formats a duration as minutes and seconds", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(65_400)).toBe("1:05");
    expect(formatDuration(3_725_000)).toBe("62:05");
  });
});
