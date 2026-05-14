import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createDataset,
  createListDatasets,
} from "@/api/services/__tests__/fixtures/admin.fixtures";
import { DatasetsPage } from "../datasets";

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

describe("Datasets Data Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading skeleton state while data loads", async () => {
      server.use(
        rest.get("*/api/v1/admin/datasets", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createListDatasets([])));
        }),
      );

      const { container } = render(<DatasetsPage />);

      const skeletonElements = container.querySelectorAll(
        "div[style*='animation: skeleton-shimmer']",
      );
      expect(skeletonElements.length).toBeGreaterThanOrEqual(5);
    });

    it("verifies data-testid attribute present on page container during loading", async () => {
      server.use(
        rest.get("*/api/v1/admin/datasets", async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(ctx.json(createListDatasets([])));
        }),
      );

      render(<DatasetsPage />);

      const page = screen.getByTestId("datasets-page");
      expect(page).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner with retry button when API fails", async () => {
      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Internal server error" })),
        ),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load datasets/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state copy when no datasets exist", async () => {
      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) =>
          res(ctx.json(createListDatasets([]))),
        ),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("No datasets yet")).toBeInTheDocument();
        expect(
          screen.getByText(/Datasets allow you to manage and organize imported data sources/i),
        ).toBeInTheDocument();
      });
    });

    it("displays CTA button with correct label in empty state", async () => {
      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) =>
          res(ctx.json(createListDatasets([]))),
        ),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("No datasets yet")).toBeInTheDocument();
      });

      const actionButton = screen.getByTestId("empty-state-new-dataset");
      expect(actionButton).toBeInTheDocument();
      expect(actionButton).toHaveTextContent("Create Dataset");
    });

    it("verifies empty-state element is present", async () => {
      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) =>
          res(ctx.json(createListDatasets([]))),
        ),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("empty-state")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("displays table with datasets when data loads", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Customer Data",
          filename: "customers.csv",
          description: "Customer information",
          is_active: false,
        }),
        createDataset({
          id: "dataset-002",
          title: "Product Data",
          filename: "products.csv",
          description: "Product catalog",
          is_active: true,
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Customer Data")).toBeInTheDocument();
        expect(screen.getByText("Product Data")).toBeInTheDocument();
      });
    });

    it("displays mono ID truncated to 8 characters in first column", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-with-very-long-id-12345",
          title: "Test Dataset",
          filename: "test.csv",
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Dataset")).toBeInTheDocument();
      });

      const monoId = screen.getByText("dataset-");
      expect(monoId).toHaveClass("mono");
    });

    it("displays status column with Active for active datasets", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Active Dataset",
          filename: "active.csv",
          is_active: true,
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Active Dataset")).toBeInTheDocument();
      });

      expect(screen.getByText("Active")).toBeInTheDocument();
    });

    it("displays status column with Inactive for inactive datasets", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Inactive Dataset",
          filename: "inactive.csv",
          is_active: false,
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Inactive Dataset")).toBeInTheDocument();
      });

      expect(screen.getByText("Inactive")).toBeInTheDocument();
    });

    it("displays description column with em-dash placeholder when empty", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Test Dataset",
          filename: "test.csv",
          description: null,
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Dataset")).toBeInTheDocument();
      });

      const cells = screen.getAllByText("—");
      expect(cells.length).toBeGreaterThan(0);
    });

    it("truncates long descriptions in description column", async () => {
      const longDescription =
        "This is a very long description that should be truncated at 50 characters";
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Test Dataset",
          filename: "test.csv",
          description: longDescription,
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Dataset")).toBeInTheDocument();
      });

      const truncatedDesc = screen.getByText(/This is a very long description that should/);
      expect(truncatedDesc).toBeInTheDocument();
      expect(truncatedDesc.textContent).toContain("…");
    });

    it("verifies row-level testids are present for delete actions", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Test Dataset",
          filename: "test.csv",
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Dataset")).toBeInTheDocument();
      });

      expect(screen.getByTestId("dataset-row-delete-dataset-001")).toBeInTheDocument();
    });

    it("verifies name cell is clickable and has correct testid", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Test Dataset",
          filename: "test.csv",
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Test Dataset")).toBeInTheDocument();
      });

      const nameCell = screen.getByTestId("dataset-name-dataset-001");
      expect(nameCell).toHaveStyle({ cursor: "pointer" });
    });

    it("disables delete button for active datasets", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Active Dataset",
          filename: "active.csv",
          is_active: true,
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Active Dataset")).toBeInTheDocument();
      });

      const deleteButton = screen.getByTestId("dataset-row-delete-dataset-001");
      expect(deleteButton).toBeDisabled();
    });

    it("enables delete button for inactive datasets", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Inactive Dataset",
          filename: "inactive.csv",
          is_active: false,
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Inactive Dataset")).toBeInTheDocument();
      });

      const deleteButton = screen.getByTestId("dataset-row-delete-dataset-001");
      expect(deleteButton).not.toBeDisabled();
    });
  });

  // ========================================================================
  // Filtered/Search State
  // ========================================================================
  describe("filtered/search state", () => {
    it("filters datasets by search term in title", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Customer Data",
          filename: "customers.csv",
        }),
        createDataset({
          id: "dataset-002",
          title: "Product Data",
          filename: "products.csv",
        }),
        createDataset({
          id: "dataset-003",
          title: "Sales Data",
          filename: "sales.csv",
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Customer Data")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "Customer");

      expect(screen.getByText("Customer Data")).toBeInTheDocument();
      expect(screen.queryByText("Product Data")).not.toBeInTheDocument();
      expect(screen.queryByText("Sales Data")).not.toBeInTheDocument();
    });

    it("filters datasets by description text", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Dataset A",
          filename: "a.csv",
          description: "Contains customer records",
        }),
        createDataset({
          id: "dataset-002",
          title: "Dataset B",
          filename: "b.csv",
          description: "Contains product inventory",
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Dataset A")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "customer");

      expect(screen.getByText("Dataset A")).toBeInTheDocument();
      expect(screen.queryByText("Dataset B")).not.toBeInTheDocument();
    });

    it("filters datasets by ID text", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-abc-001",
          title: "Dataset A",
          filename: "a.csv",
        }),
        createDataset({
          id: "dataset-xyz-002",
          title: "Dataset B",
          filename: "b.csv",
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Dataset A")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "abc");

      expect(screen.getByText("Dataset A")).toBeInTheDocument();
      expect(screen.queryByText("Dataset B")).not.toBeInTheDocument();
    });

    it("displays 'no results' empty state when search yields no matches", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Customer Data",
          filename: "customers.csv",
        }),
        createDataset({
          id: "dataset-002",
          title: "Product Data",
          filename: "products.csv",
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Customer Data")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "NonexistentDataset");

      await waitFor(() => {
        expect(screen.getByText("No datasets found")).toBeInTheDocument();
      });
    });

    it("clears filter when search input is cleared", async () => {
      const mockDatasets = createListDatasets([
        createDataset({
          id: "dataset-001",
          title: "Customer Data",
          filename: "customers.csv",
        }),
        createDataset({
          id: "dataset-002",
          title: "Product Data",
          filename: "products.csv",
        }),
      ]);

      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) => res(ctx.json(mockDatasets))),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Customer Data")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await userEvent.type(searchInput, "Customer");

      expect(screen.queryByText("Product Data")).not.toBeInTheDocument();

      await userEvent.clear(searchInput);

      expect(screen.getByText("Customer Data")).toBeInTheDocument();
      expect(screen.getByText("Product Data")).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Page Header and CTA
  // ========================================================================
  describe("page header and call-to-action", () => {
    it("displays page title 'Datasets'", async () => {
      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) =>
          res(ctx.json(createListDatasets([]))),
        ),
      );

      render(<DatasetsPage />);

      await waitFor(() => {
        expect(screen.getByText("Datasets")).toBeInTheDocument();
      });
    });

    it("displays 'New Dataset' button in header", async () => {
      server.use(
        rest.get("*/api/v1/admin/datasets", (req, res, ctx) =>
          res(ctx.json(createListDatasets([]))),
        ),
      );

      render(<DatasetsPage />);

      const addButton = screen.getByTestId("dataset-add-button");
      expect(addButton).toBeInTheDocument();
      expect(addButton).toHaveTextContent("New Dataset");
    });
  });
});
