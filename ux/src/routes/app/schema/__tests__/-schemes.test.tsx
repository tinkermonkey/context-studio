import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createListSchemes,
  createConceptScheme,
  createListTaxonomies,
  createListClasses,
  createListProperties,
  createListRelationships,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { SchemesIndexPage } from "../schemes.index";

const server = setupServer(
  http.get("*/api/taxonomies", () => HttpResponse.json(createListTaxonomies([]))),
  http.get("*/api/classes", () => HttpResponse.json(createListClasses([]))),
  http.get("*/api/properties", () => HttpResponse.json(createListProperties([]))),
  http.get("*/api/relationships", () => HttpResponse.json(createListRelationships([]))),
);

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
    it("displays loading skeleton state with 5 skeleton rows matching table layout", async () => {
      server.use(
        http.get("*/api/schemes", async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(createListSchemes([]));
        }),
      );

      const { container } = render(<SchemesIndexPage />);

      // Wait a bit for the component to render
      await new Promise((resolve) => setTimeout(resolve, 50));

      // Verify skeleton rows are rendered before data arrives.
      // Skeletons now use the `.skeleton` class (shimmer is in CSS, not inline style).
      const skeletonElements = container.querySelectorAll(".skeleton");
      expect(skeletonElements.length).toBeGreaterThanOrEqual(5);
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner with retry button when API fails", async () => {
      server.use(
        http.get("*/api/schemes", () =>
          HttpResponse.json({ detail: "Internal server error" }, { status: 500 }),
        ),
      );

      render(<SchemesIndexPage />);

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
      server.use(http.get("*/api/schemes", () => HttpResponse.json(createListSchemes([]))));

      render(<SchemesIndexPage />);

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

      server.use(http.get("*/api/schemes", () => HttpResponse.json(mockSchemes)));

      render(<SchemesIndexPage />);

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

      server.use(http.get("*/api/schemes", () => HttpResponse.json(mockSchemes)));

      render(<SchemesIndexPage />);

      await waitFor(() => {
        expect(screen.getByText("TestScheme")).toBeInTheDocument();
      });

      // The identifier cell renders the id truncated to 8 chars ("scheme-1")
      // in a mono-font span, no longer a <code> element.
      const monoId = screen.getByText("scheme-1");
      expect(monoId.tagName.toLowerCase()).toBe("span");
      expect(monoId).toHaveStyle({ fontFamily: "var(--font-mono)" });
    });

    it("displays description column with em-dash placeholder when empty", async () => {
      const mockSchemes = createListSchemes([
        createConceptScheme({
          id: "scheme-1",
          title: "TestScheme",
          description: null,
        }),
      ]);

      server.use(http.get("*/api/schemes", () => HttpResponse.json(mockSchemes)));

      render(<SchemesIndexPage />);

      await waitFor(() => {
        expect(screen.getByText("TestScheme")).toBeInTheDocument();
      });

      const cells = screen.getAllByText("—");
      expect(cells.length).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // Filtered State
  // ========================================================================
  describe("filtered state", () => {
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

      server.use(http.get("*/api/schemes", () => HttpResponse.json(mockSchemes)));

      render(<SchemesIndexPage />);

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

      server.use(http.get("*/api/schemes", () => HttpResponse.json(mockSchemes)));

      render(<SchemesIndexPage />);

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
