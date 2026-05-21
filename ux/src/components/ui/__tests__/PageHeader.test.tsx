import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { PageHeader } from "../PageHeader";

describe("PageHeader", () => {
  describe("CSS classes", () => {
    it("applies page-header class to root element", () => {
      const { container } = render(<PageHeader eyebrow="Eyebrow" title="Test Title" />);
      const header = container.querySelector("[data-testid='page-header']");
      expect(header).toHaveClass("page-header");
    });

    it("merges custom className with base class", () => {
      const { container } = render(
        <PageHeader eyebrow="Eyebrow" title="Test Title" className="custom-class" />,
      );
      const header = container.querySelector("[data-testid='page-header']");
      expect(header).toHaveClass("page-header");
      expect(header).toHaveClass("custom-class");
    });

    it("does not add empty className to class list", () => {
      const { container } = render(
        <PageHeader eyebrow="Eyebrow" title="Test Title" className="" />,
      );
      const header = container.querySelector("[data-testid='page-header']");
      expect(header?.className).toBe("page-header");
    });
  });

  describe("data-testid attribute", () => {
    it("has data-testid on root element", () => {
      const { container } = render(<PageHeader eyebrow="Eyebrow" title="Test Title" />);
      const header = container.querySelector("[data-testid='page-header']");
      expect(header).toBeInTheDocument();
      expect(header?.getAttribute("data-testid")).toBe("page-header");
    });
  });

  describe("heading role and structure", () => {
    it("renders title as h1 element", () => {
      render(<PageHeader eyebrow="Eyebrow" title="Page Title" />);
      const heading = screen.getByRole("heading", { level: 1 });
      expect(heading).toBeInTheDocument();
      expect(heading.tagName).toBe("H1");
    });

    it("renders h1 with correct text content", () => {
      render(<PageHeader eyebrow="Eyebrow" title="My Page Title" />);
      const heading = screen.getByRole("heading", { level: 1 });
      expect(heading).toHaveTextContent("My Page Title");
    });

    it("applies page-header__title class to h1", () => {
      const { container } = render(<PageHeader eyebrow="Eyebrow" title="Test Title" />);
      const heading = container.querySelector(".page-header__title");
      expect(heading).toBeInTheDocument();
      expect(heading?.tagName).toBe("H1");
    });
  });

  describe("eyebrow prop", () => {
    it("renders eyebrow when provided", () => {
      render(<PageHeader eyebrow="Eyebrow Text" title="Title" />);
      expect(screen.getByText("Eyebrow Text")).toBeInTheDocument();
    });

    it("applies page-header__eyebrow class to eyebrow", () => {
      const { container } = render(<PageHeader eyebrow="Eyebrow Text" title="Title" />);
      const eyebrow = container.querySelector(".page-header__eyebrow");
      expect(eyebrow).toBeInTheDocument();
      expect(eyebrow).toHaveTextContent("Eyebrow Text");
    });

    it("does not render eyebrow container when eyebrow is not provided", () => {
      const { container } = render(<PageHeader eyebrow="" title="Title" />);
      const eyebrow = container.querySelector(".page-header__eyebrow");
      expect(eyebrow).not.toBeInTheDocument();
    });
  });

  describe("subtitle prop", () => {
    it("renders subtitle when provided", () => {
      render(<PageHeader eyebrow="Eyebrow" title="Title" subtitle="Subtitle Text" />);
      expect(screen.getByText("Subtitle Text")).toBeInTheDocument();
    });

    it("applies page-header__subtitle class to subtitle", () => {
      const { container } = render(
        <PageHeader eyebrow="Eyebrow" title="Title" subtitle="Subtitle Text" />,
      );
      const subtitle = container.querySelector(".page-header__subtitle");
      expect(subtitle).toBeInTheDocument();
      expect(subtitle).toHaveTextContent("Subtitle Text");
    });

    it("does not render subtitle when not provided", () => {
      const { container } = render(<PageHeader eyebrow="Eyebrow" title="Title" />);
      const subtitle = container.querySelector(".page-header__subtitle");
      expect(subtitle).not.toBeInTheDocument();
    });
  });

  describe("idChip prop", () => {
    it("renders idChip when provided", () => {
      render(<PageHeader eyebrow="Eyebrow" title="Title" idChip="ID-12345" />);
      expect(screen.getByText("ID-12345")).toBeInTheDocument();
    });

    it("applies page-header__id-chip class to idChip", () => {
      const { container } = render(
        <PageHeader eyebrow="Eyebrow" title="Title" idChip="ID-12345" />,
      );
      const idChip = container.querySelector(".page-header__id-chip");
      expect(idChip).toBeInTheDocument();
      expect(idChip).toHaveTextContent("ID-12345");
    });

    it("does not render idChip when not provided", () => {
      const { container } = render(<PageHeader eyebrow="Eyebrow" title="Title" />);
      const idChip = container.querySelector(".page-header__id-chip");
      expect(idChip).not.toBeInTheDocument();
    });
  });

  describe("actions prop", () => {
    it("renders actions when provided as ReactNode", () => {
      render(
        <PageHeader eyebrow="Eyebrow" title="Title" actions={<button>Action Button</button>} />,
      );
      expect(screen.getByRole("button", { name: "Action Button" })).toBeInTheDocument();
    });

    it("applies page-header__actions class to actions container", () => {
      const { container } = render(
        <PageHeader eyebrow="Eyebrow" title="Title" actions={<span>Actions</span>} />,
      );
      const actions = container.querySelector(".page-header__actions");
      expect(actions).toBeInTheDocument();
      expect(actions).toHaveTextContent("Actions");
    });

    it("does not render actions container when not provided", () => {
      const { container } = render(<PageHeader eyebrow="Eyebrow" title="Title" />);
      const actions = container.querySelector(".page-header__actions");
      expect(actions).not.toBeInTheDocument();
    });

    it("renders multiple actions in actions container", () => {
      render(
        <PageHeader
          eyebrow="Eyebrow"
          title="Title"
          actions={
            <div>
              <button>Edit</button>
              <button>Delete</button>
            </div>
          }
        />,
      );
      expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    });
  });

  describe("all props together", () => {
    it("renders all components correctly", () => {
      const { container } = render(
        <PageHeader
          eyebrow="API Reference"
          title="Documentation"
          subtitle="Complete API documentation"
          idChip="v1.0"
          actions={<button>Edit</button>}
        />,
      );

      expect(screen.getByText("API Reference")).toBeInTheDocument();
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Documentation");
      expect(screen.getByText("Complete API documentation")).toBeInTheDocument();
      expect(screen.getByText("v1.0")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();

      const header = container.querySelector("[data-testid='page-header']");
      expect(header).toBeInTheDocument();
    });
  });

  describe("HTML attributes and props spreading", () => {
    it("spreads HTML attributes to root element", () => {
      const { container } = render(
        <PageHeader
          eyebrow="Eyebrow"
          title="Title"
          data-custom-attr="custom-value"
          aria-label="Page header"
        />,
      );
      const header = container.querySelector("[data-testid='page-header']");
      expect(header?.getAttribute("data-custom-attr")).toBe("custom-value");
      expect(header?.getAttribute("aria-label")).toBe("Page header");
    });

    it("does not have banner role on root element", () => {
      const { container } = render(<PageHeader eyebrow="Eyebrow" title="Title" />);
      const header = container.querySelector("[data-testid='page-header']");
      expect(header?.getAttribute("role")).not.toBe("banner");
    });
  });

  describe("required props", () => {
    it("requires eyebrow and title props", () => {
      // This is a TypeScript check, but we verify the component renders with required props
      render(<PageHeader eyebrow="Eyebrow" title="Title" />);
      expect(screen.getByText("Eyebrow")).toBeInTheDocument();
      expect(screen.getByText("Title")).toBeInTheDocument();
    });
  });
});
