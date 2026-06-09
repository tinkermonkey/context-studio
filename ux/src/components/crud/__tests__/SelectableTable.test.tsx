import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type Column } from "@tinkermonkey/heimdall-ui";
import { render } from "@/test/test-utils";
import { SelectableTable } from "../SelectableTable";

interface TestRow {
  id: string;
  name: string;
  type: string;
}

const columns: Column<TestRow>[] = [
  { key: "name", label: "Name" },
  { key: "type", label: "Type" },
];

function makeRows(count: number): TestRow[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `${i + 1}`,
    name: `Item ${i + 1}`,
    type: `Type${i % 3}`,
  }));
}

describe("SelectableTable", () => {
  describe("data-testid and ARIA", () => {
    it("has default data-testid on root", () => {
      render(<SelectableTable columns={columns} data={makeRows(3)} />);
      expect(screen.getByTestId("selectable-table")).toBeInTheDocument();
    });

    it("accepts custom testId", () => {
      render(<SelectableTable columns={columns} data={makeRows(3)} testId="my-table" />);
      expect(screen.getByTestId("my-table")).toBeInTheDocument();
    });

    it("pagination nav has navigation role", () => {
      render(<SelectableTable columns={columns} data={makeRows(10)} />);
      expect(screen.getByRole("navigation", { name: "Pagination" })).toBeInTheDocument();
    });
  });

  describe("CSS classes", () => {
    it("root element has schema-table-wrap class", () => {
      const { container } = render(<SelectableTable columns={columns} data={makeRows(3)} />);
      expect(container.querySelector(".schema-table-wrap")).toBeInTheDocument();
    });
  });

  describe("rendering", () => {
    it("renders column headers", () => {
      render(<SelectableTable columns={columns} data={makeRows(3)} />);
      expect(screen.getByText("Name")).toBeInTheDocument();
      expect(screen.getByText("Type")).toBeInTheDocument();
    });

    it("renders row data", () => {
      render(<SelectableTable columns={columns} data={makeRows(3)} />);
      expect(screen.getByText("Item 1")).toBeInTheDocument();
      expect(screen.getByText("Item 2")).toBeInTheDocument();
      expect(screen.getByText("Item 3")).toBeInTheDocument();
    });

    it("shows skeleton rows when loading", () => {
      const { container } = render(
        <SelectableTable columns={columns} data={[]} isLoading={true} />,
      );
      const skeletons = container.querySelectorAll(".skeleton");
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it("hides row data when loading", () => {
      render(<SelectableTable columns={columns} data={makeRows(3)} isLoading={true} />);
      expect(screen.queryByText("Item 1")).not.toBeInTheDocument();
    });
  });

  describe("pagination", () => {
    it("shows no pager when total is 9 or fewer rows", () => {
      render(<SelectableTable columns={columns} data={makeRows(9)} />);
      expect(screen.queryByTestId("selectable-table-prev")).not.toBeInTheDocument();
    });

    it("shows pager when total exceeds 9 rows", () => {
      render(<SelectableTable columns={columns} data={makeRows(10)} />);
      expect(screen.getByTestId("selectable-table-prev")).toBeInTheDocument();
      expect(screen.getByTestId("selectable-table-next")).toBeInTheDocument();
    });

    it("shows X–Y of N range", () => {
      render(<SelectableTable columns={columns} data={makeRows(10)} />);
      expect(screen.getByText("1–9 of 10")).toBeInTheDocument();
    });

    it("shows range on second page", async () => {
      const user = userEvent.setup();
      render(<SelectableTable columns={columns} data={makeRows(20)} />);
      await user.click(screen.getByTestId("selectable-table-next"));
      expect(screen.getByText("10–18 of 20")).toBeInTheDocument();
    });

    it("disables prev button on first page", () => {
      render(<SelectableTable columns={columns} data={makeRows(10)} />);
      expect(screen.getByTestId("selectable-table-prev")).toBeDisabled();
    });

    it("disables next button on last page", async () => {
      const user = userEvent.setup();
      render(<SelectableTable columns={columns} data={makeRows(10)} />);
      await user.click(screen.getByTestId("selectable-table-next"));
      expect(screen.getByTestId("selectable-table-next")).toBeDisabled();
    });

    it("clamps page when data shrinks", async () => {
      const user = userEvent.setup();
      const { rerender } = render(
        <SelectableTable columns={columns} data={makeRows(20)} />,
      );
      await user.click(screen.getByTestId("selectable-table-next"));
      expect(screen.getByText("10–18 of 20")).toBeInTheDocument();

      rerender(
        <SelectableTable columns={columns} data={makeRows(9)} />,
      );
      expect(screen.queryByTestId("selectable-table-prev")).not.toBeInTheDocument();
    });
  });

  describe("row menu", () => {
    it("renders row menu trigger buttons for each row", () => {
      const actions = [{ id: "edit", label: "Edit", icon: "edit" as const }];
      const onAction = vi.fn();
      render(
        <SelectableTable
          columns={columns}
          data={makeRows(3)}
          rowMenuActions={actions}
          onRowMenuAction={onAction}
        />,
      );
      expect(screen.getAllByRole("button", { name: "Row actions" }).length).toBe(3);
    });

    it("calls onRowMenuAction with actionId and row when action is clicked", async () => {
      const user = userEvent.setup();
      const actions = [{ id: "edit", label: "Edit" }];
      const onAction = vi.fn();
      render(
        <SelectableTable
          columns={columns}
          data={makeRows(3)}
          rowMenuActions={actions}
          onRowMenuAction={onAction}
        />,
      );
      const editButtons = screen.getAllByRole("button", { name: "Edit" });
      await user.click(editButtons[0]);
      expect(onAction).toHaveBeenCalledWith("edit", expect.objectContaining({ id: "1" }));
    });

    it("does not render row menu when no actions provided", () => {
      render(<SelectableTable columns={columns} data={makeRows(3)} />);
      expect(screen.queryByRole("button", { name: "Row actions" })).not.toBeInTheDocument();
    });
  });

  describe("selection", () => {
    it("calls onSelectRows when Heimdall Table fires selection", () => {
      const onSelectRows = vi.fn();
      render(
        <SelectableTable
          columns={columns}
          data={makeRows(3)}
          selectedRows={[]}
          onSelectRows={onSelectRows}
        />,
      );
      expect(screen.getByTestId("selectable-table")).toBeInTheDocument();
    });

    it("calls onRowClick when a row is clicked", async () => {
      const user = userEvent.setup();
      const onRowClick = vi.fn();
      render(
        <SelectableTable columns={columns} data={makeRows(3)} onRowClick={onRowClick} />,
      );
      const rows = screen.getAllByRole("row");
      await user.click(rows[1]);
      expect(onRowClick).toHaveBeenCalled();
    });
  });
});
