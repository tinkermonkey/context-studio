import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createListRelationships,
  createRelationship,
  createListClasses,
  createClass,
  createListProperties,
  createPropertyDefinition,
  createListTaxonomies,
  createListSchemes,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { RelationshipsPage } from "../relationships";

// The Predicate column renders the property *identifier* wrapped in mono
// arrows: `— {identifier} →`. The three segments are separate text nodes
// inside one span, so we match on the span's combined textContent.
function predicateMatcher(identifier: string) {
  return (_content: string, element: Element | null) =>
    element?.tagName.toLowerCase() === "span" &&
    element.textContent?.replace(/\s+/g, " ").trim() === `— ${identifier} →`;
}

const server = setupServer(
  http.get("*/api/taxonomies", () => HttpResponse.json(createListTaxonomies([]))),
  http.get("*/api/schemes", () => HttpResponse.json(createListSchemes([]))),
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

describe("Relationships Schema Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading skeleton state with 5 skeleton rows matching table layout", async () => {
      server.use(
        http.get("*/api/relationships", async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(createListRelationships([]));
        }),
        http.get("*/api/classes", () => HttpResponse.json(createListClasses([]))),
        http.get("*/api/properties", () => HttpResponse.json(createListProperties([]))),
      );

      const { container } = render(<RelationshipsPage />);

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
        http.get("*/api/relationships", () =>
          HttpResponse.json({ detail: "Internal server error" }, { status: 500 }),
        ),
        http.get("*/api/classes", () => HttpResponse.json(createListClasses([]))),
        http.get("*/api/properties", () => HttpResponse.json(createListProperties([]))),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load relationships/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state copy when no relationships exist", async () => {
      server.use(
        http.get("*/api/relationships", () => HttpResponse.json(createListRelationships([]))),
        http.get("*/api/classes", () => HttpResponse.json(createListClasses([]))),
        http.get("*/api/properties", () => HttpResponse.json(createListProperties([]))),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        expect(screen.getByText("No relationships defined")).toBeInTheDocument();
        expect(
          screen.getByText("Relationships are typed edges between classes."),
        ).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("displays table with relationships when data loads", async () => {
      const mockClasses = createListClasses([
        createClass({ id: "class-1", title: "Person" }),
        createClass({ id: "class-2", title: "Company" }),
      ]);

      const mockProperties = createListProperties([
        createPropertyDefinition({ id: "prop-1", title: "works_for", identifier: "works_for" }),
      ]);

      const mockRelationships = createListRelationships([
        createRelationship({
          id: "rel-1",
          source_id: "class-1",
          target_id: "class-2",
          property_definition_id: "prop-1",
        }),
      ]);

      server.use(
        http.get("*/api/relationships", () => HttpResponse.json(mockRelationships)),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/properties", () => HttpResponse.json(mockProperties)),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        // Page renders without errors.
        expect(screen.getByTestId("relationships-page")).toBeInTheDocument();
      });

      // The Predicate column resolves the property identifier ("— works_for →").
      expect(screen.getByText(predicateMatcher("works_for"))).toBeInTheDocument();
      // Source and target columns resolve the class titles.
      expect(screen.getByText("Person")).toBeInTheDocument();
      expect(screen.getByText("Company")).toBeInTheDocument();
    });

    it("displays mono ID in first column of table rows", async () => {
      const mockClasses = createListClasses([]);
      const mockProperties = createListProperties([]);
      const mockRelationships = createListRelationships([
        createRelationship({
          id: "rel-123",
          source_id: "class-1",
          target_id: "class-2",
          property_definition_id: "prop-1",
        }),
      ]);

      server.use(
        http.get("*/api/relationships", () => HttpResponse.json(mockRelationships)),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/properties", () => HttpResponse.json(mockProperties)),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        // Verify the component loads
        expect(screen.getByTestId("relationships-page")).toBeInTheDocument();
      });

      // The identifier cell renders the id ("rel-123") in a mono-font span,
      // no longer a <code> element.
      const monoId = screen.getByText("rel-123");
      expect(monoId.tagName.toLowerCase()).toBe("span");
      expect(monoId).toHaveStyle({ fontFamily: "var(--font-mono)" });
    });
  });

  // ========================================================================
  // Partial State (One API Failure)
  // ========================================================================
  describe("partial state with one failing dependency", () => {
    it("displays relationships table when classes API fails but relationships and properties succeed", async () => {
      const mockRelationships = createListRelationships([
        createRelationship({
          id: "rel-1",
          source_id: "class-1",
          target_id: "class-2",
          property_definition_id: "prop-1",
        }),
      ]);

      const mockProperties = createListProperties([
        createPropertyDefinition({ id: "prop-1", title: "works_for", identifier: "works_for" }),
      ]);

      server.use(
        http.get("*/api/relationships", () => HttpResponse.json(mockRelationships)),
        http.get("*/api/classes", () =>
          HttpResponse.json({ detail: "Classes API error" }, { status: 500 }),
        ),
        http.get("*/api/properties", () => HttpResponse.json(mockProperties)),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        // Relationships and properties should render — the Predicate column
        // resolves from the (successful) properties query.
        expect(screen.getByText(predicateMatcher("works_for"))).toBeInTheDocument();
        // Missing class names (classes query failed) show as em-dash.
        expect(screen.getAllByText("—").length).toBeGreaterThan(0);
      });
    });
  });

  // ========================================================================
  // Filtered State
  // ========================================================================
  describe("filtered state", () => {
    it("filters relationships by search term", async () => {
      const mockClasses = createListClasses([
        createClass({ id: "class-1", title: "Person" }),
        createClass({ id: "class-2", title: "Company" }),
      ]);

      const mockProperties = createListProperties([
        createPropertyDefinition({ id: "prop-1", title: "works_for", identifier: "works_for" }),
        createPropertyDefinition({ id: "prop-2", title: "manages", identifier: "manages" }),
      ]);

      const mockRelationships = createListRelationships([
        createRelationship({
          id: "rel-1",
          source_id: "class-1",
          target_id: "class-2",
          property_definition_id: "prop-1",
        }),
        createRelationship({
          id: "rel-2",
          source_id: "class-1",
          target_id: "class-2",
          property_definition_id: "prop-2",
        }),
      ]);

      server.use(
        http.get("*/api/relationships", () => HttpResponse.json(mockRelationships)),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/properties", () => HttpResponse.json(mockProperties)),
      );

      render(<RelationshipsPage />);

      // Both predicates render initially (Predicate column shows identifier).
      await waitFor(() => {
        expect(screen.getByText(predicateMatcher("works_for"))).toBeInTheDocument();
        expect(screen.getByText(predicateMatcher("manages"))).toBeInTheDocument();
      });

      // Search filters on property title; "manages" row should be removed.
      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "works_for");

      expect(screen.getByText(predicateMatcher("works_for"))).toBeInTheDocument();
      expect(screen.queryByText(predicateMatcher("manages"))).not.toBeInTheDocument();
    });

    it("shows filtered empty state when filters match no results", async () => {
      const mockClasses = createListClasses([createClass({ id: "class-1", title: "Person" })]);

      const mockProperties = createListProperties([
        createPropertyDefinition({ id: "prop-1", title: "works_for", identifier: "works_for" }),
      ]);

      const mockRelationships = createListRelationships([
        createRelationship({
          id: "rel-1",
          source_id: "class-1",
          target_id: "class-1",
          property_definition_id: "prop-1",
        }),
      ]);

      server.use(
        http.get("*/api/relationships", () => HttpResponse.json(mockRelationships)),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/properties", () => HttpResponse.json(mockProperties)),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        expect(screen.getByText(predicateMatcher("works_for"))).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "nonexistent");

      await waitFor(() => {
        expect(screen.getByText("No matching relationships")).toBeInTheDocument();
        expect(
          screen.getByText("Try adjusting your search or filters to find relationships."),
        ).toBeInTheDocument();
      });
    });
  });
});
