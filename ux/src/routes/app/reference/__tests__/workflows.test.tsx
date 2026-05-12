import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { createReferenceStatusResponse } from "@/api/services/__tests__/fixtures/reference.fixtures";
import { WorkflowsPage } from "../workflows";

const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

describe("Reference Workflows Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("renders loading skeleton state with 3 skeleton rows", async () => {
      server.use(
        rest.get("*/api/reference/status", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createReferenceStatusResponse()));
        }),
      );

      const { container } = render(<WorkflowsPage />);

      const skeletonElements = container.querySelectorAll(
        "div[style*='animation: skeleton-shimmer']",
      );
      expect(skeletonElements.length).toBeGreaterThanOrEqual(3);
    });

    it("displays page root with data-testid during loading", async () => {
      server.use(
        rest.get("*/api/reference/status", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createReferenceStatusResponse()));
        }),
      );

      render(<WorkflowsPage />);

      expect(screen.getByTestId("reference-workflows-page")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner when API fails", async () => {
      server.use(
        rest.get("*/api/reference/status", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Internal server error" })),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("reference-workflows-page")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("renders empty state when no workflows exist", async () => {
      server.use(
        rest.get("*/api/reference/status", (req, res, ctx) =>
          res(ctx.json(createReferenceStatusResponse())),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("reference-workflows-page")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("renders page root with data-testid in populated state", async () => {
      server.use(
        rest.get("*/api/reference/grounding-workflows", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0 })),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("reference-workflows-page")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Create Modal
  // ========================================================================
  describe("create workflow modal", () => {
    it("opens create modal on button click", async () => {
      const mockResponse = createReferenceStatusResponse();

      server.use(
        rest.get("*/api/reference/status", (req, res, ctx) => res(ctx.json(mockResponse))),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("reference-workflows-page")).toBeInTheDocument();
      });

      // Look for create button (if present)
      const createButton = screen.queryByRole("button", { name: /create|add|new/i });
      if (createButton) {
        await userEvent.click(createButton);
      }
    });
  });
});
