import { describe, it, expect } from "vitest";
import {
  createChangeProposal,
  createProposedOperation,
} from "@/api/services/__tests__/fixtures/proposals.fixtures";
import {
  classOperation,
  createOperation,
  deleteOperation,
  openProposal,
  renameOperation,
} from "@/test/proposalFixtures";
import {
  asApplied,
  changeRows,
  decidedPercent,
  formatAge,
  formatAgo,
  formatValue,
  isAwaiting,
  operationTouchesClass,
  opMixLabel,
  pendingLabel,
  planKind,
  propertyTriples,
  proposalRefs,
  referencedClassIds,
  resolveRef,
  strictestScope,
  tallyLabel,
  tallyOperations,
} from "../proposalModel";

describe("tally, pending and scope", () => {
  const ops = openProposal.operations;

  it("counts operations by status", () => {
    const tally = tallyOperations(ops);
    expect(tally).toEqual({
      total: 4,
      pending: 3,
      applied: 1,
      rejected: 0,
      failed: 0,
      awaiting: 3,
    });
    expect(tallyLabel(tally)).toBe("3 pending · 1 applied · 0 rejected · 0 failed");
    expect(pendingLabel(tally)).toBe("3 of 4 · 1 applied");
    expect(decidedPercent(tally)).toBe(25);
  });

  it("counts failed operations as awaiting a decision, not decided", () => {
    const failed = createProposedOperation({ id: "op-f", status: "failed" });
    const rejected = createProposedOperation({ id: "op-r", status: "rejected" });
    const tally = tallyOperations([renameOperation, failed, rejected, createOperation]);
    expect(tally.awaiting).toBe(2);
    expect(pendingLabel(tally)).toBe("2 of 4 · 1 applied · 1 failed");
    expect(decidedPercent(tally)).toBe(50);
    expect(isAwaiting(failed)).toBe(true);
    expect(isAwaiting(rejected)).toBe(false);
  });

  it("reads 'N of N' with nothing applied, and 100% decided when empty", () => {
    const tally = tallyOperations([renameOperation]);
    expect(pendingLabel(tally)).toBe("1 of 1");
    expect(decidedPercent(tallyOperations([]))).toBe(100);
  });

  it("finds the strictest scope", () => {
    expect(strictestScope(ops)).toBe("breaking");
    expect(strictestScope([classOperation, createOperation])).toBe("additive");
    expect(strictestScope([classOperation])).toBe("editorial");
    expect(strictestScope([])).toBeUndefined();
  });

  it("summarises the op mix in create / update / move / delete order", () => {
    expect(opMixLabel(ops)).toBe("1 create · 2 update · 1 delete");
  });
});

describe("planKind and formatAge", () => {
  it("reads the plan kind from the rationale, if present", () => {
    expect(planKind(renameOperation)).toBe("rename-predicate");
    expect(planKind(deleteOperation)).toBe("reverse");
    expect(planKind(createOperation)).toBeUndefined();
    expect(planKind(classOperation)).toBeUndefined();
  });

  it("formats compact ages", () => {
    const now = new Date("2026-11-03T12:00:00Z");
    expect(formatAge("2026-11-03T11:59:40Z", now)).toBe("now");
    expect(formatAge("2026-11-03T11:15:00Z", now)).toBe("45m");
    expect(formatAge("2026-11-03T07:00:00Z", now)).toBe("5h");
    expect(formatAge("2026-10-28T12:00:00Z", now)).toBe("6d");
    expect(formatAge("not a date", now)).toBe("—");
  });

  it("phrases ages without 'now ago'", () => {
    const now = new Date("2026-11-03T12:00:00Z");
    expect(formatAgo("2026-11-03T11:59:40Z", now)).toBe("just now");
    expect(formatAgo("2026-11-03T07:00:00Z", now)).toBe("5h ago");
    expect(formatAgo("not a date", now)).toBe("at an unknown time");
  });
});

