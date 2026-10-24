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
import { serverSideList, pageRequests } from "@/test/serverSideList";
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
        expect(screen.getByText(predicateMatcher("works_for"))).toBeInTheDocument();
      });

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

      // The identifier cell renders the id ("rel-123") in a mono-font span.
      const monoId = await waitFor(() => screen.getByText("rel-123"));
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
    const classes = [
      createClass({ id: "class-1", title: "Person" }),
      createClass({ id: "class-2", title: "Company" }),
    ];
    const properties = [
      createPropertyDefinition({ id: "prop-1", title: "works_for", identifier: "works_for" }),
      createPropertyDefinition({ id: "prop-2", title: "manages", identifier: "manages" }),
    ];
    const names = new Map(
      [...classes, ...properties].map((e) => [e.id, `${e.title} ${e.identifier ?? ""}`]),
    );
    const relationships = [
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
    ];
    // Like the backend: q matches the source title, target title or predicate.
    const relationshipText = (rel: (typeof relationships)[number]) =>
      [rel.source_id, rel.target_id, rel.property_definition_id]
        .map((id) => names.get(id) ?? "")
        .join(" ");

    it("sends the search text to the server as q and shows only the matches", async () => {
      const requests: URLSearchParams[] = [];
      server.use(
        serverSideList("/api/relationships", relationships, requests, {
          matchText: relationshipText,
        }),
        serverSideList("/api/classes", classes),
        serverSideList("/api/properties", properties),
      );

      render(<RelationshipsPage />);

      // Both predicates render initially (Predicate column shows identifier).
      await waitFor(() => {
        expect(screen.getByText(predicateMatcher("works_for"))).toBeInTheDocument();
        expect(screen.getByText(predicateMatcher("manages"))).toBeInTheDocument();
      });

      await userEvent.type(screen.getByPlaceholderText(/search/i), "works_for");

      await waitFor(() => {
        expect(screen.queryByText(predicateMatcher("manages"))).not.toBeInTheDocument();
      });
      expect(screen.getByText(predicateMatcher("works_for"))).toBeInTheDocument();
      expect(pageRequests(requests).at(-1)!.get("q")).toBe("works_for");
    });

    it("shows filtered empty state when filters match no results", async () => {
      server.use(
        serverSideList("/api/relationships", relationships, [], { matchText: relationshipText }),
        serverSideList("/api/classes", classes),
        serverSideList("/api/properties", properties),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        expect(screen.getByText(predicateMatcher("works_for"))).toBeInTheDocument();
      });

      await userEvent.type(screen.getByPlaceholderText(/search/i), "nonexistent");

      await waitFor(() => {
        expect(screen.getByText("No matching relationships")).toBeInTheDocument();
        expect(
          screen.getByText("Try adjusting your search or filters to find relationships."),
        ).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Server-side paging, title lookups and counts
  // ========================================================================
  describe("server-side paging", () => {
    it("requests one page, resolves names by id, and reads tab counts from limit=1 totals", async () => {
      const relationshipRequests: URLSearchParams[] = [];
      const classRequests: URLSearchParams[] = [];
      const propertyRequests: URLSearchParams[] = [];
      const relationships = {
        ...createListRelationships([
          createRelationship({
            id: "rel-1",
            source_id: "class-1",
            target_id: "class-2",
            property_definition_id: "prop-1",
          }),
        ]),
        total: 595,
      };

      server.use(
        http.get("*/api/relationships", ({ request }) => {
          relationshipRequests.push(new URL(request.url).searchParams);
          return HttpResponse.json(relationships);
        }),
        serverSideList(
          "/api/classes",
          [
            createClass({ id: "class-1", title: "Person" }),
            createClass({ id: "class-2", title: "Company" }),
          ],
          classRequests,
        ),
        serverSideList(
          "/api/properties",
          [createPropertyDefinition({ id: "prop-1", identifier: "works_for" })],
          propertyRequests,
        ),
      );

      render(<RelationshipsPage />);

      // The relationships tab count is the backend total, not the loaded row count.
      await waitFor(() => {
        expect(screen.getByRole("tab", { name: "Relationships" })).toHaveAttribute(
          "data-count",
          "595",
        );
      });
      await waitFor(() => {
        expect(screen.getByText("Company")).toBeInTheDocument();
      });
      expect(screen.getByText(predicateMatcher("works_for"))).toBeInTheDocument();

      const page = pageRequests(relationshipRequests)[0];
      expect(page.get("limit")).toBe("50");
      expect(page.get("offset")).toBe("0");
      expect(page.get("sort_by")).toBe("created_at");
      expect(page.get("sort_order")).toBe("desc");
      expect(relationshipRequests.some((r) => r.get("limit") === "1")).toBe(true);
      // Names resolve with ids lookups for this page's rows; counts use limit=1.
      expect(classRequests.find((r) => r.getAll("ids").length)!.getAll("ids")).toEqual([
        "class-1",
        "class-2",
      ]);
      expect(propertyRequests.find((r) => r.getAll("ids").length)!.getAll("ids")).toEqual([
        "prop-1",
      ]);
      expect(
        [...classRequests, ...propertyRequests].every(
          (r) => r.getAll("ids").length > 0 || r.get("limit") === "1",
        ),
      ).toBe(true);
      expect(screen.getByTestId("list-pager-range")).toHaveTextContent("1–50 of 595");
    });
  });
});
