import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
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
        expect(screen.getByText(/Failed to load grounding workflows/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("renders empty state when no workflows exist", async () => {
      server.use(
        rest.get("*/api/reference/grounding-workflows", (req, res, ctx) =>
          res(ctx.json([])),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        const emptyState = screen.getByTestId("empty-state");
        expect(emptyState).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("renders table with workflow rows when data loads", async () => {
      const mockWorkflows = [
        {
          id: "workflow-1",
          title: "Entity Extraction",
          source: "anthropic",
          class_scope: ["Person", "Organization"],
          status: "active" as const,
          last_run: new Date().toISOString(),
        },
        {
          id: "workflow-2",
          title: "Relationship Detection",
          source: "spacy",
          class_scope: ["Event"],
          status: "active" as const,
          last_run: new Date().toISOString(),
        },
      ];

      server.use(
        rest.get("*/api/reference/grounding-workflows", (req, res, ctx) =>
          res(ctx.json(mockWorkflows)),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText("Entity Extraction")).toBeInTheDocument();
        expect(screen.getByText("Relationship Detection")).toBeInTheDocument();
      });
    });

    it("asserts schema-page-layout is present when workflows are rendered", async () => {
      const mockWorkflows = [
        {
          id: "workflow-1",
          title: "Entity Extraction",
          source: "anthropic",
          class_scope: ["Person"],
          status: "active" as const,
          last_run: new Date().toISOString(),
        },
      ];

      server.use(
        rest.get("*/api/reference/grounding-workflows", (req, res, ctx) =>
          res(ctx.json(mockWorkflows)),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("schema-page-layout")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Create Modal
  // ========================================================================
  describe("create workflow modal", () => {
    it("opens create modal on button click", async () => {
      server.use(
        rest.get("*/api/reference/grounding-workflows", (req, res, ctx) =>
          res(ctx.json([])),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("new-workflow-button")).toBeInTheDocument();
      });

      const createButton = screen.getByTestId("new-workflow-button");
      await userEvent.click(createButton);

      await waitFor(() => {
        const modal = screen.getByRole("dialog");
        expect(modal).toBeInTheDocument();
      });
    });
  });
});
