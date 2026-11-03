import { describe, it, expect } from "vitest";
import { createProposedOperation } from "@/api/services/__tests__/fixtures/proposals.fixtures";
import {
  classOperation,
  createOperation,
  deleteOperation,
  openProposal,
  renameOperation,
} from "@/test/proposalFixtures";
import {
  changeRows,
  decidedPercent,
  formatAge,
  formatValue,
  operationTouchesClass,
  opMixLabel,
  pendingLabel,
  planKind,
  propertyTriples,
  referencedClassIds,
  strictestScope,
  tallyLabel,
  tallyOperations,
} from "../proposalModel";

describe("tally, pending and scope", () => {
  const ops = openProposal.operations;

  it("counts operations by status", () => {
    const tally = tallyOperations(ops);
    expect(tally).toEqual({ total: 4, pending: 3, applied: 1, rejected: 0, failed: 0 });
    expect(tallyLabel(tally)).toBe("3 pending · 1 applied · 0 rejected · 0 failed");
    expect(pendingLabel(tally)).toBe("3 of 4 · 1 applied");
    expect(decidedPercent(tally)).toBe(25);
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
