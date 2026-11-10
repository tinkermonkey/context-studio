import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import type { ReactNode } from "react";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createDataset,
  createListTaxonomies,
  createTaxonomy,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { DatasetsPage } from "../DatasetsPage";
import { datasetSlug } from "../CreateDatasetModal";

const mockNavigate = vi.hoisted(() => vi.fn());
const { toastSpy } = vi.hoisted(() => ({ toastSpy: vi.fn() }));
vi.mock("@/components/ui/Toast", () => ({
  ToastProvider: ({ children }: { children: ReactNode }) => children,
  useToasts: () => ({ toast: toastSpy, toasts: [], dismiss: vi.fn() }),
}));
let mockSearch: { dataset?: string } = {};
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => mockNavigate, useSearch: () => mockSearch };
});

const dr = createTaxonomy({ id: "tax-dr", identifier: "dr_spec", title: "Documentation Robotics" });
const life = createTaxonomy({ id: "tax-life", identifier: "life", title: "Life Sciences" });
const contextStudio = createDataset({
  id: "ds-1",
  taxonomy_id: "tax-dr",
  identifier: "context-studio",
  title: "Context Studio",
  yields_to_schema: true,
  individual_count: 450,
  relationship_count: 402,
});
const sample = createDataset({
  id: "ds-2",
  taxonomy_id: "tax-dr",
  identifier: "sample",
  title: "Sample",
  individual_count: 1,
  relationship_count: 0,
});

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  mockNavigate.mockClear();
  toastSpy.mockClear();
  mockSearch = {};
});
afterAll(() => server.close());

function serve(datasets = [contextStudio, sample], taxonomies = [dr, life]) {
  const requests: URL[] = [];
  server.use(
    http.get("*/api/datasets", ({ request }) => {
      const url = new URL(request.url);
      requests.push(url);
      const taxonomyId = url.searchParams.get("taxonomy_id");
      return HttpResponse.json(datasets.filter((d) => !taxonomyId || d.taxonomy_id === taxonomyId));
    }),
    http.get("*/api/taxonomies", () => HttpResponse.json(createListTaxonomies(taxonomies))),
  );
  return requests;
}

const table = () => within(screen.getByTestId("datasets-table"));

