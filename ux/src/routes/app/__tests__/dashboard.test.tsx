import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { Dashboard } from "../index";

const HEALTH = {
  status: "ok",
  database_connected: true,
  nlp_pipeline_ready: true,
  embedding_model_loaded: true,
  llm_providers_available: ["anthropic"],
  uptime_seconds: 3600,
};

/**
 * Register handlers for every endpoint the Dashboard fetches. The test server
 * runs with onUnhandledRequest:"error", so each request must be mocked. The
 * Dashboard hooks call: taxonomies, schemes, classes, individuals, admin health,
 * admin stats trends, and versioning changes.
 */
function baseHandlers(overrides: ReturnType<typeof http.get>[] = []) {
  // MSW v2 resolves with the FIRST matching handler, so overrides must precede
  // the defaults to take effect.
  return [
    ...overrides,
    http.get("*/api/v1/admin/health", () => HttpResponse.json(HEALTH)),
    http.get("*/api/v1/admin/stats/trends", () =>
      HttpResponse.json({ taxonomies: [], schemes: [], classes: [], individuals: [] }),
    ),
    http.get("*/api/taxonomies", () => HttpResponse.json({ items: [], total: 0, offset: 0 })),
    http.get("*/api/schemes", () => HttpResponse.json({ items: [], total: 0, offset: 0 })),
    http.get("*/api/classes", () => HttpResponse.json({ items: [], total: 0, offset: 0 })),
    http.get("*/api/individuals", () => HttpResponse.json({ items: [], total: 0, offset: 0 })),
    http.get("*/api/v1/versioning/changes", () => HttpResponse.json({ events: [], total: 0 })),
  ];
}

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
      server.use(...baseHandlers());

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText("Welcome to Context Studio")).toBeInTheDocument();
        expect(screen.getByText("Start building your knowledge graph")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Create taxonomy/i })).toBeInTheDocument();
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
      let resolveChanges: () => void;
      const changesPromise = new Promise<void>((resolve) => {
        resolveChanges = resolve;
      });

      // Hold taxonomies pending so the dashboard renders its main view (not the
      // empty state), and hold the changes request pending so the Recent
      // activity panel renders its skeleton placeholders (4 of them).
      server.use(
        ...baseHandlers([
          http.get("*/api/taxonomies", async () => {
            await taxonomiesPromise;
            return HttpResponse.json({ items: [{ id: "t-1", title: "Bio" }], total: 1, offset: 0 });
          }),
          http.get("*/api/v1/versioning/changes", async () => {
            await changesPromise;
            return HttpResponse.json({ events: [], total: 0 });
          }),
        ]),
      );

      const { container } = render(<Dashboard />);

      // Skeletons render as <div className="skeleton"> (CSS-driven shimmer).
      // The Recent activity panel renders 4 while changes are loading.
      await waitFor(() => {
        const skeletons = container.querySelectorAll(".skeleton");
        expect(skeletons.length).toBeGreaterThanOrEqual(4);
      });

      resolveTaxonomies!();
      resolveChanges!();
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner when taxonomies fail to load", async () => {
      server.use(
        ...baseHandlers([
          http.get("*/api/taxonomies", () =>
            HttpResponse.json({ detail: "Server error" }, { status: 500 }),
          ),
        ]),
      );

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText("Could not load taxonomies")).toBeInTheDocument();
      });
    });

    it("displays multiple error banners when multiple sections fail", async () => {
      server.use(
        ...baseHandlers([
          http.get("*/api/taxonomies", () =>
            HttpResponse.json({ detail: "Server error" }, { status: 500 }),
          ),
          http.get("*/api/classes", () =>
            HttpResponse.json({ detail: "Server error" }, { status: 500 }),
          ),
        ]),
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
        ...baseHandlers([
          http.get("*/api/taxonomies", () =>
            HttpResponse.json({
              items: [{ id: "tax-1", title: "Biology", description: "Life sciences" }],
              total: 1,
              offset: 0,
            }),
          ),
          http.get("*/api/classes", () =>
            HttpResponse.json({
              items: [{ id: "class-1", title: "Organism", description: "Living things" }],
              total: 3,
              offset: 0,
            }),
          ),
          http.get("*/api/individuals", () =>
            HttpResponse.json({
              items: [{ id: "ind-1", title: "Human", description: "Species" }],
              total: 5,
              offset: 0,
            }),
          ),
        ]),
      );

      const { container } = render(<Dashboard />);

      // "Taxonomies" appears in the stat grid, the Quick Access grid, and the
      // hierarchy panel. Scope assertions to the stat grid (.stat-grid) so each
      // label/value pair is unambiguous.
      await waitFor(() => {
        expect(container.querySelector(".stat-grid")).toBeInTheDocument();
      });
      const statGrid = within(container.querySelector(".stat-grid") as HTMLElement);

      await waitFor(() => {
        expect(statGrid.getByText("Taxonomies")).toBeInTheDocument();
        expect(statGrid.getByText("1")).toBeInTheDocument();
      });

      expect(statGrid.getByText("Classes")).toBeInTheDocument();
      expect(statGrid.getByText("3")).toBeInTheDocument();

      expect(statGrid.getByText("Individuals")).toBeInTheDocument();
      expect(statGrid.getByText("5")).toBeInTheDocument();
    });

    it("displays activity section header when populated", async () => {
      server.use(
        ...baseHandlers([
          http.get("*/api/taxonomies", () =>
            HttpResponse.json({
              items: [{ id: "tax-1", title: "Biology" }],
              total: 1,
              offset: 0,
            }),
          ),
        ]),
      );

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText("Recent activity")).toBeInTheDocument();
        expect(screen.getByText("No recent changes.")).toBeInTheDocument();
      });
    });

    it("displays quick access section when populated", async () => {
      server.use(
        ...baseHandlers([
          http.get("*/api/taxonomies", () =>
            HttpResponse.json({
              items: [{ id: "tax-1", title: "Biology" }],
              total: 1,
              offset: 0,
            }),
          ),
        ]),
      );

      render(<Dashboard />);

      await waitFor(() => {
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
        ...baseHandlers([
          http.get("*/api/taxonomies", () =>
            HttpResponse.json({
              items: [{ id: "tax-1", title: "Biology" }],
              total: 1,
              offset: 0,
            }),
          ),
          http.get("*/api/classes", () =>
            HttpResponse.json({ detail: "Error" }, { status: 500 }),
          ),
        ]),
      );

      const { container } = render(<Dashboard />);

      await waitFor(() => {
        // Should show classes error
        expect(screen.getByText("Could not load class hierarchy")).toBeInTheDocument();
      });

      // Should still show the taxonomy stat tile (count 1) despite the class
      // hierarchy error. Scope to the stat grid since "Taxonomies" also appears
      // in the Quick Access grid.
      const statGrid = within(container.querySelector(".stat-grid") as HTMLElement);
      expect(statGrid.getByText("Taxonomies")).toBeInTheDocument();
      expect(statGrid.getByText("1")).toBeInTheDocument();
    });
  });
});
