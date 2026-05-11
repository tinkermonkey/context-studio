import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createListRelationships,
  createRelationship,
  createListClasses,
  createClass,
  createListProperties,
  createPropertyDefinition,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { RelationshipsPage } from "../relationships";

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

describe("Relationships Schema Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading skeleton state with 5 skeleton rows matching table layout", async () => {
      server.use(
        rest.get("*/api/relationships", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createListRelationships([])));
        }),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(createListClasses([])))),
        rest.get("*/api/properties", (req, res, ctx) => res(ctx.json(createListProperties([])))),
      );

      const { container } = render(<RelationshipsPage />);

      // Verify skeleton rows are rendered before data arrives
      const skeletonElements = container.querySelectorAll(
        "div[style*='animation: skeleton-shimmer']",
      );
      expect(skeletonElements.length).toBeGreaterThanOrEqual(5);
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner with retry button when API fails", async () => {
      server.use(
        rest.get("*/api/relationships", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Internal server error" })),
        ),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(createListClasses([])))),
        rest.get("*/api/properties", (req, res, ctx) => res(ctx.json(createListProperties([])))),
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
        rest.get("*/api/relationships", (req, res, ctx) =>
          res(ctx.json(createListRelationships([]))),
        ),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(createListClasses([])))),
        rest.get("*/api/properties", (req, res, ctx) => res(ctx.json(createListProperties([])))),
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
        createPropertyDefinition({ id: "prop-1", title: "works_for" }),
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
        rest.get("*/api/relationships", (req, res, ctx) => res(ctx.json(mockRelationships))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/properties", (req, res, ctx) => res(ctx.json(mockProperties))),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        // Check for the relationship data in the table
        expect(screen.getByText("works_for")).toBeInTheDocument();
        // Check that the page renders without errors
        expect(screen.getByTestId("relationships-page")).toBeInTheDocument();
      });
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
        rest.get("*/api/relationships", (req, res, ctx) => res(ctx.json(mockRelationships))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/properties", (req, res, ctx) => res(ctx.json(mockProperties))),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        // Verify the component loads
        expect(screen.getByTestId("relationships-page")).toBeInTheDocument();
      });

      const monoId = screen.getByText("rel-123");
      expect(monoId).toHaveClass("mono");
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
        createPropertyDefinition({ id: "prop-1", title: "works_for" }),
      ]);

      server.use(
        rest.get("*/api/relationships", (req, res, ctx) => res(ctx.json(mockRelationships))),
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Classes API error" })),
        ),
        rest.get("*/api/properties", (req, res, ctx) => res(ctx.json(mockProperties))),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        // Relationships and properties should render
        expect(screen.getByText("works_for")).toBeInTheDocument();
        // Missing class names show as em-dash
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
        createPropertyDefinition({ id: "prop-1", title: "works_for" }),
        createPropertyDefinition({ id: "prop-2", title: "manages" }),
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
        rest.get("*/api/relationships", (req, res, ctx) => res(ctx.json(mockRelationships))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/properties", (req, res, ctx) => res(ctx.json(mockProperties))),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        expect(screen.getByText("works_for")).toBeInTheDocument();
        expect(screen.getByText("manages")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "works_for");

      expect(screen.getByText("works_for")).toBeInTheDocument();
      expect(screen.queryByText("manages")).not.toBeInTheDocument();
    });

    it("shows filtered empty state when filters match no results", async () => {
      const mockClasses = createListClasses([createClass({ id: "class-1", title: "Person" })]);

      const mockProperties = createListProperties([
        createPropertyDefinition({ id: "prop-1", title: "works_for" }),
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
        rest.get("*/api/relationships", (req, res, ctx) => res(ctx.json(mockRelationships))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/properties", (req, res, ctx) => res(ctx.json(mockProperties))),
      );

      render(<RelationshipsPage />);

      await waitFor(() => {
        expect(screen.getByText("works_for")).toBeInTheDocument();
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
