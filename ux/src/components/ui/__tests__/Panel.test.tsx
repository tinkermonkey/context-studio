import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Panel } from "../Panel";

describe("Panel", () => {
  describe("CSS class styling", () => {
    it("applies panel base class", () => {
      const { container } = render(<Panel>Content</Panel>);
      expect(container.querySelector(".panel")).toBeInTheDocument();
    });

    it("always renders panel-body class", () => {
      const { container } = render(<Panel>Content</Panel>);
      expect(container.querySelector(".panel-body")).toBeInTheDocument();
    });
  });

  describe("title and header", () => {
    it("renders panel-head when title is provided", () => {
      const { container } = render(<Panel title="Title">Content</Panel>);
      expect(container.querySelector(".panel-head")).toBeInTheDocument();
    });

    it("does not render panel-head when title is not provided", () => {
      const { container } = render(<Panel>Content</Panel>);
      expect(container.querySelector(".panel-head")).not.toBeInTheDocument();
    });

    it("renders panel-title class inside panel-head", () => {
      const { container } = render(<Panel title="My Title">Content</Panel>);
      const title = container.querySelector(".panel-title");
      expect(title).toBeInTheDocument();
      expect(title).toHaveTextContent("My Title");
    });

    it("renders title text content", () => {
      render(<Panel title="Section Title">Content</Panel>);
      expect(screen.getByText("Section Title")).toBeInTheDocument();
    });

    it("renders element title", () => {
      render(
        <Panel title={<strong>Bold Title</strong>}>
          Content
        </Panel>,
      );
      expect(screen.getByText("Bold Title")).toBeInTheDocument();
    });
  });

  describe("actions", () => {
    it("renders actions in panel-head when provided", () => {
      const { container } = render(
        <Panel title="Title" actions={<button>Action</button>}>
          Content
        </Panel>,
      );
      expect(container.querySelector(".panel-head")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Action" })).toBeInTheDocument();
    });

    it("renders actions in correct position within panel-head", () => {
      const { container } = render(
        <Panel title="Title" actions={<span data-testid="action">Action</span>}>
          Content
        </Panel>,
      );
      const panelHead = container.querySelector(".panel-head");
      const action = screen.getByTestId("action");
      expect(panelHead).toContainElement(action);
    });
  });

  describe("content", () => {
    it("renders children in panel-body", () => {
      const { container } = render(<Panel>Body Content</Panel>);
      const body = container.querySelector(".panel-body");
      expect(body).toHaveTextContent("Body Content");
    });

    it("renders element children in panel-body", () => {
      render(
        <Panel>
          <p>Paragraph</p>
          <button>Button</button>
        </Panel>,
      );
      expect(screen.getByText("Paragraph")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Button" })).toBeInTheDocument();
    });
  });

  describe("custom classes", () => {
    it("accepts additional className prop on panel container", () => {
      const { container } = render(
        <Panel className="custom-class">
          Content
        </Panel>,
      );
      const panel = container.querySelector(".panel");
      expect(panel).toHaveClass("panel");
      expect(panel).toHaveClass("custom-class");
    });
  });

  describe("complete structure", () => {
    it("renders panel with title, actions, and content", () => {
      const { container } = render(
        <Panel title="Full Panel" actions={<span>✕</span>}>
          Panel content goes here
        </Panel>,
      );
      expect(container.querySelector(".panel")).toBeInTheDocument();
      expect(container.querySelector(".panel-head")).toBeInTheDocument();
      expect(container.querySelector(".panel-body")).toBeInTheDocument();
      expect(screen.getByText("Full Panel")).toBeInTheDocument();
      expect(screen.getByText("Panel content goes here")).toBeInTheDocument();
      expect(screen.getByText("✕")).toBeInTheDocument();
    });
  });
});
