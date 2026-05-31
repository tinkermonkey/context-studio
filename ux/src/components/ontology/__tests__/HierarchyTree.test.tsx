import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { HierarchyTree } from "../HierarchyTree";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];
type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];
type ClassResponse = components["schemas"]["ClassResponse"];

const taxonomies: TaxonomyResponse[] = [
  { id: "tax-1", identifier: "alpha_taxonomy", title: "Alpha Taxonomy", description: "Alpha root", version: 1, status: "draft" },
  { id: "tax-2", identifier: "beta_taxonomy", title: "Beta Taxonomy", description: "Beta root", version: 1, status: "draft" },
];

const schemes: ConceptSchemeResponse[] = [
  { id: "scheme-1", taxonomy_id: "tax-1", identifier: "scheme_one", title: "Scheme One", description: "First scheme", version: 1, status: "draft" },
  { id: "scheme-2", taxonomy_id: "tax-1", identifier: "scheme_two", title: "Scheme Two", description: "Second scheme", version: 1, status: "draft" },
  { id: "scheme-3", taxonomy_id: "tax-2", identifier: "scheme_three", title: "Scheme Three", description: "Third scheme", version: 1, status: "draft" },
];

const classes: ClassResponse[] = [
  { id: "class-1", concept_scheme_id: "scheme-1", taxonomy_id: "tax-1", identifier: "class_one", title: "Class One", description: "First class", parent_class_id: null, version: 1, status: "draft" },
  { id: "class-2", concept_scheme_id: "scheme-1", taxonomy_id: "tax-1", identifier: "class_two", title: "Class Two", description: "Second class", parent_class_id: null, version: 1, status: "draft" },
  { id: "class-3", concept_scheme_id: "scheme-2", taxonomy_id: "tax-1", identifier: "class_three", title: "Class Three", description: "Third class", parent_class_id: null, version: 1, status: "draft" },
];

function renderTree(overrides?: Partial<Parameters<typeof HierarchyTree>[0]>) {
  return render(
    <HierarchyTree taxonomies={taxonomies} schemes={schemes} classes={classes} {...overrides} />,
  );
}

