import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Button } from "../Button";

describe("Button", () => {
  describe("CSS class variants", () => {
    it("applies btn base class", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn");
    });

    it("applies primary variant class", () => {
      render(<Button variant="primary">Click me</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-primary");
    });

    it("applies accent variant class", () => {
      render(<Button variant="accent">Click me</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-accent");
    });

    it("applies ghost variant class by default", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-ghost");
    });

    it("applies danger variant class", () => {
      render(<Button variant="danger">Delete</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-danger");
    });

    it("applies icon variant class", () => {
      render(<Button variant="icon">✕</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-icon");
    });
  });

  describe("size modifiers", () => {
    it("applies btn-sm class when size is sm", () => {
      render(<Button size="sm">Small</Button>);
      expect(screen.getByRole("button")).toHaveClass("btn-sm");
    });

    it("applies both variant and size classes together", () => {
      render(
        <Button variant="primary" size="sm">
          Small Primary
        </Button>,
      );
      const btn = screen.getByRole("button");
      expect(btn).toHaveClass("btn");
      expect(btn).toHaveClass("btn-primary");
      expect(btn).toHaveClass("btn-sm");
    });
  });

  describe("disabled state", () => {
    it("is not disabled by default", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).not.toBeDisabled();
    });

    it("is disabled when disabled prop is true", () => {
      render(<Button disabled>Disabled</Button>);
      expect(screen.getByRole("button")).toBeDisabled();
    });

    it("applies disabled attribute to disabled buttons", () => {
      render(<Button disabled>Disabled</Button>);
      expect(screen.getByRole("button")).toHaveAttribute("disabled");
    });
  });

  describe("accessibility", () => {
    it("renders as a button element", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).toBeInTheDocument();
    });
  });

  describe("custom classes", () => {
    it("accepts additional className prop", () => {
      render(<Button className="custom-class">Click me</Button>);
      const btn = screen.getByRole("button");
      expect(btn).toHaveClass("btn");
      expect(btn).toHaveClass("custom-class");
    });
  });

  describe("content", () => {
    it("renders children text", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByText("Click me")).toBeInTheDocument();
    });

    it("renders children elements", () => {
      render(
        <Button>
          <span>Icon</span> Label
        </Button>,
      );
      expect(screen.getByText("Icon")).toBeInTheDocument();
      expect(screen.getByText("Label")).toBeInTheDocument();
    });
  });
});
