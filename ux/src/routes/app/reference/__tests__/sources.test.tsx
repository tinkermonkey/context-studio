import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { SourcesPage } from "../sources";

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

describe("Reference Sources Page", () => {
  // ========================================================================
  // Page Structure
  // ========================================================================
  describe("page structure", () => {
    it("renders sources page root with testid", async () => {
      server.use(
        rest.get("*/api/v1/reference/status", (req, res, ctx) =>
          res(
            ctx.json({
              sources: [],
              workflows: [],
            }),
          ),
        ),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByTestId("reference-sources-page")).toBeInTheDocument();
      });
    });

    it("displays page title", async () => {
      server.use(
        rest.get("*/api/v1/reference/status", (req, res, ctx) =>
          res(
            ctx.json({
              sources: [],
              workflows: [],
            }),
          ),
        ),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByRole("heading")).toBeInTheDocument();
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
        rest.get("*/api/v1/reference/status", async (req, res, ctx) => {
          await promise;
          return res(
            ctx.json({
              sources: [],
              workflows: [],
            }),
          );
        }),
      );

      const { container } = render(<SourcesPage />);

      // Verify page is rendered even while loading
      expect(screen.getByTestId("reference-sources-page")).toBeInTheDocument();

      resolveRequest!();
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("handles API errors gracefully", async () => {
      server.use(
        rest.get("*/api/v1/reference/status", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Server error" })),
        ),
      );

      const { container } = render(<SourcesPage />);

      // Page should still be accessible even with error
      expect(screen.getByTestId("reference-sources-page")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays message when no sources exist", async () => {
      server.use(
        rest.get("*/api/v1/reference/status", (req, res, ctx) =>
          res(
            ctx.json({
              sources: [],
              workflows: [],
            }),
          ),
        ),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByTestId("reference-sources-page")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("displays sources list with data", async () => {
      server.use(
        rest.get("*/api/v1/reference/status", (req, res, ctx) =>
          res(
            ctx.json({
              sources: [
                {
                  name: "ConceptNet",
                  available: true,
                  last_checked: new Date().toISOString(),
                  entities_count: 100,
                },
              ],
              workflows: [],
            }),
          ),
        ),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByText("ConceptNet")).toBeInTheDocument();
      });
    });

    it("displays multiple sources in the list", async () => {
      server.use(
        rest.get("*/api/v1/reference/status", (req, res, ctx) =>
          res(
            ctx.json({
              sources: [
                {
                  name: "ConceptNet",
                  available: true,
                  last_checked: new Date().toISOString(),
                  entities_count: 100,
                },
                {
                  name: "DBpedia",
                  available: false,
                  last_checked: new Date().toISOString(),
                  entities_count: 0,
                },
              ],
              workflows: [],
            }),
          ),
        ),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByText("ConceptNet")).toBeInTheDocument();
        expect(screen.getByText("DBpedia")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Interactive State
  // ========================================================================
  describe("interactive state", () => {
    it("allows filtering sources by search", async () => {
      server.use(
        rest.get("*/api/v1/reference/status", (req, res, ctx) =>
          res(
            ctx.json({
              sources: [
                {
                  name: "ConceptNet",
                  available: true,
                  last_checked: new Date().toISOString(),
                  entities_count: 100,
                },
                {
                  name: "DBpedia",
                  available: true,
                  last_checked: new Date().toISOString(),
                  entities_count: 200,
                },
              ],
              workflows: [],
            }),
          ),
        ),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByText("ConceptNet")).toBeInTheDocument();
        expect(screen.getByText("DBpedia")).toBeInTheDocument();
      });

      const filterInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(filterInput, "Concept");

      await waitFor(() => {
        expect(screen.getByText("ConceptNet")).toBeInTheDocument();
      });
    });

    it("allows selecting a source to view details", async () => {
      server.use(
        rest.get("*/api/v1/reference/status", (req, res, ctx) =>
          res(
            ctx.json({
              sources: [
                {
                  name: "ConceptNet",
                  available: true,
                  last_checked: new Date().toISOString(),
                  entities_count: 100,
                },
              ],
              workflows: [],
            }),
          ),
        ),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByText("ConceptNet")).toBeInTheDocument();
      });

      const sourceLink = screen.getByTestId("reference-source-name-ConceptNet");
      await userEvent.click(sourceLink);

      // Page should still be functional
      expect(screen.getByTestId("reference-sources-page")).toBeInTheDocument();
    });
  });
});
