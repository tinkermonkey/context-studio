import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { HierarchyTree } from "../HierarchyTree";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];

const mockClasses: ClassResponse[] = [
  {
    id: "class-1",
    title: "Root Class",
    concept_scheme_id: "scheme-1",
    taxonomy_id: "taxonomy-1",
    parent_class_id: null,
    created_at: new Date().toISOString(),
    version: 1,
    status: "draft",
  },
  {
    id: "class-2",
    title: "Child Class",
    concept_scheme_id: "scheme-1",
    taxonomy_id: "taxonomy-1",
    parent_class_id: "class-1",
    created_at: new Date().toISOString(),
    version: 1,
    status: "draft",
  },
  {
    id: "class-3",
    title: "Another Root",
    concept_scheme_id: "scheme-1",
    taxonomy_id: "taxonomy-1",
    parent_class_id: null,
    created_at: new Date().toISOString(),
    version: 1,
    status: "draft",
  },
];

const mockHierarchy: ClassResponse[] = [
  {
    id: "root-1",
    title: "Root",
    concept_scheme_id: "scheme-1",
    taxonomy_id: "taxonomy-1",
    parent_class_id: null,
    created_at: new Date().toISOString(),
    version: 1,
    status: "draft",
  },
  {
    id: "child-1",
    title: "Child 1",
    concept_scheme_id: "scheme-1",
    taxonomy_id: "taxonomy-1",
    parent_class_id: "root-1",
    created_at: new Date().toISOString(),
    version: 1,
    status: "draft",
  },
  {
    id: "child-2",
    title: "Child 2",
    concept_scheme_id: "scheme-1",
    taxonomy_id: "taxonomy-1",
    parent_class_id: "root-1",
    created_at: new Date().toISOString(),
    version: 1,
    status: "draft",
  },
  {
    id: "grandchild-1",
    title: "Grandchild",
    concept_scheme_id: "scheme-1",
    taxonomy_id: "taxonomy-1",
    parent_class_id: "child-1",
    created_at: new Date().toISOString(),
    version: 1,
    status: "draft",
  },
];

