import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { ontologyService } from "@/api/services/ontology";
import {
  createDataset,
  createListTaxonomies,
  createTaxonomy,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { DatasetSelect } from "../DatasetSelect";

const mockNavigate = vi.hoisted(() => vi.fn());
let mockSearch: { dataset?: string } = {};
vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return { ...actual, useNavigate: () => mockNavigate, useSearch: () => mockSearch };
});

const drDefault = createDataset({
  id: "ds-1",
  taxonomy_id: "tax-dr",
  identifier: "context-studio",
  title: "Context Studio",
});
const drSample = createDataset({
  id: "ds-2",
  taxonomy_id: "tax-dr",
  identifier: "sample",
  title: "Sample",
});
const lifeDefault = createDataset({
  id: "ds-3",
  taxonomy_id: "tax-life",
  identifier: "default",
  title: "Default",
});

function setup(datasets: ReturnType<typeof createDataset>[]) {
  vi.spyOn(ontologyService, "listDatasets").mockResolvedValue(datasets);
  vi.spyOn(ontologyService, "listTaxonomies").mockResolvedValue(
    createListTaxonomies([
      createTaxonomy({ id: "tax-dr", title: "Documentation Robotics" }),
      createTaxonomy({ id: "tax-life", title: "Life Sciences" }),
    ]),
  );
}

describe("DatasetSelect", () => {
  beforeEach(() => {
    mockSearch = {};
  });
  afterEach(() => {
    vi.restoreAllMocks();
    mockNavigate.mockClear();
  });

  it("renders nothing when each taxonomy has one dataset", async () => {
    const listDatasets = vi.spyOn(ontologyService, "listDatasets").mockResolvedValue([drDefault]);
    render(<DatasetSelect />);
    await vi.waitFor(() => expect(listDatasets).toHaveBeenCalled());
    expect(screen.queryByTestId("dataset-select")).not.toBeInTheDocument();
  });

  it("offers All datasets and each dataset once a taxonomy has two", async () => {
    setup([drDefault, drSample]);
    render(<DatasetSelect data-testid="graph-dataset-select" />);

    const select = await screen.findByTestId("graph-dataset-select");
    expect(select).toHaveClass("select", "dataset-select");
    expect(select).toHaveAccessibleName("Dataset");
    expect(select).toHaveValue("all");
    const options = within(select).getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual([
      "All datasets",
      "Context Studio · context-studio",
      "Sample · sample",
    ]);
  });

  it("groups datasets by taxonomy when there are several taxonomies", async () => {
    setup([drDefault, drSample, lifeDefault]);
    render(<DatasetSelect />);

    const select = await screen.findByTestId("dataset-select");
    expect(await within(select).findByText("Life Sciences")).toBeInTheDocument();
    expect(within(select).getByText("Documentation Robotics")).toBeInTheDocument();
  });

  it("offers only the given taxonomy's datasets", async () => {
    setup([drDefault, drSample, lifeDefault]);
    render(<DatasetSelect taxonomyId="tax-dr" />);

    const select = await screen.findByTestId("dataset-select");
    expect(within(select).queryByText(/Default · default/)).not.toBeInTheDocument();
    expect(within(select).queryByText("Life Sciences")).not.toBeInTheDocument();
  });

  it("shows the selected dataset and changes the URL parameter", async () => {
    mockSearch = { dataset: "ds-2" };
    setup([drDefault, drSample]);
    const user = userEvent.setup();
    render(<DatasetSelect />);

    const select = await screen.findByTestId("dataset-select");
    expect(select).toHaveValue("ds-2");

    await user.selectOptions(select, "all");
    expect(mockNavigate.mock.calls[0][0].search({ dataset: "ds-2" })).toEqual({
      dataset: undefined,
    });

    await user.selectOptions(select, "ds-1");
    expect(mockNavigate.mock.calls[1][0].search({})).toEqual({ dataset: "ds-1" });
  });
});
