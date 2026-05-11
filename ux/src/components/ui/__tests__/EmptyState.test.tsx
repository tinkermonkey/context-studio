import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { EmptyState } from "../EmptyState";

describe("EmptyState", () => {
  describe("data-testid attributes", () => {
    it("has empty-state data-testid", () => {
      render(<EmptyState title="No items" />);
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    it("has empty-state-action data-testid when action is provided", () => {
      render(<EmptyState title="No items" action={{ label: "Create", onClick: vi.fn() }} />);
      expect(screen.getByTestId("empty-state-action")).toBeInTheDocument();
    });

    it("does not render action testid when action is not provided", () => {
      render(<EmptyState title="No items" />);
      expect(screen.queryByTestId("empty-state-action")).not.toBeInTheDocument();
    });
  });

  describe("CSS class styling", () => {
    it("applies empty-state class", () => {
      const { container } = render(<EmptyState title="No items" />);
      const emptyState = container.querySelector(".empty-state");
      expect(emptyState).toBeInTheDocument();
    });

    it("applies compact class when variant is compact", () => {
      const { container } = render(<EmptyState title="No items" variant="compact" />);
      const emptyState = container.querySelector(".empty-state");
      expect(emptyState).toHaveClass("compact");
    });

    it("does not apply compact class for default variant", () => {
      const { container } = render(<EmptyState title="No items" variant="default" />);
      const emptyState = container.querySelector(".empty-state");
      expect(emptyState).not.toHaveClass("compact");
    });
  });

  describe("icon", () => {
    it("renders icon element when provided", () => {
      const { container } = render(<EmptyState title="No items" icon={<span>📦</span>} />);
      const icon = container.querySelector(".empty-state-icon");
      expect(icon).toBeInTheDocument();
      expect(screen.getByText("📦")).toBeInTheDocument();
    });

    it("does not render icon container when icon not provided", () => {
      const { container } = render(<EmptyState title="No items" />);
      const icon = container.querySelector(".empty-state-icon");
      expect(icon).not.toBeInTheDocument();
    });
  });

  describe("title", () => {
    it("renders title class and text", () => {
      const { container } = render(<EmptyState title="No items found" />);
      const title = container.querySelector(".empty-state-title");
      expect(title).toBeInTheDocument();
      expect(title).toHaveTextContent("No items found");
    });

    it("displays title as text", () => {
      render(<EmptyState title="Empty state" />);
      expect(screen.getByText("Empty state")).toBeInTheDocument();
    });

    it("renders element title", () => {
      render(<EmptyState title={<strong>No Data</strong>} />);
      expect(screen.getByText("No Data")).toBeInTheDocument();
    });
  });

  describe("description", () => {
    it("renders description class when provided", () => {
      const { container } = render(
        <EmptyState title="No items" description="Try creating a new item" />,
      );
      const description = container.querySelector(".empty-state-description");
      expect(description).toBeInTheDocument();
    });

    it("displays description text", () => {
      render(<EmptyState title="No items" description="No results match your search" />);
      expect(screen.getByText("No results match your search")).toBeInTheDocument();
    });

    it("does not render description when not provided", () => {
      const { container } = render(<EmptyState title="No items" />);
      const description = container.querySelector(".empty-state-description");
      expect(description).not.toBeInTheDocument();
    });
  });

  describe("action button", () => {
    it("renders button when action is provided", () => {
      render(<EmptyState title="No items" action={{ label: "Create New", onClick: vi.fn() }} />);
      expect(screen.getByRole("button", { name: "Create New" })).toBeInTheDocument();
    });

    it("does not render button when action not provided", () => {
      render(<EmptyState title="No items" />);
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("applies primary variant and sm size to action button", () => {
      render(<EmptyState title="No items" action={{ label: "Create", onClick: vi.fn() }} />);
      const button = screen.getByRole("button", { name: "Create" });
      expect(button).toHaveClass("btn-primary");
      expect(button).toHaveClass("btn-sm");
    });

    it("applies empty-state-action class", () => {
      render(<EmptyState title="No items" action={{ label: "Create", onClick: vi.fn() }} />);
      const button = screen.getByTestId("empty-state-action");
      expect(button).toHaveClass("empty-state-action");
    });

    it("calls action callback when button is clicked", async () => {
      const onClick = vi.fn();
      const user = userEvent.setup();
      render(<EmptyState title="No items" action={{ label: "Create", onClick }} />);
      const button = screen.getByRole("button", { name: "Create" });
      await user.click(button);
      expect(onClick).toHaveBeenCalled();
    });
  });

  describe("complete structure", () => {
    it("renders all elements together", () => {
      const onClick = vi.fn();
      const { container } = render(
        <EmptyState
          icon={<span>🎯</span>}
          title="No Results"
          description="Your search didn't match any items"
          action={{ label: "Clear filters", onClick }}
          variant="default"
        />,
      );
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
      expect(container.querySelector(".empty-state-icon")).toBeInTheDocument();
      expect(screen.getByText("No Results")).toBeInTheDocument();
      expect(screen.getByText("Your search didn't match any items")).toBeInTheDocument();
      expect(screen.getByTestId("empty-state-action")).toBeInTheDocument();
    });
  });
});
