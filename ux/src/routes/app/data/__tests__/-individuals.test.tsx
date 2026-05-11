import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createListIndividuals,
  createIndividual,
  createListClasses,
  createClass,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { IndividualsPage } from "../individuals";

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

describe("Individuals Data Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading skeleton state while data loads", async () => {
      server.use(
        rest.get("*/api/individuals", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createListIndividuals([])));
        }),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(createListClasses([]))))
      );

      const { container } = render(<IndividualsPage />);

      const skeletonElements = container.querySelectorAll(
        "div[style*='animation: skeleton-shimmer']",
      );
      expect(skeletonElements.length).toBeGreaterThanOrEqual(5);
    });

    it("verifies data-testid attribute present on page container during loading", async () => {
      server.use(
        rest.get("*/api/individuals", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createListIndividuals([])));
        }),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(createListClasses([]))))
      );

      render(<IndividualsPage />);

      const page = screen.getByTestId("individuals-page");
      expect(page).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner with retry button when API fails", async () => {
      server.use(
        rest.get("*/api/individuals", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Internal server error" })),
        ),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load individuals/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });

    it("verifies error state displays error message before table loads", async () => {
      server.use(
        rest.get("*/api/individuals", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Internal server error" })),
        ),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load individuals/i)).toBeInTheDocument();
      });

      const errorBanner = screen.getByText(/Failed to load individuals/i);
      expect(errorBanner).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state copy when no individuals exist", async () => {
      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(createListIndividuals([])))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("No individuals yet")).toBeInTheDocument();
        expect(
          screen.getByText(/Individuals are instances of classes/i),
        ).toBeInTheDocument();
      });
    });

    it("displays CTA button with correct label in empty state", async () => {
      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(createListIndividuals([])))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("No individuals yet")).toBeInTheDocument();
      });

      const actionButton = screen.getByTestId("empty-state-action");
      expect(actionButton).toBeInTheDocument();
      expect(actionButton).toHaveTextContent("+ New individual");
    });

    it("verifies empty-state element is present", async () => {
      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(createListIndividuals([])))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("empty-state")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("displays table with individuals when data loads", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-person-001",
          title: "John Doe",
          description: "A person entity",
          class_ids: ["class-person"],
        }),
        createIndividual({
          id: "ind-person-002",
          title: "Jane Smith",
          description: "Another person",
          class_ids: ["class-person"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("John Doe")).toBeInTheDocument();
        expect(screen.getByText("Jane Smith")).toBeInTheDocument();
      });
    });

    it("displays mono ID truncated to 8 characters in first column", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "individual-with-very-long-id-12345",
          title: "Test Individual",
          class_ids: ["class-123"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Individual")).toBeInTheDocument();
      });

      const monoId = screen.getByText("individu");
      expect(monoId).toHaveClass("mono");
    });

    it("displays class chips with correct class names", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-person", "class-employee"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
        createClass({
          id: "class-employee",
          title: "Employee",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-chip-class-person")).toBeInTheDocument();
        expect(screen.getByTestId("individual-class-chip-class-employee")).toBeInTheDocument();
      });

      expect(screen.getByText("Person")).toBeInTheDocument();
      expect(screen.getByText("Employee")).toBeInTheDocument();
    });

    it("displays description column with em-dash placeholder when empty", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          description: null,
          class_ids: ["class-123"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Individual")).toBeInTheDocument();
      });

      const cells = screen.getAllByText("—");
      expect(cells.length).toBeGreaterThan(0);
    });

    it("verifies row-level testids are present for interactive elements", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-123"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Individual")).toBeInTheDocument();
      });

      expect(screen.getByTestId("individual-row-edit-ind-001")).toBeInTheDocument();
      expect(screen.getByTestId("individual-row-delete-ind-001")).toBeInTheDocument();
    });

    it("verifies name cell is clickable and has correct testid", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-123"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Individual")).toBeInTheDocument();
      });

      const nameCell = screen.getByTestId("individual-name-ind-001");
      expect(nameCell).toHaveStyle({ cursor: "pointer" });
    });
  });

  // ========================================================================
  // Filtered State
  // ========================================================================
  describe("filtered/search state", () => {
    it("filters individuals by search term in title", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "John Doe",
          class_ids: ["class-person"],
        }),
        createIndividual({
          id: "ind-002",
          title: "Jane Smith",
          class_ids: ["class-person"],
        }),
        createIndividual({
          id: "ind-003",
          title: "Alice Brown",
          class_ids: ["class-person"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("John Doe")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "John");

      expect(screen.getByText("John Doe")).toBeInTheDocument();
      expect(screen.queryByText("Jane Smith")).not.toBeInTheDocument();
      expect(screen.queryByText("Alice Brown")).not.toBeInTheDocument();
    });

    it("displays 'no results' empty state when search yields no matches", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "John Doe",
          class_ids: ["class-person"],
        }),
        createIndividual({
          id: "ind-002",
          title: "Jane Smith",
          class_ids: ["class-person"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("John Doe")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "NonexistentIndividual");

      await waitFor(() => {
        expect(screen.getByText("No matching individuals")).toBeInTheDocument();
      });
    });

    it("clears filter when search input is cleared", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "John Doe",
          class_ids: ["class-person"],
        }),
        createIndividual({
          id: "ind-002",
          title: "Jane Smith",
          class_ids: ["class-person"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("John Doe")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await userEvent.type(searchInput, "John");

      expect(screen.queryByText("Jane Smith")).not.toBeInTheDocument();

      await userEvent.clear(searchInput);

      expect(screen.getByText("John Doe")).toBeInTheDocument();
      expect(screen.getByText("Jane Smith")).toBeInTheDocument();
    });

    it("filters individuals by description text", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Individual A",
          description: "CEO of the company",
          class_ids: ["class-person"],
        }),
        createIndividual({
          id: "ind-002",
          title: "Individual B",
          description: "Software engineer",
          class_ids: ["class-person"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("Individual A")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "CEO");

      expect(screen.getByText("Individual A")).toBeInTheDocument();
      expect(screen.queryByText("Individual B")).not.toBeInTheDocument();
    });
  });

  // ========================================================================
  // Partial State (Classes Fail)
  // ========================================================================
  describe("partial state - individuals load but classes fail", () => {
    it("displays individuals table even if classes query fails", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-123"],
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Server error" })),
        ),
      );

      render(<IndividualsPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Individual")).toBeInTheDocument();
      });

      expect(screen.getByTestId("individuals-page")).toBeInTheDocument();
    });
  });
});
