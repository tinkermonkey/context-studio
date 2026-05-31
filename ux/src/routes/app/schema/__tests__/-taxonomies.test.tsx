import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createListTaxonomies,
  createTaxonomy,
  createListSchemes,
  createListClasses,
  createListProperties,
  createListRelationships,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { TaxonomiesPage } from "../taxonomies";

const server = setupServer(
  http.get("*/api/schemes", () => HttpResponse.json(createListSchemes([]))),
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

describe("Taxonomies Schema Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading skeleton state with 5 skeleton rows matching table layout", async () => {
      server.use(
        http.get("*/api/taxonomies", async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(createListTaxonomies([]));
        }),
      );

      const { container } = render(<TaxonomiesPage />);

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
        http.get("*/api/taxonomies", () =>
          HttpResponse.json({ detail: "Internal server error" }, { status: 500 }),
        ),
      );

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load taxonomies/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state copy when no taxonomies exist", async () => {
      server.use(http.get("*/api/taxonomies", () => HttpResponse.json(createListTaxonomies([]))));

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText("No taxonomies yet")).toBeInTheDocument();
        expect(
          screen.getByText(
            "A taxonomy groups related classes. Most workspaces start with one or two.",
          ),
        ).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("displays table with taxonomies when data loads", async () => {
      const mockTaxonomies = createListTaxonomies([
        createTaxonomy({
          id: "tax-1",
          title: "Biology",
          description: "Biological concepts",
        }),
        createTaxonomy({
          id: "tax-2",
          title: "Chemistry",
          description: "Chemical concepts",
        }),
      ]);

      server.use(http.get("*/api/taxonomies", () => HttpResponse.json(mockTaxonomies)));

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText("Biology")).toBeInTheDocument();
        expect(screen.getByText("Chemistry")).toBeInTheDocument();
      });
    });

    it("displays mono ID in first column of table rows", async () => {
      const mockTaxonomies = createListTaxonomies([
        createTaxonomy({
          id: "tax-123",
          identifier: "tax_123",
          title: "TestTax",
        }),
      ]);

      server.use(http.get("*/api/taxonomies", () => HttpResponse.json(mockTaxonomies)));

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestTax")).toBeInTheDocument();
      });

      // The identifier cell renders the identifier in a mono-font span,
      // no longer a <code> element.
      const monoId = screen.getByText("tax_123");
      expect(monoId.tagName.toLowerCase()).toBe("span");
      expect(monoId).toHaveClass("taxonomy-id-cell__text");
    });

    it("displays description column with em-dash placeholder when empty", async () => {
      const mockTaxonomies = createListTaxonomies([
        createTaxonomy({
          id: "tax-1",
          title: "TestTax",
          description: null,
        }),
      ]);

      server.use(http.get("*/api/taxonomies", () => HttpResponse.json(mockTaxonomies)));

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestTax")).toBeInTheDocument();
      });

      const cells = screen.getAllByText("—");
      expect(cells.length).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // Filtered State
  // ========================================================================
  describe("filtered state", () => {
    it("filters taxonomies by search term", async () => {
      const mockTaxonomies = createListTaxonomies([
        createTaxonomy({
          id: "tax-1",
          title: "Biology",
        }),
        createTaxonomy({
          id: "tax-2",
          title: "Chemistry",
        }),
        createTaxonomy({
          id: "tax-3",
          title: "Physics",
        }),
      ]);

      server.use(http.get("*/api/taxonomies", () => HttpResponse.json(mockTaxonomies)));

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText("Biology")).toBeInTheDocument();
        expect(screen.getByText("Chemistry")).toBeInTheDocument();
        expect(screen.getByText("Physics")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "Biology");

      expect(screen.getByText("Biology")).toBeInTheDocument();
      expect(screen.queryByText("Chemistry")).not.toBeInTheDocument();
      expect(screen.queryByText("Physics")).not.toBeInTheDocument();
    });

    it("clears filter when search term is removed", async () => {
      const mockTaxonomies = createListTaxonomies([
        createTaxonomy({
          id: "tax-1",
          title: "Biology",
        }),
        createTaxonomy({
          id: "tax-2",
          title: "Chemistry",
        }),
      ]);

      server.use(http.get("*/api/taxonomies", () => HttpResponse.json(mockTaxonomies)));

      render(<TaxonomiesPage />);

      await waitFor(() => {
        expect(screen.getByText("Biology")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await userEvent.type(searchInput, "Biology");

      expect(screen.queryByText("Chemistry")).not.toBeInTheDocument();

      await userEvent.clear(searchInput);

      expect(screen.getByText("Biology")).toBeInTheDocument();
      expect(screen.getByText("Chemistry")).toBeInTheDocument();
    });
  });
});
