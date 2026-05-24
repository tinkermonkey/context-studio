import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createListClasses,
  createClass,
  createListSchemes,
  createConceptScheme,
  createListTaxonomies,
  createListProperties,
  createListRelationships,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { ClassesPage } from "../classes";

const server = setupServer(
  rest.get("*/api/taxonomies", (req, res, ctx) => res(ctx.json(createListTaxonomies([])))),
  rest.get("*/api/properties", (req, res, ctx) => res(ctx.json(createListProperties([])))),
  rest.get("*/api/relationships", (req, res, ctx) => res(ctx.json(createListRelationships([])))),
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

describe("Classes Schema Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading skeleton state with 5 skeleton rows matching table layout", async () => {
      server.use(
        rest.get("*/api/classes", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createListClasses([])));
        }),
        rest.get("*/api/schemes", (req, res, ctx) => res(ctx.json(createListSchemes([])))),
      );

      const { container } = render(<ClassesPage />);

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
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Internal server error" })),
        ),
      );

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load classes/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state copy when no classes exist", async () => {
      server.use(
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(createListClasses([])))),
      );

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("No classes yet")).toBeInTheDocument();
        expect(
          screen.getByText("Classes are the types your individuals will conform to."),
        ).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("displays table with classes when data loads", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "Person",
          description: "A person entity",
        }),
        createClass({
          id: "class-2",
          title: "Company",
          description: "A company entity",
        }),
      ]);

      server.use(rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))));

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("Person")).toBeInTheDocument();
        expect(screen.getByText("Company")).toBeInTheDocument();
      });
    });

    it("displays mono ID in first column of table rows", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))));

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestClass")).toBeInTheDocument();
      });

      const monoId = screen.getByText("class-12");
      expect(monoId.tagName.toLowerCase()).toBe("code");
    });

    it("displays description column with em-dash placeholder when empty", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "TestClass",
          description: null,
        }),
      ]);

      server.use(rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))));

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestClass")).toBeInTheDocument();
      });

      const cells = screen.getAllByText("—");
      expect(cells.length).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // Filtered State
  // ========================================================================
  describe("filtered state", () => {
    it("filters classes by search term", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "Person",
        }),
        createClass({
          id: "class-2",
          title: "Company",
        }),
        createClass({
          id: "class-3",
          title: "Location",
        }),
      ]);

      server.use(rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))));

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("Person")).toBeInTheDocument();
        expect(screen.getByText("Company")).toBeInTheDocument();
        expect(screen.getByText("Location")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "Person");

      expect(screen.getByText("Person")).toBeInTheDocument();
      expect(screen.queryByText("Company")).not.toBeInTheDocument();
      expect(screen.queryByText("Location")).not.toBeInTheDocument();
    });

    it("clears filter when search term is removed", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "Person",
        }),
        createClass({
          id: "class-2",
          title: "Company",
        }),
      ]);

      server.use(rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))));

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("Person")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await userEvent.type(searchInput, "Company");

      expect(screen.queryByText("Person")).not.toBeInTheDocument();

      await userEvent.clear(searchInput);

      expect(screen.getByText("Person")).toBeInTheDocument();
      expect(screen.getByText("Company")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Partial State
  // ========================================================================
  describe("partial state", () => {
    it("displays classes table even when schemes query fails", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "Person",
          concept_scheme_id: "scheme-1",
        }),
        createClass({
          id: "class-2",
          title: "Company",
          concept_scheme_id: "scheme-1",
        }),
      ]);

      server.use(
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/schemes", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Failed to load schemes" })),
        ),
      );

      render(<ClassesPage />);

      // Verify error banner appears for schemes failure
      await waitFor(() => {
        expect(screen.getByText(/Failed to load domains/i)).toBeInTheDocument();
      });

      // Verify classes table still renders despite schemes error
      expect(screen.getByText("Person")).toBeInTheDocument();
      expect(screen.getByText("Company")).toBeInTheDocument();

      // Verify retry button is available for schemes
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });

    it("can retry schemes query independently when partial state occurs", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "Person",
          concept_scheme_id: "scheme-1",
        }),
      ]);

      const mockSchemes = createListSchemes([
        createConceptScheme({ id: "scheme-1", title: "People Domain" }),
      ]);

      let schemesCallCount = 0;

      server.use(
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/schemes", (req, res, ctx) => {
          schemesCallCount++;
          if (schemesCallCount === 1) {
            return res(ctx.status(500), ctx.json({ detail: "Failed to load schemes" }));
          }
          return res(ctx.json(mockSchemes));
        }),
      );

      render(<ClassesPage />);

      // Verify initial error state
      await waitFor(() => {
        expect(screen.getByText(/Failed to load domains/i)).toBeInTheDocument();
      });

      // Verify class is visible
      expect(screen.getByText("Person")).toBeInTheDocument();

      // Click retry and verify recovery
      const retryButtons = screen.getAllByRole("button", { name: /retry/i });
      const schemesRetryButton = retryButtons[0]; // First retry button is for schemes error
      await userEvent.click(schemesRetryButton);

      // Wait for schemes to load successfully
      await waitFor(() => {
        // Error banner should disappear
        expect(screen.queryByText(/Failed to load domains/i)).not.toBeInTheDocument();
        // Scheme name should now appear in the Domain column
        expect(screen.getByText("People Domain")).toBeInTheDocument();
      });
    });
  });
});
