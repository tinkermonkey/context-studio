import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Panel } from "../Panel";

describe("Panel", () => {
  describe("title and header", () => {
    it("renders title text content", () => {
      render(<Panel title="Section Title">Content</Panel>);
      expect(screen.getByText("Section Title")).toBeInTheDocument();
    });

    it("does not render title when not provided", () => {
      render(<Panel>Content</Panel>);
      expect(screen.queryByText(/Section Title|Bold Title/)).not.toBeInTheDocument();
    });
  });

  describe("actions", () => {
    it("renders actions when provided with title", () => {
      render(
        <Panel title="Title" actions={<button>Action</button>}>
          Content
        </Panel>,
      );
      expect(screen.getByRole("button", { name: "Action" })).toBeInTheDocument();
    });

    it("renders action element", () => {
      render(
        <Panel title="Title" actions={<span data-testid="action">Action</span>}>
          Content
        </Panel>,
      );
      expect(screen.getByTestId("action")).toBeInTheDocument();
    });
  });

  describe("content", () => {
    it("renders children content", () => {
      render(<Panel>Body Content</Panel>);
      expect(screen.getByText("Body Content")).toBeInTheDocument();
    });

    it("renders element children", () => {
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

  describe("subtitle and footer", () => {
    it("renders subtitle when provided", () => {
      render(
        <Panel title="Title" subtitle="Subtitle">
          Content
        </Panel>,
      );
      expect(screen.getByText("Subtitle")).toBeInTheDocument();
    });

    it("renders footer when provided", () => {
      render(<Panel footer={<div>Footer content</div>}>Content</Panel>);
      expect(screen.getByText("Footer content")).toBeInTheDocument();
    });
  });

  describe("custom classes", () => {
    it("accepts additional className prop on panel container", () => {
      const { container } = render(<Panel className="custom-class">Content</Panel>);
      const panel = container.querySelector("[class*='custom-class']");
      expect(panel).toBeInTheDocument();
    });
  });

  describe("complete structure", () => {
    it("renders panel with title, actions, and content", () => {
      render(
        <Panel title="Full Panel" actions={<span>✕</span>}>
          Panel content goes here
        </Panel>,
      );
      expect(screen.getByText("Full Panel")).toBeInTheDocument();
      expect(screen.getByText("Panel content goes here")).toBeInTheDocument();
      expect(screen.getByText("✕")).toBeInTheDocument();
    });
  });
});