describe("propertyTriples", () => {
  const current = {
    canonical_predicate: "realizes",
    domain_class_id: "class-1",
    range_class_id: "class-2",
  };

  it("fills an update's untouched parts from the current property", () => {
    expect(propertyTriples(renameOperation, current)).toEqual({
      before: { predicate: "realizes", domain: "class-1", range: "class-2" },
      after: { predicate: "serves", domain: "class-1", range: "class-2" },
    });
  });

  it("leaves an update's untouched ends unknown without the current property", () => {
    expect(propertyTriples(renameOperation, undefined)).toEqual({
      before: { predicate: "realizes", domain: undefined, range: undefined },
      after: { predicate: "serves", domain: undefined, range: undefined },
    });
  });

  it("reads an unconstrained end as null: a create without it, or a current property's null", () => {
    const anyDomain = createProposedOperation({
      kind: "property",
      op: "create",
      target_id: null,
      fields: { canonical_predicate: "mentions", range_class_id: "class-2" },
      base: {},
    });
    expect(propertyTriples(anyDomain).after).toEqual({
      predicate: "mentions",
      domain: null,
      range: "class-2",
    });
    const open = { ...current, domain_class_id: null };
    expect(propertyTriples(renameOperation, open).before?.domain).toBeNull();
  });

  it("falls back to the title only after merging base and fields", () => {
    const untitled = {
      title: "x realizes y",
      domain_class_id: "class-1",
      range_class_id: "class-2",
    };
    // The current property has no canonical predicate; the update sets one.
    expect(propertyTriples(renameOperation, untitled).after?.predicate).toBe("serves");
    const titleOnly = createProposedOperation({
      kind: "property",
      op: "update",
      target_id: "prop-1",
      fields: { title: "x serves y" },
      base: { title: "x realizes y" },
    });
    expect(propertyTriples(titleOnly, current).before?.predicate).toBe("realizes");
  });

  it("prefers base over an already-applied current property", () => {
    const applied = { ...current, canonical_predicate: "serves" };
    expect(propertyTriples(renameOperation, applied).before?.predicate).toBe("realizes");
  });

  it("reads a delete from its whole-entity base and a create from its fields", () => {
    expect(propertyTriples(deleteOperation)).toEqual({
      before: { predicate: "realizes", domain: "class-1", range: "class-2" },
    });
    expect(propertyTriples(createOperation)).toEqual({
      after: { predicate: "uses", domain: "class-2", range: "class-1" },
    });
  });

  it("collects the class ids an operation refers to, skipping $refs", () => {
    const withRef = createProposedOperation({
      kind: "property",
      op: "create",
      target_id: null,
      fields: { domain_class_id: "$c1", range_class_id: "class-9" },
      base: {},
    });
    expect(referencedClassIds(withRef)).toEqual(["class-9"]);
    expect(referencedClassIds(classOperation)).toEqual(["class-1"]);
  });

  it("names $ref ends by their create, and resolves them once applied", () => {
    const create = createProposedOperation({
      id: "op-c",
      op: "create",
      kind: "class",
      target_id: null,
      ref: "cap",
      fields: { title: "BusinessCapability" },
      status: "pending",
    });
    const usesRef = createProposedOperation({
      id: "op-p",
      op: "create",
      kind: "property",
      target_id: null,
      fields: { domain_class_id: "$cap", range_class_id: "class-2" },
      base: {},
    });
    const pending = proposalRefs(createChangeProposal({ operations: [create, usesRef] }));
    expect(pending.get("$cap")).toEqual({ title: "BusinessCapability", resultId: undefined });
    expect(resolveRef("$cap", pending)).toBe("$cap");
    expect(operationTouchesClass(usesRef, "class-new", undefined, pending)).toBe(false);

    const applied = proposalRefs(
      createChangeProposal({
        operations: [{ ...create, status: "applied", result_entity_id: "class-new" }, usesRef],
      }),
    );
    expect(resolveRef("$cap", applied)).toBe("class-new");
    expect(referencedClassIds(usesRef, applied)).toEqual(["class-new", "class-2"]);
    expect(operationTouchesClass(usesRef, "class-new", undefined, applied)).toBe(true);
  });

  it("knows which classes an operation touches", () => {
    expect(operationTouchesClass(deleteOperation, "class-2")).toBe(true);
    expect(operationTouchesClass(createOperation, "class-1")).toBe(true);
    expect(operationTouchesClass(classOperation, "class-1")).toBe(true);
    expect(operationTouchesClass(classOperation, "class-2")).toBe(false);
    // An update that keeps the ends carries no domain or range; the current property has them.
    expect(operationTouchesClass(renameOperation, "class-1")).toBe(false);
    expect(operationTouchesClass(renameOperation, "class-1", current)).toBe(true);
    expect(operationTouchesClass(renameOperation, "class-3", current)).toBe(false);
  });
});

describe("changeRows", () => {
  it("lists an update's touched fields with before and after", () => {
    expect(changeRows(renameOperation)).toEqual([
      { field: "canonical_predicate", before: "realizes", after: "serves", changed: true },
      {
        field: "identifier",
        before: "component_realizes_service",
        after: "component_serves_service",
        changed: true,
      },
    ]);
  });

  it("lists a delete's fields without its bookkeeping", () => {
    const fields = changeRows(deleteOperation).map((row) => row.field);
    expect(fields).toEqual([
      "canonical_predicate",
      "domain_class_id",
      "range_class_id",
      "identifier",
      "title",
    ]);
    expect(changeRows(deleteOperation).every((row) => row.after === undefined)).toBe(true);
  });

  it("lists a create's fields as after values only", () => {
    expect(changeRows(createOperation).every((row) => row.before === undefined)).toBe(true);
  });

  it("formats values for display", () => {
    expect(formatValue(undefined)).toBe("—");
    expect(formatValue("x")).toBe("x");
    expect(formatValue(3)).toBe("3");
    expect(formatValue([{ source: "dr", identifier: "a.b" }])).toBe("a.b");
    expect(formatValue({ a: 1 })).toBe('{"a":1}');
  });
});

describe("asApplied", () => {
  it("reads an edited operation as the update it applied, others as proposed", () => {
    const remove = createProposedOperation({ op: "delete", kind: "property", fields: {} });
    expect(asApplied(remove)).toBe(remove);
    const edited = { ...remove, applied_fields: { canonical_predicate: "serves" } };
    expect(asApplied(edited)).toMatchObject({
      op: "update",
      fields: { canonical_predicate: "serves" },
    });
  });
});
