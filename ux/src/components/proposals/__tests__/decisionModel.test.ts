import { describe, it, expect } from "vitest";
import { ApiError } from "@/api/client/interceptors";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import {
  atOrAboveThreshold,
  checkDrTriple,
  decisionPreview,
  drEditFields,
  drPredicateCatalog,
  drSpecOf,
  drTriplesOf,
  hasProbabilities,
  hasTripleErrors,
  isBelowThreshold,
  isDrEditable,
  outcomeRows,
  revertConflictOf,
  revertSummary,
  splitStale,
  staleCause,
  staleCauseText,
  takesDecisions,
  type DrTriple,
} from "../decisionModel";

const op = createProposedOperation;

describe("probability threshold", () => {
  const ops = [
    op({ id: "a", probability: 0.82 }),
    op({ id: "b", probability: 0.6 }),
    op({ id: "c", probability: 0.59 }),
    op({ id: "d", probability: 0.95, stale: true }),
    op({ id: "e", probability: 0.9, status: "applied" }),
    op({ id: "f", probability: 0.7, status: "failed" }),
    op({ id: "g", probability: null }),
  ];

  it("selects awaiting, non-stale operations at or above the threshold", () => {
    expect(atOrAboveThreshold(ops, 0.6).map((o) => o.id)).toEqual(["a", "b", "f"]);
    expect(atOrAboveThreshold(ops, 0.85).map((o) => o.id)).toEqual([]);
    expect(atOrAboveThreshold(ops, 0).map((o) => o.id)).toEqual(["a", "b", "c", "f"]);
  });

  it("never selects a stale operation, however probable", () => {
    expect(atOrAboveThreshold(ops, 0.9).map((o) => o.id)).not.toContain("d");
  });

  it("mutes only probabilities below the threshold", () => {
    expect(isBelowThreshold(ops[2], 0.6)).toBe(true);
    expect(isBelowThreshold(ops[1], 0.6)).toBe(false);
    expect(isBelowThreshold(ops[6], 0.6)).toBe(false);
  });

  it("knows whether any operation has a probability", () => {
    expect(hasProbabilities(ops)).toBe(true);
    expect(hasProbabilities([op({ probability: null }), op({ probability: undefined })])).toBe(
      false,
    );
  });
});

describe("who decides", () => {
  it("takes decisions until reverted", () => {
    expect(takesDecisions(createChangeProposal({ status: "open" }))).toBe(true);
    expect(takesDecisions(createChangeProposal({ status: "done" }))).toBe(true);
    expect(takesDecisions(createChangeProposal({ status: "reverted" }))).toBe(false);
  });

  it("splits awaiting operations into fresh and stale, dropping decided ones", () => {
    const ops = [
      op({ id: "a" }),
      op({ id: "b", stale: true }),
      op({ id: "c", status: "applied" }),
      op({ id: "d", status: "failed" }),
    ];
    expect(splitStale(ops, ["a", "b", "c", "d"])).toEqual({ fresh: ["a", "d"], stale: ["b"] });
  });
});

describe("staleCause", () => {
  it("reads the fields from a target_changed failure", () => {
    const failed = op({ reason: "target_changed: description, title changed since proposed" });
    expect(staleCause(failed)).toEqual({ gone: false, fields: ["description", "title"] });
  });

  it("says the target is gone from a target_missing failure", () => {
    expect(staleCause(op({ reason: "target_missing: property p1" })).gone).toBe(true);
  });

  it("compares the base with the current target, ignoring bookkeeping", () => {
    const stale = op({
      base: { description: "old", title: "Same", version: 2, last_modified: "x" },
    });
    const current = { description: "new", title: "Same", version: 5, last_modified: "y" };
    expect(staleCause(stale, current)).toEqual({ gone: false, fields: ["description"] });
  });

  it("falls back to gone or unknown", () => {
    expect(staleCause(op({}), undefined, true)).toEqual({ gone: true, fields: [] });
    expect(staleCauseText(staleCause(op({})))).toBe("Its target changed after it was proposed.");
    expect(staleCauseText({ gone: false, fields: ["description"] })).toBe(
      "description changed since it was proposed.",
    );
  });
});

// ==================== DR triple edits ====================