describe("HierarchyTree", () => {
  describe("structure", () => {
    it("renders every taxonomy as a top-level row", () => {
      renderTree();
      expect(screen.getByTestId("hierarchy-node-tax-1")).toBeInTheDocument();
      expect(screen.getByTestId("hierarchy-node-tax-2")).toBeInTheDocument();
    });

    it("seeds the first taxonomy and its first scheme open", () => {
      renderTree();
      // tax-1 open → both of its schemes visible
      expect(screen.getByTestId("hierarchy-node-scheme-1")).toBeInTheDocument();
      expect(screen.getByTestId("hierarchy-node-scheme-2")).toBeInTheDocument();
      // scheme-1 open → its classes visible
      expect(screen.getByTestId("hierarchy-node-class-1")).toBeInTheDocument();
      expect(screen.getByTestId("hierarchy-node-class-2")).toBeInTheDocument();
    });

    it("keeps collapsed branches out of the DOM", () => {
      renderTree();
      // tax-2 collapsed → its scheme hidden
      expect(screen.queryByTestId("hierarchy-node-scheme-3")).not.toBeInTheDocument();
      // scheme-2 collapsed → its class hidden
      expect(screen.queryByTestId("hierarchy-node-class-3")).not.toBeInTheDocument();
    });

    it("tags each row with the correct kind", () => {
      renderTree();
      expect(screen.getByTestId("hierarchy-node-tax-1")).toHaveAttribute("data-kind", "taxonomy");
      expect(screen.getByTestId("hierarchy-node-scheme-1")).toHaveAttribute("data-kind", "scheme");
      expect(screen.getByTestId("hierarchy-node-class-1")).toHaveAttribute("data-kind", "class");
    });

    it("uses the default domain swatch for all rows", () => {
      renderTree();
      expect(screen.getByTestId("hierarchy-node-tax-1")).toHaveAttribute("data-domain", "default");
      expect(screen.getByTestId("hierarchy-node-class-1")).toHaveAttribute("data-domain", "default");
    });

    it("indents rows by depth", () => {
      renderTree();
      expect(screen.getByTestId("hierarchy-node-tax-1")).toHaveAttribute("data-depth", "0");
      expect(screen.getByTestId("hierarchy-node-scheme-1")).toHaveAttribute("data-depth", "1");
      expect(screen.getByTestId("hierarchy-node-class-1")).toHaveAttribute("data-depth", "2");
    });
  });

  describe("meta counts", () => {
    it("shows pluralized scheme counts on taxonomy rows", () => {
      renderTree();
      expect(screen.getByText("2 schemes")).toBeInTheDocument();
      expect(screen.getByText("1 scheme")).toBeInTheDocument();
    });

    it("shows pluralized class counts on scheme rows", () => {
      renderTree();
      expect(screen.getByText("2 classes")).toBeInTheDocument();
      expect(screen.getByText("1 class")).toBeInTheDocument();
    });
  });

  describe("expand / collapse", () => {
    it("expands a collapsed taxonomy on click", async () => {
      const user = userEvent.setup();
      renderTree();
      expect(screen.queryByTestId("hierarchy-node-scheme-3")).not.toBeInTheDocument();
      await user.click(screen.getByTestId("hierarchy-node-tax-2"));
      expect(screen.getByTestId("hierarchy-node-scheme-3")).toBeInTheDocument();
    });

    it("collapses an open taxonomy on click", async () => {
      const user = userEvent.setup();
      renderTree();
      expect(screen.getByTestId("hierarchy-node-scheme-1")).toBeInTheDocument();
      await user.click(screen.getByTestId("hierarchy-node-tax-1"));
      expect(screen.queryByTestId("hierarchy-node-scheme-1")).not.toBeInTheDocument();
    });

    it("expands a collapsed scheme to reveal its classes", async () => {
      const user = userEvent.setup();
      renderTree();
      expect(screen.queryByTestId("hierarchy-node-class-3")).not.toBeInTheDocument();
      await user.click(screen.getByTestId("hierarchy-node-scheme-2"));
      expect(screen.getByTestId("hierarchy-node-class-3")).toBeInTheDocument();
    });
  });

  describe("class selection", () => {
    it("calls onSelectClass with the class id", async () => {
      const onSelectClass = vi.fn();
      const user = userEvent.setup();
      renderTree({ onSelectClass });
      await user.click(screen.getByTestId("hierarchy-node-class-1"));
      expect(onSelectClass).toHaveBeenCalledWith("class-1");
    });

    it("marks the selected class row", async () => {
      const user = userEvent.setup();
      renderTree();
      await user.click(screen.getByTestId("hierarchy-node-class-1"));
      expect(screen.getByTestId("hierarchy-node-class-1").className).toContain("hierarchy-row--selected");
    });
  });

  describe("loading state", () => {
    it("renders skeleton loaders when loading", () => {
      const { container } = render(<HierarchyTree loading />);
      const hasSkeleton = container.querySelector(".skeleton");
      expect(hasSkeleton).toBeInTheDocument();
    });

    it("does not render rows when loading", () => {
      renderTree({ loading: true });
      expect(screen.queryByTestId("hierarchy-node-tax-1")).not.toBeInTheDocument();
    });
  });

  describe("error state", () => {
    it("renders the error message", () => {
      renderTree({ error: new Error("Boom") });
      expect(screen.getByText("Boom")).toBeInTheDocument();
    });

    it("renders a default message when the error has none", () => {
      renderTree({ error: new Error("") });
      expect(screen.getByText("Failed to load class hierarchy")).toBeInTheDocument();
    });

    it("does not render rows when in error", () => {
      renderTree({ error: new Error("Boom") });
      expect(screen.queryByTestId("hierarchy-node-tax-1")).not.toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("renders an empty message when there are no taxonomies", () => {
      render(<HierarchyTree taxonomies={[]} schemes={[]} classes={[]} />);
      expect(screen.getByText("No structure yet")).toBeInTheDocument();
    });

    it("renders an empty message when props are undefined", () => {
      render(<HierarchyTree />);
      expect(screen.getByText("No structure yet")).toBeInTheDocument();
    });
  });
});
