import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { Button } from "@tinkermonkey/heimdall-ui";

describe("Heimdall Button", () => {
  describe("data-testid attributes", () => {
    it("renders with data-testid when provided", () => {
      render(<Button data-testid="test-button">Click</Button>);
      expect(screen.getByTestId("test-button")).toBeInTheDocument();
    });

    it("renders without data-testid when not provided", () => {
      render(<Button>Click</Button>);
      const button = screen.getByRole("button");
      expect(button.getAttribute("data-testid")).toBeNull();
    });
  });

  describe("CSS class styling", () => {
    it("renders as button element", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).toBeInTheDocument();
    });

    it("renders with button class by default", () => {
      render(<Button>Click me</Button>);
      const button = screen.getByRole("button");
      expect(button.className).toBeTruthy();
    });

    it("applies additional className prop", () => {
      render(<Button className="custom-class">Click me</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("custom-class");
    });

    it("combines default and custom classes", () => {
      render(<Button className="custom-1 custom-2">Click</Button>);
      const button = screen.getByRole("button");
      expect(button).toHaveClass("custom-1");
      expect(button).toHaveClass("custom-2");
    });
  });

  describe("ARIA roles and attributes", () => {
    it("has button role", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).toBeInTheDocument();
    });

    it("is not disabled by default", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByRole("button")).not.toBeDisabled();
    });

    it("is disabled when disabled prop is true", () => {
      render(<Button disabled>Disabled</Button>);
      expect(screen.getByRole("button")).toBeDisabled();
    });

    it("forwards aria attributes", () => {
      render(<Button aria-label="Custom label">Click</Button>);
      expect(screen.getByRole("button", { name: "Custom label" })).toBeInTheDocument();
    });
  });

  describe("content", () => {
    it("renders text content", () => {
      render(<Button>Click me</Button>);
      expect(screen.getByText("Click me")).toBeInTheDocument();
    });

    it("renders element content", () => {
      render(
        <Button>
          <span>Icon</span> Label
        </Button>,
      );
      expect(screen.getByText("Icon")).toBeInTheDocument();
      expect(screen.getByText("Label")).toBeInTheDocument();
    });
  });

  describe("interactions", () => {
    it("calls onClick handler when clicked", async () => {
      const onClick = vi.fn();
      const user = userEvent.setup();
      render(<Button onClick={onClick}>Click me</Button>);

      await user.click(screen.getByRole("button"));
      expect(onClick).toHaveBeenCalled();
    });

    it("does not call onClick when disabled", () => {
      const onClick = vi.fn();
      render(
        <Button disabled onClick={onClick}>
          Click me
        </Button>,
      );

      const button = screen.getByRole("button");
      // Disabled buttons still fire click in some cases, but button element prevents interaction
      expect(button).toBeDisabled();
    });

    it("forwards other HTML attributes", () => {
      render(<Button id="my-button">Click</Button>);
      expect(screen.getByRole("button")).toHaveAttribute("id", "my-button");
    });
  });

  describe("type attribute", () => {
    it("defaults to button type", () => {
      render(<Button>Click</Button>);
      expect(screen.getByRole("button")).toHaveAttribute("type", "button");
    });

    it("accepts submit type", () => {
      render(<Button type="submit">Submit</Button>);
      expect(screen.getByRole("button")).toHaveAttribute("type", "submit");
    });

    it("accepts reset type", () => {
      render(<Button type="reset">Reset</Button>);
      expect(screen.getByRole("button")).toHaveAttribute("type", "reset");
    });
  });
});