const dr = (identifier: string) => [{ source: "documentation_robotics", identifier }];
const spec = drSpecOf(
  [
    { id: "c-role", external_references: dr("business.businessrole") },
    { id: "c-process", external_references: dr("business.businessprocess") },
    { id: "c-event", external_references: dr("business.businessevent") },
    { id: "c-other", external_references: [] },
  ],
  drPredicateCatalog({
    external_references: [
      {
        source: "documentation_robotics",
        identifier: "spec",
        metadata: { predicates: { performs: {}, triggers: {}, "assigned-to": {} } },
      },
    ],
  }),
);

const update = op({
  id: "op-u",
  seq: 1,
  op: "update",
  kind: "property",
  target_id: "p-assigned",
  fields: { canonical_predicate: "performs" },
  base: { canonical_predicate: "assigned-to" },
});
const current = {
  canonical_predicate: "assigned-to",
  domain_class_id: "c-role",
  range_class_id: "c-process",
};

describe("drSpecOf and the predicate catalog", () => {
  it("maps spec node ids to class ids and reads the catalog", () => {
    expect(spec.classIdByNode.get("business.businessrole")).toBe("c-role");
    expect(spec.nodeByClassId.get("c-event")).toBe("business.businessevent");
    expect(spec.classIdByNode.size).toBe(3);
    expect([...(spec.predicates ?? [])].sort()).toEqual(["assigned-to", "performs", "triggers"]);
  });

  it("has no catalog when the import stored none", () => {
    expect(drPredicateCatalog({ external_references: [] })).toBeUndefined();
  });

  it("gives an update's current and proposed triples by spec node", () => {
    expect(drTriplesOf(update, spec, current)).toEqual({
      current: {
        source: "business.businessrole",
        predicate: "assigned-to",
        destination: "business.businessprocess",
      },
      proposed: {
        source: "business.businessrole",
        predicate: "performs",
        destination: "business.businessprocess",
      },
    });
  });

  it("edits only property updates and deletes on dr_spec", () => {
    expect(isDrEditable(update, "dr_spec")).toBe(true);
    expect(isDrEditable(op({ ...update, op: "delete" }), "dr_spec")).toBe(true);
    expect(isDrEditable(update, "house")).toBe(false);
    expect(isDrEditable(op({ ...update, op: "create", target_id: null }), "dr_spec")).toBe(false);
    expect(isDrEditable(op({ kind: "class" }), "dr_spec")).toBe(false);
  });
});

describe("checkDrTriple", () => {
  const triple = (source: string, predicate: string, destination: string): DrTriple => ({
    source,
    predicate,
    destination,
  });
  const check = (t: DrTriple, extra: Partial<Parameters<typeof checkDrTriple>[2]> = {}) =>
    checkDrTriple(t, spec, { operation: update, others: [update], ...extra });

  it("accepts a triple of dr_spec classes and a catalog predicate", () => {
    const errors = check(triple("business.businessevent", "triggers", "business.businessprocess"));
    expect(hasTripleErrors(errors)).toBe(false);
  });

  it("names an unknown class, an unknown predicate and empty parts", () => {
    expect(check(triple("business.typo", "triggers", "business.businessrole"))).toEqual({
      source: "No class business.typo in dr_spec",
      destination: undefined,
      predicate: undefined,
    });
    expect(
      check(triple("business.businessrole", "befriends", "business.businessrole")).predicate,
    ).toBe("befriends is not in the predicate catalog");
    expect(check(triple("", "", "")).source).toBe("Required");
    expect(check(triple("", "", "")).predicate).toBe("Required");
  });

  it("refuses a triple that another relationship type already has", () => {
    const existing = [
      {
        id: "p-other",
        identifier: "businessevent_triggers_businessprocess",
        canonical_predicate: "triggers",
        domain_class_id: "c-event",
        range_class_id: "c-process",
      },
    ];
    const errors = check(triple("business.businessevent", "triggers", "business.businessprocess"), {
      existing,
    });
    expect(errors.triple).toMatch(
      /^business\.businessevent\.triggers\.business\.businessprocess already exists as businessevent_triggers_businessprocess/,
    );
    // The target itself may keep its own triple.
    const own = check(triple("business.businessrole", "assigned-to", "business.businessprocess"), {
      existing: [
        {
          ...existing[0],
          id: "p-assigned",
          canonical_predicate: "assigned-to",
          domain_class_id: "c-role",
        },
      ],
    });
    expect(own.triple).toBeUndefined();
  });

  it("refuses a triple another open operation of the proposal makes", () => {
    const other = op({
      id: "op-c",
      seq: 4,
      op: "create",
      kind: "property",
      fields: {
        external_references: dr("business.businessevent.triggers.business.businessrole"),
      },
    });
    const errors = check(triple("business.businessevent", "triggers", "business.businessrole"), {
      others: [update, other],
    });
    expect(errors.triple).toBe(
      "seq 4 also produces business.businessevent.triggers.business.businessrole.",
    );
  });

  it("refuses a delete's replacement that is the current triple", () => {
    const remove = op({ ...update, op: "delete", fields: {} });
    const now = triple("business.businessrole", "assigned-to", "business.businessprocess");
    expect(check(now, { operation: remove, current: now }).triple).toMatch(
      /is the current triple\. To keep it, reject the delete\./,
    );
  });
});

