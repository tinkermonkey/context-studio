import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { ErrorBoundary } from "../ErrorBoundary";

describe("ErrorBoundary", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("rendering without errors", () => {
    it("renders children when no error occurs", () => {
      render(
        <ErrorBoundary>
          <div>Content</div>
        </ErrorBoundary>,
      );
      expect(screen.getByText("Content")).toBeInTheDocument();
    });

    it("renders multiple children", () => {
      render(
        <ErrorBoundary>
          <div>Child 1</div>
          <div>Child 2</div>
        </ErrorBoundary>,
      );
      expect(screen.getByText("Child 1")).toBeInTheDocument();
      expect(screen.getByText("Child 2")).toBeInTheDocument();
    });
  });

  describe("error catching", () => {
    it("catches errors thrown by children and displays fallback", () => {
      const ThrowError = () => {
        throw new Error("Test error message");
      };

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>,
      );

      expect(screen.getByText("Something went wrong")).toBeInTheDocument();
      expect(screen.getByText("Test error message")).toBeInTheDocument();
    });

    it("displays error message in fallback UI", () => {
      const ThrowError = () => {
        throw new Error("Custom error");
      };

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>,
      );

      expect(screen.getByText("Custom error")).toBeInTheDocument();
    });

    it("displays generic message when error has no message", () => {
      const ThrowError = () => {
        throw new Error("");
      };

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>,
      );

      expect(screen.getByText("An unexpected error occurred")).toBeInTheDocument();
    });
  });

  describe("fallback UI", () => {
    it("renders error state with correct structure", () => {
      const ThrowError = () => {
        throw new Error("Test");
      };

      const { container } = render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>,
      );

      expect(screen.getByText("Something went wrong")).toBeInTheDocument();
      expect(container.querySelector("h1")).toBeInTheDocument();
      expect(container.querySelector("p")).toBeInTheDocument();
    });

    it("renders try again button in fallback", () => {
      const ThrowError = () => {
        throw new Error("Test");
      };

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>,
      );

      expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    });

    it("button has btn class", () => {
      const ThrowError = () => {
        throw new Error("Test");
      };

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>,
      );

      const button = screen.getByRole("button", { name: "Try again" });
      expect(button).toHaveClass("btn");
    });
  });

  describe("error recovery", () => {
    it("resets error state when try again button is clicked", async () => {
      let shouldThrow = true;

      const ConditionalThrow = () => {
        if (shouldThrow) {
          throw new Error("Initial error");
        }
        return <div>Content loaded</div>;
      };

      const { rerender } = render(
        <ErrorBoundary>
          <ConditionalThrow />
        </ErrorBoundary>,
      );

      expect(screen.getByText("Something went wrong")).toBeInTheDocument();

      shouldThrow = false;
      const button = screen.getByRole("button", { name: "Try again" });
      await userEvent.click(button);

      rerender(
        <ErrorBoundary>
          <ConditionalThrow />
        </ErrorBoundary>,
      );

      expect(screen.getByText("Content loaded")).toBeInTheDocument();
    });
  });

  describe("console logging", () => {
    it("logs error to console", () => {
      const consoleSpy = vi.spyOn(console, "error");

      const ThrowError = () => {
        throw new Error("Test error");
      };

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>,
      );

      expect(consoleSpy).toHaveBeenCalledWith("Error boundary caught:", expect.any(Error));
    });
  });
});
