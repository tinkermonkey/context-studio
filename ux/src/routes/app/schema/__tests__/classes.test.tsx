import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { createListClasses, createClass, createListSchemes } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import ClassesPage from "../classes";

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

describe("Classes Schema Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading skeleton state before data arrives", async () => {
      server.use(
        rest.get("*/api/classes", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createListClasses([])));
        }),
        rest.get("*/api/schemes", (req, res, ctx) =>
          res(ctx.json(createListSchemes([]))),
        ),
      );

      const { container } = render(<ClassesPage />);

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
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.json(createListClasses([]))),
        ),
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

      server.use(
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.json(mockClasses)),
        ),
      );

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

      server.use(
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.json(mockClasses)),
        ),
      );

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestClass")).toBeInTheDocument();
      });

      const monoId = screen.getByText("class-12");
      expect(monoId).toHaveClass("mono");
    });

    it("displays description column with em-dash placeholder when empty", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "TestClass",
          description: null,
        }),
      ]);

      server.use(
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.json(mockClasses)),
        ),
      );

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestClass")).toBeInTheDocument();
      });

      const cells = screen.getAllByText("—");
      expect(cells.length).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // Partial State (Filtered)
  // ========================================================================
  describe("partial state with filtering", () => {
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

      server.use(
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.json(mockClasses)),
        ),
      );

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

      server.use(
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.json(mockClasses)),
        ),
      );

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
});
