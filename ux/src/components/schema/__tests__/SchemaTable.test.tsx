import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type Column } from "@tinkermonkey/heimdall-ui";
import { render } from "@/test/test-utils";
import { SchemaTable } from "../SchemaTable";

interface TestItem {
  id: string;
  name: string;
  type: string;
}

const mockColumns: Column<TestItem>[] = [
  {
    key: "name",
    label: "Name",
  },
  {
    key: "type",
    label: "Type",
  },
];

const mockData: TestItem[] = [
  { id: "1", name: "Item 1", type: "TypeA" },
  { id: "2", name: "Item 2", type: "TypeB" },
];

describe("SchemaTable", () => {
  describe("data-testid attributes", () => {
    it("has schema-table data-testid", () => {
      render(<SchemaTable columns={mockColumns} data={mockData} />);
      expect(screen.getByTestId("schema-table")).toBeInTheDocument();
    });

    it("uses default schema-table testid when no tableTestId provided", () => {
      render(<SchemaTable columns={mockColumns} data={mockData} />);
      expect(screen.getByTestId("schema-table")).toBeInTheDocument();
    });
  });

  describe("table rendering", () => {
    it("renders table element", () => {
      const { container } = render(<SchemaTable columns={mockColumns} data={mockData} />);
      expect(container.querySelector("table")).toBeInTheDocument();
    });

    it("renders column headers", () => {
      render(<SchemaTable columns={mockColumns} data={mockData} />);
      expect(screen.getByText("Name")).toBeInTheDocument();
      expect(screen.getByText("Type")).toBeInTheDocument();
    });

    it("renders data rows", () => {
      render(<SchemaTable columns={mockColumns} data={mockData} />);
      expect(screen.getByText("Item 1")).toBeInTheDocument();
      expect(screen.getByText("Item 2")).toBeInTheDocument();
      expect(screen.getByText("TypeA")).toBeInTheDocument();
      expect(screen.getByText("TypeB")).toBeInTheDocument();
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
      render(<SchemaTable columns={mockColumns} data={mockData} isLoading={true} />);
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
      render(<SchemaTable columns={mockColumns} data={largeData} />);
      expect(screen.getByTestId("schema-pagination-prev")).toBeInTheDocument();
      expect(screen.getByTestId("schema-pagination-next")).toBeInTheDocument();
    });

    it("shows correct page numbers", () => {
      const largeData = Array.from({ length: 30 }, (_, i) => ({
        id: `${i}`,
        name: `Item ${i}`,
        type: `Type${i % 2}`,
      }));
      render(<SchemaTable columns={mockColumns} data={largeData} />);
      expect(screen.getByText(/Page 1 of/)).toBeInTheDocument();
    });

    it("navigates to next page", async () => {
      const largeData = Array.from({ length: 30 }, (_, i) => ({
        id: `${i}`,
        name: `Item ${i}`,
        type: `Type${i % 2}`,
      }));
      const user = userEvent.setup();
      render(<SchemaTable columns={mockColumns} data={largeData} />);
      const nextButton = screen.getByTestId("schema-pagination-next");
      await user.click(nextButton);
      expect(screen.getByText(/Page 2 of/)).toBeInTheDocument();
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
      expect(screen.getByText("Name")).toBeInTheDocument();
      expect(screen.getByText("Item 1")).toBeInTheDocument();
    });
  });
});