describe("the edits payload and the decision preview", () => {
  const edited: DrTriple = {
    source: "business.businessevent",
    predicate: "triggers",
    destination: "business.businessprocess",
  };

  it("sends the triple as Context Studio fields", () => {
    expect(drEditFields(edited, spec)).toEqual({
      canonical_predicate: "triggers",
      domain_class_id: "c-event",
      range_class_id: "c-process",
    });
  });

  it("previews DR's decision line, with fields only on an edit", () => {
    expect(decisionPreview(update, edited)).toEqual({
      seq: 1,
      op_id: "op-u",
      status: "applied",
      fields: {
        predicate: "triggers",
        source_spec_node_id: "business.businessevent",
        destination_spec_node_id: "business.businessprocess",
      },
      reason: null,
    });
    expect(decisionPreview(update)).toEqual({
      seq: 1,
      op_id: "op-u",
      status: "applied",
      reason: null,
    });
  });
});

describe("outcomeRows", () => {
  it("lists the sent operations in seq order with what each did", () => {
    const proposal = createChangeProposal({
      operations: [
        op({ id: "a", seq: 1, op: "update", status: "applied", fields: { identifier: "x_y" } }),
        op({
          id: "b",
          seq: 2,
          op: "delete",
          status: "applied",
          applied_fields: { identifier: "b_assigned_to_a" },
        }),
        op({ id: "c", seq: 3, op: "delete", status: "applied" }),
        op({ id: "d", seq: 4, status: "failed", reason: "target_missing: property p" }),
        op({ id: "e", seq: 5, status: "pending" }),
      ],
    });
    const rows = outcomeRows(proposal, ["d", "a", "b", "c"]);
    expect(rows.map((r) => [r.operation.id, r.edited, r.result])).toEqual([
      ["a", false, "x_y"],
      ["b", true, "b_assigned_to_a"],
      ["c", false, "removed"],
      ["d", false, "target_missing: property p"],
    ]);
  });
});

describe("revert", () => {
  it("summarizes what a revert undoes", () => {
    const proposal = createChangeProposal({
      operations: [
        op({ id: "a", op: "create", status: "applied" }),
        op({ id: "b", op: "update", status: "applied" }),
        op({ id: "c", op: "delete", status: "applied", applied_fields: { identifier: "x" } }),
        op({ id: "d", op: "delete", status: "applied" }),
        op({ id: "e", status: "pending" }),
        op({ id: "f", status: "rejected" }),
      ],
    });
    expect(revertSummary(proposal)).toEqual({
      applied: 4,
      created: 1,
      updated: 2,
      deleted: 1,
      edited: 1,
      open: 1,
    });
  });

  it("reads the blockers from a 409 and ignores other errors", () => {
    const blocking = [{ kind: "individual", dependent_id: "i1", referenced_id: "c1" }];
    const conflict = new ApiError("refused", 409, "refused", { message: "refused", blocking });
    expect(revertConflictOf(conflict)).toEqual({ message: "refused", blocking });
    expect(revertConflictOf(new ApiError("x", 409, "can't be undone"))).toEqual({
      message: "can't be undone",
      blocking: [],
    });
    expect(revertConflictOf(new ApiError("boom", 500, "boom"))).toBeUndefined();
    expect(revertConflictOf(new Error("x"))).toBeUndefined();
  });
});