describe("HierarchyTree", () => {
  describe("rendering nodes", () => {
    it("renders root class nodes", () => {
      render(<HierarchyTree classes={mockClasses} />);
      expect(screen.getByTestId("hierarchy-node-class-1")).toBeInTheDocument();
      expect(screen.getByTestId("hierarchy-node-class-3")).toBeInTheDocument();
    });

    it("displays root node titles", () => {
      render(<HierarchyTree classes={mockClasses} />);
      expect(screen.getByText("Root Class")).toBeInTheDocument();
      expect(screen.getByText("Another Root")).toBeInTheDocument();
    });

    it("renders a hierarchy tree container", () => {
      const { container } = render(<HierarchyTree classes={mockClasses} />);
      expect(container.querySelector('[data-testid="hierarchy-node-class-1"]')).toBeInTheDocument();
    });
  });

  describe("node data attributes", () => {
    it("has hierarchy-node testid with class id", () => {
      render(<HierarchyTree classes={mockClasses} />);
      const node = screen.getByTestId("hierarchy-node-class-1");
      expect(node).toBeInTheDocument();
    });

    it("has data-domain attribute with concept scheme id", () => {
      const { container } = render(<HierarchyTree classes={mockClasses} />);
      const node = container.querySelector('[data-testid="hierarchy-node-class-1"]');
      expect(node).toHaveAttribute("data-domain", "scheme-1");
    });
  });

  describe("expand/collapse functionality", () => {
    it("renders expand button for nodes with children", () => {
      render(<HierarchyTree classes={mockHierarchy} />);
      const expandButton = screen.getByLabelText("Expand");
      expect(expandButton).toBeInTheDocument();
    });

    it("does not render expand button for leaf nodes", () => {
      render(<HierarchyTree classes={[mockClasses[0]]} />);
      const expandButton = screen.queryByLabelText("Expand");
      expect(expandButton).not.toBeInTheDocument();
    });

    it("toggles expand button label on click", async () => {
      const user = userEvent.setup();
      render(<HierarchyTree classes={mockHierarchy} />);
      let expandButton = screen.getByLabelText("Expand");
      await user.click(expandButton);
      expandButton = screen.getByLabelText("Collapse");
      expect(expandButton).toBeInTheDocument();
    });

    it("shows children when node is expanded", async () => {
      const user = userEvent.setup();
      render(<HierarchyTree classes={mockHierarchy} />);
      expect(screen.queryByText("Child 1")).not.toBeInTheDocument();
      const expandButton = screen.getByLabelText("Expand");
      await user.click(expandButton);
      expect(screen.getByText("Child 1")).toBeInTheDocument();
    });

    it("hides children when node is collapsed", async () => {
      const user = userEvent.setup();
      render(<HierarchyTree classes={mockHierarchy} />);
      const expandButton = screen.getByLabelText("Expand");
      await user.click(expandButton);
      expect(screen.getByText("Child 1")).toBeInTheDocument();
      const collapseButton = screen.getByLabelText("Collapse");
      await user.click(collapseButton);
      expect(screen.queryByText("Child 1")).not.toBeInTheDocument();
    });
  });

  describe("child count meta", () => {
    it("renders child count for nodes with children", () => {
      render(<HierarchyTree classes={mockHierarchy} />);
      expect(screen.getByText("2")).toBeInTheDocument();
    });

    it("does not render child count for leaf nodes", () => {
      render(<HierarchyTree classes={[mockHierarchy[2]]} />);
      expect(screen.queryByText("2")).not.toBeInTheDocument();
    });
  });

  describe("node selection", () => {
    it("calls onNodeSelect when node is clicked", async () => {
      const onNodeSelect = vi.fn();
      const user = userEvent.setup();
      render(<HierarchyTree classes={mockClasses} onNodeSelect={onNodeSelect} />);
      const node = screen.getByTestId("hierarchy-node-class-1");
      await user.click(node);
      expect(onNodeSelect).toHaveBeenCalledWith("class-1");
    });

    it("does not call onNodeSelect when not provided", async () => {
      const user = userEvent.setup();
      render(<HierarchyTree classes={mockClasses} />);
      const node = screen.getByTestId("hierarchy-node-class-1");
      await user.click(node);
    });

    it("calls onNodeSelect with correct child id when child is clicked", async () => {
      const onNodeSelect = vi.fn();
      const user = userEvent.setup();
      render(<HierarchyTree classes={mockHierarchy} onNodeSelect={onNodeSelect} />);
      const expandButton = screen.getByLabelText("Expand");
      await user.click(expandButton);
      const childNode = screen.getByTestId("hierarchy-node-child-1");
      await user.click(childNode);
      expect(onNodeSelect).toHaveBeenCalledWith("child-1");
    });
  });

  describe("loading state", () => {
    it("renders skeleton loaders when loading is true", () => {
      const { container } = render(<HierarchyTree classes={[]} loading={true} />);
      const skeletons = container.querySelectorAll("div");
      const hasLoading = Array.from(skeletons).some((el) =>
        el.style.animation?.includes("skeleton-shimmer"),
      );
      expect(hasLoading).toBe(true);
    });

    it("does not render nodes when loading", () => {
      render(<HierarchyTree classes={mockClasses} loading={true} />);
      expect(screen.queryByText("Root Class")).not.toBeInTheDocument();
    });
  });

  describe("error state", () => {
    it("renders error message when error provided", () => {
      const error = new Error("Failed to load");
      render(<HierarchyTree classes={[]} error={error} />);
      expect(screen.getByText("Failed to load")).toBeInTheDocument();
    });

    it("renders default error message when error has no message", () => {
      render(<HierarchyTree classes={[]} error={new Error("")} />);
      expect(screen.getByText("Failed to load class hierarchy")).toBeInTheDocument();
    });

    it("does not render nodes when error", () => {
      render(<HierarchyTree classes={mockClasses} error={new Error("Error")} />);
      expect(screen.queryByText("Root Class")).not.toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("renders empty message when no classes provided", () => {
      render(<HierarchyTree classes={[]} />);
      expect(screen.getByText("No classes found")).toBeInTheDocument();
    });

    it("does not render nodes when classes is undefined", () => {
      render(<HierarchyTree />);
      expect(screen.getByText("No classes found")).toBeInTheDocument();
    });
  });

  describe("max depth", () => {
    it("limits expansion to maxDepth", async () => {
      const user = userEvent.setup();
      render(<HierarchyTree classes={mockHierarchy} maxDepth={2} />);

      // Expand root (depth 0) - should have expand button
      expect(screen.getAllByLabelText("Expand")).toHaveLength(1);
      await user.click(screen.getAllByLabelText("Expand")[0]);

      // After expanding root, child-1 should be visible and have an expand button
      expect(screen.getByText("Child 1")).toBeInTheDocument();
      expect(screen.getAllByLabelText("Expand")).toHaveLength(1); // Just child-1's expand button

      // Expand child-1 (depth 1) — find the expand button for "Child 1"
      const child1Node = screen.getByTestId("hierarchy-node-child-1");
      const child1Row = child1Node.closest("div");
      const child1ExpandBtn = child1Row?.parentElement?.querySelector("button[aria-label]") as HTMLButtonElement;
      await user.click(child1ExpandBtn);

      // Grandchild should be visible
      expect(screen.getByText("Grandchild")).toBeInTheDocument();

      // Grandchild should NOT have an expand button (depth 2 >= maxDepth 2)
      const grandchildNode = screen.getByTestId("hierarchy-node-grandchild-1");
      const grandchildContainer = grandchildNode.closest("div")?.parentElement;
      const expandButtons = grandchildContainer?.querySelectorAll("button[aria-label]");
      expect(expandButtons?.length || 0).toBe(0);
    });
  });

  describe("accessibility", () => {
    it("expand/collapse buttons have aria labels", () => {
      render(<HierarchyTree classes={mockHierarchy} />);
      expect(screen.getByLabelText("Expand")).toBeInTheDocument();
    });

    it("root nodes have data-testid for semantic identification", () => {
      render(<HierarchyTree classes={mockClasses} />);
      // Only root nodes are rendered without expansion
      expect(screen.getByTestId("hierarchy-node-class-1")).toBeInTheDocument();
      expect(screen.getByTestId("hierarchy-node-class-3")).toBeInTheDocument();
    });
  });

  describe("complete structure", () => {
    it("renders full tree with root and children", () => {
      render(<HierarchyTree classes={mockHierarchy} />);
      expect(screen.getByText("Root")).toBeInTheDocument();
      expect(screen.queryByText("Child 1")).not.toBeInTheDocument();
    });

    it("renders tree with expansion", async () => {
      const user = userEvent.setup();
      const onNodeSelect = vi.fn();
      render(<HierarchyTree classes={mockHierarchy} onNodeSelect={onNodeSelect} />);

      // Initial state
      expect(screen.getByText("Root")).toBeInTheDocument();
      expect(screen.queryByText("Child 1")).not.toBeInTheDocument();

      // Expand
      const expandButton = screen.getByLabelText("Expand");
      await user.click(expandButton);
      expect(screen.getByText("Child 1")).toBeInTheDocument();
      expect(screen.getByText("Child 2")).toBeInTheDocument();
    });
  });
});
