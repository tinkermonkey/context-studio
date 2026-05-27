import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { Dashboard } from "../index";

// Mock the Link component to avoid router issues
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return {
    ...actual,
    Link: ({ children, to }: any) => <a href={to}>{children}</a>,
  };
});

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

describe("Dashboard", () => {
  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state when no taxonomies exist", async () => {
      server.use(
        rest.get("*/api/v1/admin/health", (req, res, ctx) =>
          res(
            ctx.json({
              status: "ok",
              database_connected: true,
              nlp_pipeline_ready: true,
              embedding_model_loaded: true,
              llm_providers_available: ["anthropic"],
              uptime_seconds: 3600,
            }),
          ),
        ),
        rest.get("*/api/taxonomies", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, offset: 0 })),
        ),
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, offset: 0 })),
        ),
        rest.get("*/api/individuals", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, offset: 0 })),
        ),
        rest.get("*/api/v1/pipelines", (req, res, ctx) => res(ctx.json([]))),
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
      );

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText("Welcome to Context Studio")).toBeInTheDocument();
        expect(screen.getByText("Start building your knowledge graph")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Create taxonomy/i })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Run pipeline/i })).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays skeleton loaders while data is fetching", async () => {
      let resolveTaxonomies: () => void;
      const taxonomiesPromise = new Promise<void>((resolve) => {
        resolveTaxonomies = resolve;
      });

      server.use(
        rest.get("*/api/taxonomies", async (req, res, ctx) => {
          await taxonomiesPromise;
          return res(ctx.json({ items: [], total: 0 }));
        }),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json({ items: [], total: 0 }))),
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json({ items: [], total: 0 }))),
        rest.get("*/api/v1/pipelines", (req, res, ctx) => res(ctx.json([]))),
        rest.get("*/api/v1/admin/health", (req, res, ctx) =>
          res(
            ctx.json({
              status: "ok",
              database_connected: true,
              nlp_pipeline_ready: true,
              embedding_model_loaded: true,
              llm_providers_available: ["anthropic"],
              uptime_seconds: 3600,
            }),
          ),
        ),
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
      );

      const { container } = render(<Dashboard />);

      // Verify skeletons are rendered by looking for skeleton-shimmer animation
      const skeletons = container.querySelectorAll('[style*="skeleton-shimmer"]');
      expect(skeletons.length).toBeGreaterThan(0);

      resolveTaxonomies!();
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner when taxonomies fail to load", async () => {
      server.use(
        rest.get("*/api/taxonomies", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Server error" })),
        ),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json({ items: [], total: 0 }))),
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json({ items: [], total: 0 }))),
        rest.get("*/api/v1/pipelines", (req, res, ctx) => res(ctx.json([]))),
        rest.get("*/api/v1/admin/health", (req, res, ctx) =>
          res(
            ctx.json({
              status: "ok",
              database_connected: true,
              nlp_pipeline_ready: true,
              embedding_model_loaded: true,
              llm_providers_available: ["anthropic"],
              uptime_seconds: 3600,
            }),
          ),
        ),
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
      );

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText("Could not load taxonomies")).toBeInTheDocument();
      });
    });

    it("displays multiple error banners when multiple sections fail", async () => {
      server.use(
        rest.get("*/api/taxonomies", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Server error" })),
        ),
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Server error" })),
        ),
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json({ items: [], total: 0 }))),
        rest.get("*/api/v1/pipelines", (req, res, ctx) => res(ctx.json([]))),
        rest.get("*/api/v1/admin/health", (req, res, ctx) =>
          res(
            ctx.json({
              status: "ok",
              database_connected: true,
              nlp_pipeline_ready: true,
              embedding_model_loaded: true,
              llm_providers_available: ["anthropic"],
              uptime_seconds: 3600,
            }),
          ),
        ),
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
      );

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText("Could not load taxonomies")).toBeInTheDocument();
        expect(screen.getByText("Could not load class hierarchy")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("displays stat tiles with loaded data", async () => {
      server.use(
        rest.get("*/api/taxonomies", (req, res, ctx) =>
          res(
            ctx.json({
              items: [{ id: "tax-1", title: "Biology", description: "Life sciences" }],
              total: 1,
              offset: 0,
            }),
          ),
        ),
        rest.get("*/api/classes", (req, res, ctx) =>
          res(
            ctx.json({
              items: [{ id: "class-1", title: "Organism", description: "Living things" }],
              total: 3,
              offset: 0,
            }),
          ),
        ),
        rest.get("*/api/individuals", (req, res, ctx) =>
          res(
            ctx.json({
              items: [{ id: "ind-1", title: "Human", description: "Species" }],
              total: 5,
              offset: 0,
            }),
          ),
        ),
        rest.get("*/api/v1/pipelines", (req, res, ctx) =>
          res(
            ctx.json([
              { id: "pipe-1", title: "Extraction", enabled: true },
              { id: "pipe-2", title: "Enrichment", enabled: false },
            ]),
          ),
        ),
        rest.get("*/api/v1/admin/health", (req, res, ctx) =>
          res(
            ctx.json({
              status: "ok",
              database_connected: true,
              nlp_pipeline_ready: true,
              embedding_model_loaded: true,
              llm_providers_available: ["anthropic"],
              uptime_seconds: 3600,
            }),
          ),
        ),
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) =>
          res(
            ctx.json({
              events: [
                {
                  id: "event-1",
                  operation: "create",
                  entity_type: "taxonomy",
                  entity_id: "tax-1",
                  timestamp: new Date().toISOString(),
                  new_state: { title: "Biology" },
                },
              ],
              total: 1,
            }),
          ),
        ),
      );

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText("Taxonomies")).toBeInTheDocument();
        expect(screen.getByText("1")).toBeInTheDocument();
      });

      expect(screen.getByText("Classes")).toBeInTheDocument();
      expect(screen.getAllByText("3")).toBeTruthy();

      expect(screen.getByText("Individuals")).toBeInTheDocument();
      expect(screen.getAllByText("5")).toBeTruthy();

      expect(screen.getAllByText("Pipelines")).toBeTruthy();
      expect(screen.getAllByText("1")).toBeTruthy();
    });

    it("displays activity section header when populated", async () => {
      server.use(
        rest.get("*/api/taxonomies", (req, res, ctx) =>
          res(
            ctx.json({
              items: [{ id: "tax-1", title: "Biology" }],
              total: 1,
              offset: 0,
            }),
          ),
        ),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json({ items: [], total: 0 }))),
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json({ items: [], total: 0 }))),
        rest.get("*/api/v1/pipelines", (req, res, ctx) => res(ctx.json([]))),
        rest.get("*/api/v1/admin/health", (req, res, ctx) =>
          res(
            ctx.json({
              status: "ok",
              database_connected: true,
              nlp_pipeline_ready: true,
              embedding_model_loaded: true,
              llm_providers_available: ["anthropic"],
              uptime_seconds: 3600,
            }),
          ),
        ),
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) =>
          res(
            ctx.json({
              events: [],
              total: 0,
            }),
          ),
        ),
      );

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText("Recent activity")).toBeInTheDocument();
        expect(screen.getByText("No recent changes.")).toBeInTheDocument();
      });
    });

    it("displays active pipelines and quick access sections when populated", async () => {
      server.use(
        rest.get("*/api/taxonomies", (req, res, ctx) =>
          res(
            ctx.json({
              items: [{ id: "tax-1", title: "Biology" }],
              total: 1,
              offset: 0,
            }),
          ),
        ),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json({ items: [], total: 0 }))),
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json({ items: [], total: 0 }))),
        rest.get("*/api/v1/pipelines", (req, res, ctx) => res(ctx.json([]))),
        rest.get("*/api/v1/admin/health", (req, res, ctx) =>
          res(
            ctx.json({
              status: "ok",
              database_connected: true,
              nlp_pipeline_ready: true,
              embedding_model_loaded: true,
              llm_providers_available: ["anthropic"],
              uptime_seconds: 3600,
            }),
          ),
        ),
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
      );

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText("Active pipelines")).toBeInTheDocument();
        expect(screen.getByText("Quick access")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Partial State
  // ========================================================================
  describe("partial state", () => {
    it("displays available data while some sections error", async () => {
      server.use(
        rest.get("*/api/taxonomies", (req, res, ctx) =>
          res(
            ctx.json({
              items: [{ id: "tax-1", title: "Biology" }],
              total: 1,
              offset: 0,
            }),
          ),
        ),
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Error" })),
        ),
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json({ items: [], total: 0 }))),
        rest.get("*/api/v1/pipelines", (req, res, ctx) => res(ctx.json([]))),
        rest.get("*/api/v1/admin/health", (req, res, ctx) =>
          res(
            ctx.json({
              status: "ok",
              database_connected: true,
              nlp_pipeline_ready: true,
              embedding_model_loaded: true,
              llm_providers_available: ["anthropic"],
              uptime_seconds: 3600,
            }),
          ),
        ),
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) =>
          res(ctx.json({ events: [], total: 0 })),
        ),
      );

      render(<Dashboard />);

      await waitFor(() => {
        // Should show taxonomy data
        expect(screen.getByText("Taxonomies")).toBeInTheDocument();
        expect(screen.getByText("1")).toBeInTheDocument();

        // Should show classes error
        expect(screen.getByText("Could not load class hierarchy")).toBeInTheDocument();
      });
    });
  });
});
