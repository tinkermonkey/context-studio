import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { SchemaPageLayout } from "../SchemaPageLayout";

interface TestEntity {
  id: string;
  name: string;
}

const mockData: TestEntity[] = [
  { id: "1", name: "Entity 1" },
  { id: "2", name: "Entity 2" },
  { id: "3", name: "Entity 3" },
];

describe("SchemaPageLayout", () => {
  describe("data-testid attributes", () => {
    it("has schema-page-layout data-testid", () => {
      render(
        <SchemaPageLayout data={mockData}>
          <div>Content</div>
        </SchemaPageLayout>,
      );
      expect(screen.getByTestId("schema-page-layout")).toBeInTheDocument();
    });

    it("has schema-inspector-container data-testid when entity is selected", () => {
      render(
        <SchemaPageLayout
          data={mockData}
          selectedId="1"
          renderInspectorContent={(entity) => <div>Details for {entity.name}</div>}
        >
          <div>Content</div>
        </SchemaPageLayout>,
      );
      expect(screen.getByTestId("schema-inspector-container")).toBeInTheDocument();
    });

    it("does not render drawer container when no entity selected", () => {
      render(
        <SchemaPageLayout
          data={mockData}
          renderInspectorContent={(entity) => <div>Details for {entity.name}</div>}
        >
          <div>Content</div>
        </SchemaPageLayout>,
      );
      expect(screen.queryByTestId("schema-inspector-container")).not.toBeInTheDocument();
    });
  });

  describe("children rendering", () => {
    it("renders children content", () => {
      render(
        <SchemaPageLayout data={mockData}>
          <div>Main content</div>
        </SchemaPageLayout>,
      );
      expect(screen.getByText("Main content")).toBeInTheDocument();
    });

    it("renders multiple children", () => {
      render(
        <SchemaPageLayout data={mockData}>
          <div>First</div>
          <div>Second</div>
        </SchemaPageLayout>,
      );
      expect(screen.getByText("First")).toBeInTheDocument();
      expect(screen.getByText("Second")).toBeInTheDocument();
    });

    it("renders element children", () => {
      render(
        <SchemaPageLayout data={mockData}>
          <button>Click me</button>
        </SchemaPageLayout>,
      );
      expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
    });
  });

  describe("drawer content rendering", () => {
    it("renders drawer content when entity is selected", () => {
      render(
        <SchemaPageLayout
          data={mockData}
          selectedId="1"
          renderInspectorContent={(entity) => <div>Details: {entity.name}</div>}
        >
          <div>Content</div>
        </SchemaPageLayout>,
      );
      expect(screen.getByText("Details: Entity 1")).toBeInTheDocument();
    });

    it("does not render drawer content when no entity selected", () => {
      render(
        <SchemaPageLayout
          data={mockData}
          renderInspectorContent={(entity) => <div>Details: {entity.name}</div>}
        >
          <div>Content</div>
        </SchemaPageLayout>,
      );
      expect(screen.queryByText(/Details:/)).not.toBeInTheDocument();
    });

    it("does not render drawer when renderInspectorContent not provided", () => {
      render(
        <SchemaPageLayout data={mockData} selectedId="1">
          <div>Content</div>
        </SchemaPageLayout>,
      );
      expect(screen.queryByTestId("schema-inspector-container")).not.toBeInTheDocument();
    });

    it("renders correct drawer content for selected entity", () => {
      render(
        <SchemaPageLayout
          data={mockData}
          selectedId="2"
          renderInspectorContent={(entity) => <div>Editing: {entity.name}</div>}
        >
          <div>Content</div>
        </SchemaPageLayout>,
      );
      expect(screen.getByText("Editing: Entity 2")).toBeInTheDocument();
    });

    it("updates drawer content when selectedId changes", () => {
      const { rerender } = render(
        <SchemaPageLayout
          data={mockData}
          selectedId="1"
          renderInspectorContent={(entity) => <div>{entity.name}</div>}
        >
          <div>Content</div>
        </SchemaPageLayout>,
      );

      expect(screen.getByText("Entity 1")).toBeInTheDocument();

      rerender(
        <SchemaPageLayout
          data={mockData}
          selectedId="3"
          renderInspectorContent={(entity) => <div>{entity.name}</div>}
        >
          <div>Content</div>
        </SchemaPageLayout>,
      );

      expect(screen.getByText("Entity 3")).toBeInTheDocument();
      expect(screen.queryByText("Entity 1")).not.toBeInTheDocument();
    });
  });

  describe("entity lookup", () => {
    it("finds entity by id in data array", () => {
      render(
        <SchemaPageLayout
          data={mockData}
          selectedId="2"
          renderInspectorContent={(entity) => <div>{entity.name}</div>}
        >
          <div>Content</div>
        </SchemaPageLayout>,
      );
      expect(screen.getByText("Entity 2")).toBeInTheDocument();
    });

    it("does not render drawer for non-existent entity id", () => {
      render(
        <SchemaPageLayout
          data={mockData}
          selectedId="999"
          renderInspectorContent={(entity) => <div>{entity.name}</div>}
        >
          <div>Content</div>
        </SchemaPageLayout>,
      );
      expect(screen.queryByTestId("schema-inspector-container")).not.toBeInTheDocument();
    });
  });

  describe("complete structure", () => {
    it("renders layout with main content and drawer together", () => {
      render(
        <SchemaPageLayout
          data={mockData}
          selectedId="1"
          renderInspectorContent={(entity) => <div>Entity: {entity.name}</div>}
        >
          <div>Main content area</div>
        </SchemaPageLayout>,
      );
      expect(screen.getByTestId("schema-page-layout")).toBeInTheDocument();
      expect(screen.getByText("Main content area")).toBeInTheDocument();
      expect(screen.getByTestId("schema-inspector-container")).toBeInTheDocument();
      expect(screen.getByText("Entity: Entity 1")).toBeInTheDocument();
    });

    it("renders layout with only main content when no selection", () => {
      render(
        <SchemaPageLayout
          data={mockData}
          renderInspectorContent={(entity) => <div>Entity: {entity.name}</div>}
        >
          <div>Main content area</div>
        </SchemaPageLayout>,
      );
      expect(screen.getByTestId("schema-page-layout")).toBeInTheDocument();
      expect(screen.getByText("Main content area")).toBeInTheDocument();
      expect(screen.queryByTestId("schema-inspector-container")).not.toBeInTheDocument();
    });
  });
});
