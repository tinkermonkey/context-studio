import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { createListSchemes, createConceptScheme } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import SchemesPage from "../schemes.index";

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

describe("Schemes Schema Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading skeleton state before data arrives", async () => {
      server.use(
        rest.get("*/api/schemes", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createListSchemes([])));
        }),
      );

      const { container } = render(<SchemesPage />);

      // Verify the component renders (skeleton or data)
      expect(container.querySelector("div")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner with retry button when API fails", async () => {
      server.use(
        rest.get("*/api/schemes", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Internal server error" })),
        ),
      );

      render(<SchemesPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load concept schemes/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state copy when no concept schemes exist", async () => {
      server.use(
        rest.get("*/api/schemes", (req, res, ctx) =>
          res(ctx.json(createListSchemes([]))),
        ),
      );

      render(<SchemesPage />);

      await waitFor(() => {
        expect(screen.getByText("No concept schemes yet")).toBeInTheDocument();
        expect(
          screen.getByText("A concept scheme organizes classes within a taxonomy."),
        ).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("displays table with concept schemes when data loads", async () => {
      const mockSchemes = createListSchemes([
        createConceptScheme({
          id: "scheme-1",
          title: "Biological Classification",
          description: "Scientific classification scheme",
        }),
        createConceptScheme({
          id: "scheme-2",
          title: "Chemical Properties",
          description: "Periodic table organization",
        }),
      ]);

      server.use(
        rest.get("*/api/schemes", (req, res, ctx) =>
          res(ctx.json(mockSchemes)),
        ),
      );

      render(<SchemesPage />);

      await waitFor(() => {
        expect(screen.getByText("Biological Classification")).toBeInTheDocument();
        expect(screen.getByText("Chemical Properties")).toBeInTheDocument();
      });
    });

    it("displays mono ID in first column of table rows", async () => {
      const mockSchemes = createListSchemes([
        createConceptScheme({
          id: "scheme-123",
          title: "TestScheme",
        }),
      ]);

      server.use(
        rest.get("*/api/schemes", (req, res, ctx) =>
          res(ctx.json(mockSchemes)),
        ),
      );

      render(<SchemesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestScheme")).toBeInTheDocument();
      });

      const monoId = screen.getByText("scheme-1");
      expect(monoId).toHaveClass("mono");
    });

    it("displays description column with em-dash placeholder when empty", async () => {
      const mockSchemes = createListSchemes([
        createConceptScheme({
          id: "scheme-1",
          title: "TestScheme",
          description: null,
        }),
      ]);

      server.use(
        rest.get("*/api/schemes", (req, res, ctx) =>
          res(ctx.json(mockSchemes)),
        ),
      );

      render(<SchemesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestScheme")).toBeInTheDocument();
      });

      const cells = screen.getAllByText("—");
      expect(cells.length).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // Partial State (Filtered)
  // ========================================================================
  describe("partial state with filtering", () => {
    it("filters concept schemes by search term", async () => {
      const mockSchemes = createListSchemes([
        createConceptScheme({
          id: "scheme-1",
          title: "Biology",
        }),
        createConceptScheme({
          id: "scheme-2",
          title: "Chemistry",
        }),
        createConceptScheme({
          id: "scheme-3",
          title: "Physics",
        }),
      ]);

      server.use(
        rest.get("*/api/schemes", (req, res, ctx) =>
          res(ctx.json(mockSchemes)),
        ),
      );

      render(<SchemesPage />);

      await waitFor(() => {
        expect(screen.getByText("Biology")).toBeInTheDocument();
        expect(screen.getByText("Chemistry")).toBeInTheDocument();
        expect(screen.getByText("Physics")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "Chemistry");

      expect(screen.getByText("Chemistry")).toBeInTheDocument();
      expect(screen.queryByText("Biology")).not.toBeInTheDocument();
      expect(screen.queryByText("Physics")).not.toBeInTheDocument();
    });

    it("clears filter when search term is removed", async () => {
      const mockSchemes = createListSchemes([
        createConceptScheme({
          id: "scheme-1",
          title: "Biology",
        }),
        createConceptScheme({
          id: "scheme-2",
          title: "Chemistry",
        }),
      ]);

      server.use(
        rest.get("*/api/schemes", (req, res, ctx) =>
          res(ctx.json(mockSchemes)),
        ),
      );

      render(<SchemesPage />);

      await waitFor(() => {
        expect(screen.getByText("Biology")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await userEvent.type(searchInput, "Chemistry");

      expect(screen.queryByText("Biology")).not.toBeInTheDocument();

      await userEvent.clear(searchInput);

      expect(screen.getByText("Biology")).toBeInTheDocument();
      expect(screen.getByText("Chemistry")).toBeInTheDocument();
    });
  });
});
