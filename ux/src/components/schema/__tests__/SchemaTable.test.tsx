import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ColumnDef } from "@tanstack/react-table";
import { render } from "@/test/test-utils";
import { SchemaTable } from "../SchemaTable";

interface TestItem {
  id: string;
  name: string;
  type: string;
}

const mockColumns: ColumnDef<TestItem>[] = [
  {
    accessorKey: "name",
    header: "Name",
  },
  {
    accessorKey: "type",
    header: "Type",
  },
];

const mockData: TestItem[] = [
  { id: "1", name: "Item 1", type: "TypeA" },
  { id: "2", name: "Item 2", type: "TypeB" },
];

describe("SchemaTable", () => {
  describe("data-testid attributes", () => {
    it("has schema-table data-testid", () => {
      render(
        <SchemaTable columns={mockColumns} data={mockData} />,
      );
      expect(screen.getByTestId("schema-table")).toBeInTheDocument();
    });

    it("has column header testids", () => {
      render(
        <SchemaTable columns={mockColumns} data={mockData} />,
      );
      expect(screen.getByTestId("schema-header-name")).toBeInTheDocument();
      expect(screen.getByTestId("schema-header-type")).toBeInTheDocument();
    });

    it("has row testids", () => {
      render(
        <SchemaTable columns={mockColumns} data={mockData} />,
      );
      expect(screen.getByTestId("schema-row-1")).toBeInTheDocument();
      expect(screen.getByTestId("schema-row-2")).toBeInTheDocument();
    });
  });

  describe("table rendering", () => {
    it("renders table element", () => {
      const { container } = render(
        <SchemaTable columns={mockColumns} data={mockData} />,
      );
      expect(container.querySelector("table")).toBeInTheDocument();
    });

    it("renders column headers", () => {
      render(
        <SchemaTable columns={mockColumns} data={mockData} />,
      );
      expect(screen.getByText("Name")).toBeInTheDocument();
      expect(screen.getByText("Type")).toBeInTheDocument();
    });

    it("renders data rows", () => {
      render(
        <SchemaTable columns={mockColumns} data={mockData} />,
      );
      expect(screen.getByText("Item 1")).toBeInTheDocument();
      expect(screen.getByText("Item 2")).toBeInTheDocument();
      expect(screen.getByText("TypeA")).toBeInTheDocument();
      expect(screen.getByText("TypeB")).toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("renders empty state message when no data", () => {
      render(
        <SchemaTable columns={mockColumns} data={[]} />,
      );
      expect(screen.getByText("No items")).toBeInTheDocument();
    });

    it("shows selected class for selected row", () => {
      const { container } = render(
        <SchemaTable columns={mockColumns} data={mockData} selectedId="1" />,
      );
      const selectedRow = container.querySelector('tr[data-testid="schema-row-1"]');
      expect(selectedRow).toHaveClass("selected");
    });

    it("does not show selected class for non-selected rows", () => {
      const { container } = render(
        <SchemaTable columns={mockColumns} data={mockData} selectedId="1" />,
      );
      const unselectedRow = container.querySelector(
        'tr[data-testid="schema-row-2"]',
      );
      expect(unselectedRow).not.toHaveClass("selected");
    });
  });

  describe("row selection", () => {
    it("calls onRowSelect when row is clicked", async () => {
      const onRowSelect = vi.fn();
      const user = userEvent.setup();
      render(
        <SchemaTable
          columns={mockColumns}
          data={mockData}
          onRowSelect={onRowSelect}
        />,
      );
      const row = screen.getByTestId("schema-row-1");
      await user.click(row);
      expect(onRowSelect).toHaveBeenCalledWith("1");
    });

    it("does not call onRowSelect when not provided", async () => {
      const user = userEvent.setup();
      const { container } = render(
        <SchemaTable columns={mockColumns} data={mockData} />,
      );
      const row = container.querySelector('tr[data-testid="schema-row-1"]');
      if (row) {
        await user.click(row);
      }
    });
  });

  describe("loading state", () => {
    it("renders skeleton loaders when isLoading is true", () => {
      const { container } = render(
        <SchemaTable columns={mockColumns} data={[]} isLoading={true} />,
      );
      const skeletons = container.querySelectorAll('[style*="height: 16"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it("does not show data rows when loading", () => {
      render(
        <SchemaTable columns={mockColumns} data={mockData} isLoading={true} />,
      );
      expect(screen.queryByText("Item 1")).not.toBeInTheDocument();
    });
  });

  describe("pagination", () => {
    it("renders pagination buttons when multiple pages", () => {
      const largeData = Array.from({ length: 30 }, (_, i) => ({
        id: `${i}`,
        name: `Item ${i}`,
        type: `Type${i % 2}`,
      }));
      render(
        <SchemaTable columns={mockColumns} data={largeData} />,
      );
      expect(screen.getByTestId("schema-pagination-prev")).toBeInTheDocument();
      expect(screen.getByTestId("schema-pagination-next")).toBeInTheDocument();
    });

    it("shows correct page numbers", () => {
      const largeData = Array.from({ length: 30 }, (_, i) => ({
        id: `${i}`,
        name: `Item ${i}`,
        type: `Type${i % 2}`,
      }));
      render(
        <SchemaTable columns={mockColumns} data={largeData} />,
      );
      expect(screen.getByText(/Page 1 of/)).toBeInTheDocument();
    });

    it("navigates to next page", async () => {
      const largeData = Array.from({ length: 30 }, (_, i) => ({
        id: `${i}`,
        name: `Item ${i}`,
        type: `Type${i % 2}`,
      }));
      const user = userEvent.setup();
      render(
        <SchemaTable columns={mockColumns} data={largeData} />,
      );
      const nextButton = screen.getByTestId("schema-pagination-next");
      await user.click(nextButton);
      expect(screen.getByText(/Page 2 of/)).toBeInTheDocument();
    });
  });

  describe("row actions", () => {
    it("renders row actions when provided", () => {
      const renderActions = (row: TestItem) => (
        <button data-testid={`action-${row.id}`}>Edit</button>
      );
      render(
        <SchemaTable
          columns={mockColumns}
          data={mockData}
          renderRowActions={renderActions}
        />,
      );
      expect(screen.getByTestId("action-1")).toBeInTheDocument();
      expect(screen.getByTestId("action-2")).toBeInTheDocument();
    });

    it("does not render actions when not provided", () => {
      const { container } = render(
        <SchemaTable columns={mockColumns} data={mockData} />,
      );
      const lastCell = container.querySelector("tbody tr:last-child td:last-child");
      expect(lastCell?.textContent).toBe("");
    });
  });

  describe("complete structure", () => {
    it("renders all elements together", () => {
      const onRowSelect = vi.fn();
      render(
        <SchemaTable
          columns={mockColumns}
          data={mockData}
          onRowSelect={onRowSelect}
          selectedId="1"
        />,
      );
      expect(screen.getByTestId("schema-table")).toBeInTheDocument();
      expect(screen.getByTestId("schema-header-name")).toBeInTheDocument();
      expect(screen.getByTestId("schema-row-1")).toBeInTheDocument();
      expect(screen.getByText("Item 1")).toBeInTheDocument();
    });
  });
});
