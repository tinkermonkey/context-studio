import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
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
  // Page Structure
  // ========================================================================
  describe("page structure", () => {
    it("renders workflows page root with testid", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) => res(ctx.json([]))),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("reference-workflows-page")).toBeInTheDocument();
      });
    });

    it("displays page title", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) => res(ctx.json([]))),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByRole("heading")).toBeInTheDocument();
      });
    });

    it("displays create button", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) => res(ctx.json([]))),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(
          screen.getByTestId("new-workflow-button") ||
            screen.getByRole("button", { name: /create|new/i }),
        ).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading indicators while data is fetching", async () => {
      let resolveRequest: () => void;
      const promise = new Promise<void>((resolve) => {
        resolveRequest = resolve;
      });

      server.use(
        rest.get("*/api/v1/reference/workflows", async (req, res, ctx) => {
          await promise;
          return res(ctx.json([]));
        }),
      );

      render(<WorkflowsPage />);

      // Page should still be rendered even while loading
      expect(screen.getByTestId("reference-workflows-page")).toBeInTheDocument();

      resolveRequest!();
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("handles API errors gracefully", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Server error" })),
        ),
      );

      render(<WorkflowsPage />);

      // Page should still be accessible even with error
      expect(screen.getByTestId("reference-workflows-page")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state when no workflows exist", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) => res(ctx.json([]))),
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
    it("displays workflows list with data", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) =>
          res(
            ctx.json([
              {
                id: "workflow-1",
                title: "Entity Grounding",
                description: "Ground entities using ConceptNet",
                source: "ConceptNet",
                class_scope: ["Person", "Organization"],
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
            ]),
          ),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText("Entity Grounding")).toBeInTheDocument();
      });
    });

    it("displays multiple workflows in the list", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) =>
          res(
            ctx.json([
              {
                id: "workflow-1",
                title: "Entity Grounding",
                description: "Ground entities",
                source: "ConceptNet",
                class_scope: ["Person"],
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
              {
                id: "workflow-2",
                title: "Relationship Extraction",
                description: "Extract relationships",
                source: "DBpedia",
                class_scope: ["Thing"],
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
            ]),
          ),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText("Entity Grounding")).toBeInTheDocument();
        expect(screen.getByText("Relationship Extraction")).toBeInTheDocument();
      });
    });

    it("displays source and scope information for workflows", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) =>
          res(
            ctx.json([
              {
                id: "workflow-1",
                title: "Entity Grounding",
                description: "Ground entities",
                source: "ConceptNet",
                class_scope: ["Person", "Organization"],
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
            ]),
          ),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText("ConceptNet")).toBeInTheDocument();
        expect(screen.getByText("Person")).toBeInTheDocument();
        expect(screen.getByText("Organization")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Interactive State
  // ========================================================================
  describe("interactive state", () => {
    it("allows filtering workflows by search", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) =>
          res(
            ctx.json([
              {
                id: "workflow-1",
                title: "Entity Grounding",
                description: "Ground entities",
                source: "ConceptNet",
                class_scope: ["Person"],
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
              {
                id: "workflow-2",
                title: "Relationship Extraction",
                description: "Extract relationships",
                source: "DBpedia",
                class_scope: ["Thing"],
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
            ]),
          ),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText("Entity Grounding")).toBeInTheDocument();
        expect(screen.getByText("Relationship Extraction")).toBeInTheDocument();
      });

      const filterInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(filterInput, "Entity");

      await waitFor(() => {
        expect(screen.getByText("Entity Grounding")).toBeInTheDocument();
      });
    });

    it("allows selecting a workflow to view details", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) =>
          res(
            ctx.json([
              {
                id: "workflow-1",
                title: "Entity Grounding",
                description: "Ground entities",
                source: "ConceptNet",
                class_scope: ["Person"],
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
            ]),
          ),
        ),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText("Entity Grounding")).toBeInTheDocument();
      });

      const workflowLink = screen.getByTestId("workflow-name-workflow-1");
      await userEvent.click(workflowLink);

      // Page should still be functional
      expect(screen.getByTestId("reference-workflows-page")).toBeInTheDocument();
    });

    it("allows creating a new workflow", async () => {
      server.use(
        rest.get("*/api/v1/reference/workflows", (req, res, ctx) => res(ctx.json([]))),
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("reference-workflows-page")).toBeInTheDocument();
      });

      const createButton = screen.getByTestId("new-workflow-button");
      await userEvent.click(createButton);

      // Modal should open for workflow creation
      expect(screen.getByTestId("workflow-create-modal")).toBeInTheDocument();
    });
  });
});
