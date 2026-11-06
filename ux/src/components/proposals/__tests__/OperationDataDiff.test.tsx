/**
 * #1415: an individual operation's attribute values (data_properties) show in
 * the review queue's diff and inspector rows, one row per attribute.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { createProposedOperation } from "@/api/services/__tests__/fixtures/proposals.fixtures";
import { OperationDiff } from "../OperationDiff";
import { changeRows, dataValues, fieldLabel } from "../proposalModel";
import type { OperationContext } from "../useOperationContext";

const context: OperationContext = {
  endLabel: (end) => String(end ?? "any"),
  endTitle: () => undefined,
  currentProperty: () => undefined,
  targetGone: () => false,
};

const created = createProposedOperation({
  id: "op-saw",
  op: "create",
  kind: "individual",
  target_id: null,
  fields: {
    class_ids: ["cls-tool"],
    title: "Saw",
    data_properties: { brand: "Makita", watts: 1200 },
  },
  base: {},
});

const updated = createProposedOperation({
  id: "op-drill",
  op: "update",
  kind: "individual",
  target_id: "ind-drill",
  fields: { data_properties: { brand: "DeWalt", watts: 700, colour: null } },
  base: { data_properties: { brand: "Bosch", watts: null, colour: "red" } },
});

describe("data_properties in changeRows", () => {
  it("gives each attribute value of an update a row, before and after", () => {
    expect(changeRows(updated)).toEqual([
      { field: "data_properties.brand", before: "Bosch", after: "DeWalt", changed: true },
      { field: "data_properties.colour", before: "red", after: null, changed: true },
      { field: "data_properties.watts", before: null, after: 700, changed: true },
    ]);
    expect(fieldLabel("data_properties.watts")).toBe("watts");
    expect(fieldLabel("title")).toBe("title");
  });

  it("reads a create's map and a delete's snapshot list", () => {
    expect(changeRows(created).map((row) => [row.field, row.after])).toEqual([
      ["title", "Saw"],
      ["class_ids", ["cls-tool"]],
      ["data_properties.brand", "Makita"],
      ["data_properties.watts", 1200],
    ]);
    expect(
      dataValues([{ property_identifier: "brand", value: "Bosch", datatype: "string" }]),
    ).toEqual({ brand: "Bosch" });
  });
});

describe("OperationDiff with attribute values", () => {
  it("a create lists the values it sets", () => {
    render(<OperationDiff operation={created} context={context} />);
    expect(screen.getByTestId("operation-diff-data-op-saw")).toHaveTextContent(
      "brand Makita, watts 1200",
    );
  });

  it("an update shows each changed value by its attribute", () => {
    render(<OperationDiff operation={updated} context={context} />);
    const diff = screen.getByTestId("operation-diff-op-drill");
    expect(diff).toHaveTextContent("brand Bosch → DeWalt");
    expect(diff).toHaveTextContent("colour red → —");
    expect(diff).toHaveTextContent("and 1 more");
    expect(diff).not.toHaveTextContent("data_properties");
  });
});
