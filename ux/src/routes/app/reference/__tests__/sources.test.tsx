import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { createReferenceStatusResponse } from "@/api/services/__tests__/fixtures/reference.fixtures";
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

      const { container } = render(<SourcesPage />);

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

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load reference sources/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state UI when no sources exist", async () => {
      server.use(
        rest.get("*/api/reference/status", (req, res, ctx) =>
          res(ctx.json(createReferenceStatusResponse({ sources: [] }))),
        ),
      );

      render(<SourcesPage />);

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
    it("renders table with source rows when data loads", async () => {
      const mockResponse = createReferenceStatusResponse({
        sources: [
          {
            name: "wikipedia",
            available: true,
            last_checked: new Date().toISOString(),
          },
          {
            name: "dbpedia",
            available: true,
            last_checked: new Date().toISOString(),
          },
        ],
      });

      server.use(
        rest.get("*/api/reference/status", (req, res, ctx) => res(ctx.json(mockResponse))),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByText("wikipedia")).toBeInTheDocument();
        expect(screen.getByText("dbpedia")).toBeInTheDocument();
      });
    });

    it("asserts schema-page-layout is present when sources are rendered", async () => {
      const mockResponse = createReferenceStatusResponse({
        sources: [
          {
            name: "wikipedia",
            available: true,
            last_checked: new Date().toISOString(),
          },
        ],
      });

      server.use(
        rest.get("*/api/reference/status", (req, res, ctx) => res(ctx.json(mockResponse))),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByTestId("schema-page-layout")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Search/Filter State
  // ========================================================================
  describe("search and filtering", () => {
    it("filters sources by search term", async () => {
      const mockResponse = createReferenceStatusResponse({
        sources: [
          {
            name: "wikipedia",
            available: true,
            last_checked: new Date().toISOString(),
          },
          {
            name: "dbpedia",
            available: true,
            last_checked: new Date().toISOString(),
          },
        ],
      });

      server.use(
        rest.get("*/api/reference/status", (req, res, ctx) => res(ctx.json(mockResponse))),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByText("wikipedia")).toBeInTheDocument();
      });

      const searchInput = screen.getByTestId("schema-search-input");
      await userEvent.type(searchInput, "wiki");

      await waitFor(() => {
        expect(screen.getByText("wikipedia")).toBeInTheDocument();
        expect(screen.queryByText("dbpedia")).not.toBeInTheDocument();
      });
    });

    it("clears filter when search is removed", async () => {
      const mockResponse = createReferenceStatusResponse({
        sources: [
          {
            name: "wikipedia",
            available: true,
            last_checked: new Date().toISOString(),
          },
          {
            name: "dbpedia",
            available: true,
            last_checked: new Date().toISOString(),
          },
        ],
      });

      server.use(
        rest.get("*/api/reference/status", (req, res, ctx) => res(ctx.json(mockResponse))),
      );

      render(<SourcesPage />);

      await waitFor(() => {
        expect(screen.getByText("wikipedia")).toBeInTheDocument();
      });

      const searchInput = screen.getByTestId("schema-search-input") as HTMLInputElement;
      await userEvent.type(searchInput, "wiki");

      await waitFor(() => {
        expect(screen.queryByText("dbpedia")).not.toBeInTheDocument();
      });

      await userEvent.clear(searchInput);

      await waitFor(() => {
        expect(screen.getByText("dbpedia")).toBeInTheDocument();
      });
    });
  });
});