describe("DatasetsPage", () => {
  it("lists each dataset with its taxonomy and size", async () => {
    serve();
    render(<DatasetsPage onTaxonomyChange={vi.fn()} />);

    const row = await screen.findByTestId("dataset-row-ds-1");
    expect(row).toHaveTextContent("Context Studio");
    expect(row).toHaveTextContent("context-studio");
    expect(row).toHaveTextContent("yields to schema");
    expect(screen.getByTestId("dataset-row-ds-2")).not.toHaveTextContent("yields to schema");
    expect(table().getByText("450")).toBeInTheDocument();
    expect(table().getByText("402")).toBeInTheDocument();
    expect((await table().findAllByText("Documentation Robotics")).length).toBe(2);
  });

  it("filters by taxonomy through the URL parameter", async () => {
    const requests = serve();
    const onTaxonomyChange = vi.fn();
    const user = userEvent.setup();
    const { unmount } = render(<DatasetsPage onTaxonomyChange={onTaxonomyChange} />);

    const filter = await screen.findByTestId("dataset-taxonomy-filter");
    expect(filter).toHaveAccessibleName("Filter by taxonomy");
    await user.selectOptions(filter, "tax-life");
    expect(onTaxonomyChange).toHaveBeenCalledWith("tax-life");
    unmount();

    render(<DatasetsPage taxonomyId="tax-life" onTaxonomyChange={onTaxonomyChange} />);
    await waitFor(() =>
      expect(requests.some((u) => u.searchParams.get("taxonomy_id") === "tax-life")).toBe(true),
    );
    expect(await table().findByText("No datasets yet")).toBeInTheDocument();
  });

  it("opens a dataset's individuals from its row", async () => {
    serve();
    const user = userEvent.setup();
    render(<DatasetsPage onTaxonomyChange={vi.fn()} />);

    await user.click(await screen.findByTestId("dataset-row-ds-2"));

    expect(mockNavigate).toHaveBeenCalledWith({
      to: "/app/data/individuals",
      search: { dataset: "ds-2" },
    });
  });

  it("shows an empty state with a create action", async () => {
    serve([]);
    const user = userEvent.setup();
    render(<DatasetsPage onTaxonomyChange={vi.fn()} />);

    expect(await table().findByText("No datasets yet")).toBeInTheDocument();
    await user.click(table().getByTestId("empty-state-action"));
    expect(screen.getByTestId("dataset-create-modal")).toBeInTheDocument();
  });

  describe("create", () => {
    it("derives the identifier from the title", () => {
      expect(datasetSlug("Context Studio 2")).toBe("context-studio-2");
      expect(datasetSlug("  42 Sample!  ")).toBe("sample");
    });

    it("validates, then clears each error as the field is corrected", async () => {
      serve();
      const user = userEvent.setup();
      render(<DatasetsPage onTaxonomyChange={vi.fn()} />);
      await user.click(screen.getByTestId("dataset-add-button"));

      await user.click(screen.getByTestId("dataset-submit-button"));
      expect(screen.getByText("Choose a taxonomy.")).toBeInTheDocument();
      expect(screen.getByText("Enter a title.")).toBeInTheDocument();
      expect(screen.getByText("Enter an identifier.")).toBeInTheDocument();

      await user.type(screen.getByTestId("dataset-title-input"), "Draft");
      expect(screen.queryByText("Enter a title.")).not.toBeInTheDocument();
      expect(screen.queryByText("Enter an identifier.")).not.toBeInTheDocument();
      expect(screen.getByTestId("dataset-identifier-input")).toHaveValue("draft");

      await user.selectOptions(screen.getByTestId("dataset-taxonomy-select"), "tax-dr");
      expect(screen.queryByText("Choose a taxonomy.")).not.toBeInTheDocument();

      await user.clear(screen.getByTestId("dataset-identifier-input"));
      await user.type(screen.getByTestId("dataset-identifier-input"), "9bad");
      await user.click(screen.getByTestId("dataset-submit-button"));
      expect(
        screen.getByText("Start with a lowercase letter; use lowercase letters, digits, - or _."),
      ).toBeInTheDocument();
      await user.type(screen.getByTestId("dataset-identifier-input"), "x");
      expect(
        screen.queryByText("Start with a lowercase letter; use lowercase letters, digits, - or _."),
      ).not.toBeInTheDocument();
    });

    it("creates the dataset in the chosen taxonomy", async () => {
      serve();
      let body: unknown;
      server.use(
        http.post("*/api/datasets", async ({ request }) => {
          body = await request.json();
          return HttpResponse.json(
            createDataset({
              id: "ds-9",
              taxonomy_id: "tax-dr",
              identifier: "draft",
              title: "Draft",
            }),
            { status: 201 },
          );
        }),
      );
      const user = userEvent.setup();
      render(<DatasetsPage taxonomyId="tax-dr" onTaxonomyChange={vi.fn()} />);
      await user.click(screen.getByTestId("dataset-add-button"));

      expect(screen.getByTestId("dataset-taxonomy-select")).toHaveValue("tax-dr");
      await user.type(screen.getByTestId("dataset-title-input"), "Draft");
      await user.click(screen.getByTestId("dataset-submit-button"));

      await waitFor(() =>
        expect(screen.queryByTestId("dataset-create-modal")).not.toBeInTheDocument(),
      );
      expect(body).toEqual({ taxonomy_id: "tax-dr", identifier: "draft", title: "Draft" });
      expect(toastSpy).toHaveBeenCalledWith("success", "Dataset “Draft” created");
    });

    it("says when the taxonomy already has the identifier", async () => {
      serve();
      server.use(
        http.post("*/api/datasets", () =>
          HttpResponse.json({ detail: "Dataset 'sample' already exists" }, { status: 409 }),
        ),
      );
      const user = userEvent.setup();
      render(<DatasetsPage taxonomyId="tax-dr" onTaxonomyChange={vi.fn()} />);
      await user.click(screen.getByTestId("dataset-add-button"));
      await user.type(screen.getByTestId("dataset-title-input"), "Sample");
      await user.click(screen.getByTestId("dataset-submit-button"));

      expect(
        await screen.findByText("This taxonomy already has a dataset with this identifier."),
      ).toBeInTheDocument();
      expect(screen.getByTestId("dataset-create-modal")).toBeInTheDocument();
    });
  });

  describe("delete", () => {
    it("confirms with what goes, then deletes the dataset with its data", async () => {
      serve();
      let deleted: string | undefined;
      server.use(
        http.delete("*/api/datasets/:id", ({ params }) => {
          deleted = params.id as string;
          return HttpResponse.json({
            dataset_id: params.id,
            individual_count: 450,
            relationship_count: 402,
          });
        }),
      );
      const user = userEvent.setup();
      render(<DatasetsPage onTaxonomyChange={vi.fn()} />);

      const button = await screen.findByTestId("dataset-row-delete-ds-1");
      expect(button).toHaveAccessibleName("Delete dataset Context Studio");
      await user.click(button);

      const summary = screen.getByTestId("dataset-delete-summary");
      expect(summary).toHaveTextContent(
        "Delete Context Studio with its 450 individuals and 402 relationships?",
      );
      // The delete button does not open the row.
      expect(mockNavigate).not.toHaveBeenCalled();

      await user.click(screen.getByRole("button", { name: "Delete dataset" }));

      await waitFor(() => expect(deleted).toBe("ds-1"));
      await waitFor(() =>
        expect(toastSpy).toHaveBeenCalledWith(
          "success",
          "Dataset deleted: 450 individuals and 402 relationships removed",
        ),
      );
      expect(screen.queryByTestId("dataset-delete-summary")).not.toBeInTheDocument();
    });

    it("clears the selected dataset when it is the one deleted", async () => {
      mockSearch = { dataset: "ds-2" };
      serve();
      server.use(
        http.delete("*/api/datasets/:id", ({ params }) =>
          HttpResponse.json({ dataset_id: params.id, individual_count: 1, relationship_count: 0 }),
        ),
      );
      const user = userEvent.setup();
      render(<DatasetsPage onTaxonomyChange={vi.fn()} />);

      await user.click(await screen.findByTestId("dataset-row-delete-ds-2"));
      await user.click(screen.getByRole("button", { name: "Delete dataset" }));

      await waitFor(() =>
        expect(mockNavigate).toHaveBeenCalledWith(expect.objectContaining({ to: "." })),
      );
      expect(mockNavigate.mock.calls[0][0].search({ dataset: "ds-2" }).dataset).toBeUndefined();
    });

    it("cancelling deletes nothing", async () => {
      serve();
      const user = userEvent.setup();
      render(<DatasetsPage onTaxonomyChange={vi.fn()} />);

      await user.click(await screen.findByTestId("dataset-row-delete-ds-1"));
      await user.click(screen.getByRole("button", { name: "Cancel" }));

      expect(screen.queryByTestId("dataset-delete-summary")).not.toBeInTheDocument();
    });
  });
});
