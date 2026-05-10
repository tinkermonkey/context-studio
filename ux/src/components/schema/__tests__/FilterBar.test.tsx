import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { FilterBar } from "../FilterBar";

describe("FilterBar", () => {
  describe("data-testid attributes", () => {
    it("has schema-filter-bar data-testid", () => {
      render(
        <FilterBar searchValue="" onSearchChange={vi.fn()} />,
      );
      expect(screen.getByTestId("schema-filter-bar")).toBeInTheDocument();
    });

    it("has schema-search-input data-testid on input", () => {
      render(
        <FilterBar searchValue="" onSearchChange={vi.fn()} />,
      );
      expect(screen.getByTestId("schema-search-input")).toBeInTheDocument();
    });
  });

  describe("search input", () => {
    it("renders input element", () => {
      render(
        <FilterBar searchValue="" onSearchChange={vi.fn()} />,
      );
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    it("has default placeholder text", () => {
      render(
        <FilterBar searchValue="" onSearchChange={vi.fn()} />,
      );
      expect(
        screen.getByPlaceholderText("Search by title or description…"),
      ).toBeInTheDocument();
    });

    it("renders custom placeholder when provided", () => {
      render(
        <FilterBar
          searchValue=""
          onSearchChange={vi.fn()}
          placeholder="Search by name..."
        />,
      );
      expect(screen.getByPlaceholderText("Search by name...")).toBeInTheDocument();
    });

    it("displays current search value", () => {
      render(
        <FilterBar searchValue="test search" onSearchChange={vi.fn()} />,
      );
      const input = screen.getByTestId("schema-search-input") as HTMLInputElement;
      expect(input.value).toBe("test search");
    });

    it("calls onSearchChange when input value changes", async () => {
      const onSearchChange = vi.fn();
      const user = userEvent.setup();
      render(
        <FilterBar searchValue="" onSearchChange={onSearchChange} />,
      );
      const input = screen.getByTestId("schema-search-input");
      await user.type(input, "x");
      expect(onSearchChange).toHaveBeenCalledWith("x");
    });
  });

  describe("filter chips", () => {
    it("does not render chips container when no chips provided", () => {
      const { container } = render(
        <FilterBar searchValue="" onSearchChange={vi.fn()} />,
      );
      const chipsContainer = container.querySelector(
        'div[style*="flex-wrap"]',
      );
      expect(chipsContainer).not.toBeInTheDocument();
    });

    it("renders chip elements when filterChips provided", () => {
      const chips = [
        { label: "Tag 1", value: "tag1", onRemove: vi.fn() },
        { label: "Tag 2", value: "tag2", onRemove: vi.fn() },
      ];
      const { container } = render(
        <FilterBar
          searchValue=""
          onSearchChange={vi.fn()}
          filterChips={chips}
        />,
      );
      const chipElements = container.querySelectorAll(".chip");
      expect(chipElements.length).toBe(2);
    });

    it("displays chip labels", () => {
      const chips = [
        { label: "Active", value: "active", onRemove: vi.fn() },
        { label: "Pending", value: "pending", onRemove: vi.fn() },
      ];
      render(
        <FilterBar
          searchValue=""
          onSearchChange={vi.fn()}
          filterChips={chips}
        />,
      );
      expect(screen.getByText("Active")).toBeInTheDocument();
      expect(screen.getByText("Pending")).toBeInTheDocument();
    });

    it("renders remove button for each chip", () => {
      const chips = [
        { label: "Tag 1", value: "tag1", onRemove: vi.fn() },
        { label: "Tag 2", value: "tag2", onRemove: vi.fn() },
      ];
      render(
        <FilterBar
          searchValue=""
          onSearchChange={vi.fn()}
          filterChips={chips}
        />,
      );
      const removeButtons = screen.getAllByRole("button");
      expect(removeButtons.length).toBe(2);
    });

    it("calls onRemove callback when remove button is clicked", async () => {
      const onRemove = vi.fn();
      const chips = [
        { label: "Tag 1", value: "tag1", onRemove },
      ];
      const user = userEvent.setup();
      render(
        <FilterBar
          searchValue=""
          onSearchChange={vi.fn()}
          filterChips={chips}
        />,
      );
      const removeButton = screen.getByLabelText("Remove Tag 1");
      await user.click(removeButton);
      expect(onRemove).toHaveBeenCalled();
    });

    it("renders all chips with correct labels", () => {
      const chips = [
        { label: "Production", value: "prod", onRemove: vi.fn() },
        { label: "Development", value: "dev", onRemove: vi.fn() },
        { label: "Testing", value: "test", onRemove: vi.fn() },
      ];
      render(
        <FilterBar
          searchValue=""
          onSearchChange={vi.fn()}
          filterChips={chips}
        />,
      );
      expect(screen.getByText("Production")).toBeInTheDocument();
      expect(screen.getByText("Development")).toBeInTheDocument();
      expect(screen.getByText("Testing")).toBeInTheDocument();
    });
  });

  describe("complete structure", () => {
    it("renders search input and chips together", () => {
      const chips = [
        { label: "Important", value: "important", onRemove: vi.fn() },
      ];
      render(
        <FilterBar
          searchValue="search term"
          onSearchChange={vi.fn()}
          filterChips={chips}
        />,
      );
      expect(screen.getByTestId("schema-search-input")).toBeInTheDocument();
      expect(screen.getByText("Important")).toBeInTheDocument();
    });

    it("has correct overall data-testid", () => {
      render(
        <FilterBar searchValue="" onSearchChange={vi.fn()} />,
      );
      const filterBar = screen.getByTestId("schema-filter-bar");
      expect(filterBar).toBeInTheDocument();
      expect(filterBar.querySelector('[data-testid="schema-search-input"]')).toBeInTheDocument();
    });
  });
});
