import type { ComponentType } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { pipelineService, type PipelineConfiguration } from "@/api/services/pipeline";
import { ontologyService } from "@/api/services/ontology";
import { referenceService } from "@/api/services/reference";
import { createDataset } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import type { components } from "@/api/types";
import { RUN_WIZARDS } from "../index";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@tanstack/react-router", async () => ({
  ...(await vi.importActual("@tanstack/react-router")),
  useNavigate: () => navigate,
}));

// Picking an entity is the picker's own concern: here one click picks a fixed one
// (a multi-select picker adds the next one each click).
vi.mock("../../EntitySearchPicker", () => ({
  EntitySearchPicker: ({
    entityType,
    onSelect,
    onSelectMultiple,
    selectedIds = [],
    multiSelect,
    "data-testid": testId,
  }: {
    entityType: string;
    onSelect?: (entity: { id: string; label: string }) => void;
    onSelectMultiple?: (entities: { id: string; label: string }[]) => void;
    selectedIds?: string[];
    multiSelect?: boolean;
    "data-testid"?: string;
  }) => (
    <button
      type="button"
      data-testid={testId}
      onClick={() => {
        if (multiSelect) {
          const next = selectedIds.length + 1;
          onSelectMultiple?.(
            Array.from({ length: next }, (_, i) => ({
              id: `${entityType}-${i + 1}`,
              label: `${entityType} ${i + 1}`,
            })),
          );
        } else {
          onSelect?.({ id: `${entityType}-1`, label: `${entityType} one` });
        }
      }}
    >
      pick {entityType}
    </button>
  ),
}));
vi.mock("@/api/hooks/ontology/useClasses", () => ({ useClass: () => ({ data: undefined }) }));

type PipelineRun = components["schemas"]["PipelineRunResponse"];

const configuration = (
  type: string,
  implementation: string,
  ref: string,
  isDefault: boolean,
): PipelineConfiguration =>
  ({
    id: `${type}:${implementation}:${ref}`,
    config_ref: ref,
    pipeline_type: type,
    implementation_id: implementation,
    name: ref,
    provider: "anthropic",
    model: "model-a",
    enabled: true,
    version: 1,
    is_system: true,
    is_default: isDefault,
  }) as PipelineConfiguration;

let runPipeline: ReturnType<typeof vi.spyOn>;
let createBatch: ReturnType<typeof vi.spyOn>;
let enqueueBatchRuns: ReturnType<typeof vi.spyOn>;

// The sources the grounding adapter registers, as the reference status lists them.
const REFERENCE_SOURCES = ["DBpedia", "ConceptNet", "Wikidata", "schema.org"];

beforeEach(() => {
  navigate.mockReset();
  // Every type has a default implementation that is not called "default", and a second one.
  vi.spyOn(pipelineService, "listImplementations").mockImplementation(async (type) => [
    { id: "second", pipeline_type: type, is_default: false, extracts_sources: false },
    { id: "base", pipeline_type: type, is_default: true, extracts_sources: false },
  ]);
  vi.spyOn(pipelineService, "listConfigurations").mockImplementation(async (type, impl) => [
    configuration(type, impl, `${impl}-alt`, false),
    configuration(type, impl, `${impl}-main`, true),
  ]);
  vi.spyOn(ontologyService, "listDatasets").mockResolvedValue([createDataset()]);
  runPipeline = vi
    .spyOn(pipelineService, "runPipeline")
    .mockResolvedValue({ id: "run-1" } as PipelineRun);
  createBatch = vi
    .spyOn(pipelineService, "createBatch")
    .mockResolvedValue({ id: "batch-1" } as Awaited<
      ReturnType<typeof pipelineService.createBatch>
    >);
  enqueueBatchRuns = vi
    .spyOn(pipelineService, "enqueueBatchRuns")
    .mockResolvedValue({ batch_id: "batch-1", run_ids: ["run-1"], run_count: 1 });
  vi.spyOn(referenceService, "getStatus").mockResolvedValue({
    sources: REFERENCE_SOURCES.map((name) => ({ name, available: true })),
    sources_available: REFERENCE_SOURCES.length,
    timestamp: "2026-11-24T00:00:00Z",
  });
});
afterEach(() => vi.restoreAllMocks());

function renderWizard(type: string) {
  const Wizard = RUN_WIZARDS[type] as ComponentType;
  render(<Wizard />);
}

/** Fill a wizard's own required fields; returns its test-id prefix. */
const FILL: Record<string, { prefix: string; fill: () => Promise<void> }> = {
  individual_extraction: {
    prefix: "individual-extraction",
    fill: async () => {
      await userEvent.type(screen.getByTestId("individual-extraction-source"), "Some text.");
      await userEvent.click(screen.getByTestId("individual-extraction-ontology"));
    },
  },
  schema_extraction: {
    prefix: "schema-extraction",
    fill: async () => {
      await userEvent.type(screen.getByTestId("schema-extraction-document"), "Some text.");
    },
  },
  schema_node_grounding: {
    prefix: "schema-grounding",
    fill: async () => {
      await userEvent.click(screen.getByTestId("schema-grounding-nodes"));
      await userEvent.click(await screen.findByTestId("schema-grounding-source-dbpedia"));
      await userEvent.click(screen.getByTestId("schema-grounding-source-schema_org"));
    },
  },
  schema_node_definition_refinement: {
    prefix: "definition-refinement",
    fill: async () => {
      await userEvent.click(screen.getByTestId("definition-refinement-class"));
      await userEvent.type(screen.getByTestId("definition-refinement-definition"), "A thing.");
    },
  },
  schema_node_connection_refinement: {
    prefix: "connection-refinement",
    fill: async () => {
      await userEvent.click(screen.getByTestId("connection-refinement-scope"));
    },
  },
};

describe("run wizards", () => {
  it("has a wizard for each type the tests fill", () => {
    expect(Object.keys(RUN_WIZARDS).sort()).toEqual(Object.keys(FILL).sort());
  });

  it.each(Object.keys(FILL))(
    "%s runs with the implementation and configuration its picker shows",
    async (type) => {
      const { prefix, fill } = FILL[type];
      renderWizard(type);
      const implementation = screen.getByTestId(`${prefix}-implementation`);
      const configuration = screen.getByTestId(`${prefix}-configuration`);
      // The server's defaults are preselected.
      await waitFor(() => expect(implementation).toHaveValue("base"));
      await waitFor(() => expect(configuration).toHaveValue("base-main"));

      await userEvent.selectOptions(implementation, "second");
      await waitFor(() => expect(configuration).toHaveValue("second-main"));
      await userEvent.selectOptions(configuration, "second-alt");
      await fill();
      await userEvent.click(screen.getByTestId(`${prefix}-submit`));

      // Grounding enqueues its runs in a batch; every other wizard starts one run
      let body: Record<string, unknown>;
      if (type === "schema_node_grounding") {
        await waitFor(() => expect(enqueueBatchRuns).toHaveBeenCalledTimes(1));
        expect(runPipeline).not.toHaveBeenCalled();
        const spec = enqueueBatchRuns.mock.calls[0][1].runs[0];
        expect(spec.pipeline_type).toBe(type);
        body = spec;
      } else {
        await waitFor(() => expect(runPipeline).toHaveBeenCalledTimes(1));
        const [runType, request] = runPipeline.mock.calls[0];
        expect(runType).toBe(type);
        body = request;
      }
      expect(body).toMatchObject({
        implementation_id: "second",
        configuration_ref: "second-alt",
      });
      // The model is the configuration's, and nothing runs "as a batch".
      expect(body).not.toHaveProperty("model");
      expect(body).not.toHaveProperty("run_as_batch");
      await waitFor(() =>
        expect(navigate).toHaveBeenCalledWith({
          to: "/app/pipelines/runs",
          search: { selected: "run-1" },
        }),
      );
    },
  );

  it("grounding enqueues one run for one class: its id, type, configuration and source names", async () => {
    renderWizard("schema_node_grounding");
    await waitFor(() =>
      expect(screen.getByTestId("schema-grounding-configuration")).toHaveValue("base-main"),
    );
    await FILL.schema_node_grounding.fill();
    await userEvent.click(screen.getByTestId("schema-grounding-submit"));

    await waitFor(() => expect(enqueueBatchRuns).toHaveBeenCalledTimes(1));
    expect(createBatch).toHaveBeenCalledTimes(1);
    expect(enqueueBatchRuns).toHaveBeenCalledWith("batch-1", {
      runs: [
        {
          pipeline_type: "schema_node_grounding",
          implementation_id: "base",
          configuration_ref: "base-main",
          // Read by the background worker; the server grounds the title of the class
          input_data: {
            node_id: "Class-1",
            node_type: "Class",
            // The adapter's own, case-sensitive source names.
            sources: ["DBpedia", "schema.org"],
          },
        },
      ],
    });
    expect(runPipeline).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith({
        to: "/app/pipelines/runs",
        search: { selected: "run-1" },
      }),
    );
  });

  it("grounding enqueues one run per selected class in one batch, and opens the runs list", async () => {
    enqueueBatchRuns.mockResolvedValue({
      batch_id: "batch-1",
      run_ids: ["run-1", "run-2", "run-3"],
      run_count: 3,
    });
    renderWizard("schema_node_grounding");
    await waitFor(() =>
      expect(screen.getByTestId("schema-grounding-configuration")).toHaveValue("base-main"),
    );
    // Each click on the picker adds the next class
    await userEvent.click(screen.getByTestId("schema-grounding-nodes"));
    await userEvent.click(screen.getByTestId("schema-grounding-nodes"));
    await userEvent.click(screen.getByTestId("schema-grounding-nodes"));
    await userEvent.click(await screen.findByTestId("schema-grounding-source-conceptnet"));
    expect(screen.getByTestId("schema-grounding-submit")).toHaveTextContent("Run 3 Pipelines");
    await userEvent.click(screen.getByTestId("schema-grounding-submit"));

    await waitFor(() => expect(enqueueBatchRuns).toHaveBeenCalledTimes(1));
    expect(createBatch).toHaveBeenCalledTimes(1);
    const spec = (nodeId: string) => ({
      pipeline_type: "schema_node_grounding",
      implementation_id: "base",
      configuration_ref: "base-main",
      input_data: { node_id: nodeId, node_type: "Class", sources: ["ConceptNet"] },
    });
    expect(enqueueBatchRuns).toHaveBeenCalledWith("batch-1", {
      runs: [spec("Class-1"), spec("Class-2"), spec("Class-3")],
    });
    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith({ to: "/app/pipelines/runs", search: {} }),
    );
  });

  it("grounding offers classes only and says why property definitions are not offered", async () => {
    renderWizard("schema_node_grounding");

    expect(screen.queryByRole("radio", { name: "Property Definition" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("schema-grounding-node-type")).not.toBeInTheDocument();
    expect(screen.getByTestId("schema-grounding-classes-only")).toHaveTextContent(
      "property definitions can't be grounded here",
    );
    expect(screen.getByTestId("schema-grounding-nodes")).toHaveTextContent("pick Class");
  });

  it("grounding offers the knowledge sources the reference status lists, and no others", async () => {
    renderWizard("schema_node_grounding");

    const group = await screen.findByTestId("schema-grounding-sources");
    await waitFor(() =>
      expect(Array.from(group.querySelectorAll("label")).map((label) => label.textContent)).toEqual(
        REFERENCE_SOURCES,
      ),
    );
  });

  it("individual extraction names no dataset while the taxonomy has one", async () => {
    renderWizard("individual_extraction");
    await FILL.individual_extraction.fill();
    await waitFor(() =>
      expect(screen.getByTestId("individual-extraction-configuration")).toHaveValue("base-main"),
    );
    expect(screen.queryByTestId("individual-extraction-dataset")).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("individual-extraction-submit"));

    await waitFor(() => expect(runPipeline).toHaveBeenCalledTimes(1));
    expect(runPipeline.mock.calls[0][1]).toEqual({
      implementation_id: "base",
      configuration_ref: "base-main",
      async: true,
      text: "Some text.",
      ontology_id: "Taxonomy-1",
      ontology_name: "Taxonomy one",
    });
  });

  it("individual extraction cannot start before the taxonomy's datasets are read", async () => {
    let serve: (d: ReturnType<typeof createDataset>[]) => void = () => {};
    vi.spyOn(ontologyService, "listDatasets").mockImplementation(
      () => new Promise((resolve) => (serve = resolve)),
    );
    renderWizard("individual_extraction");
    await FILL.individual_extraction.fill();
    const submit = screen.getByTestId("individual-extraction-submit");
    expect(submit).toBeDisabled();

    serve([createDataset({ id: "ds-only", taxonomy_id: "Taxonomy-1" })]);
    await waitFor(() => expect(submit).toBeEnabled());
  });

  it("individual extraction cannot start when the datasets could not be read", async () => {
    vi.spyOn(ontologyService, "listDatasets").mockRejectedValue(new Error("boom"));
    renderWizard("individual_extraction");
    await FILL.individual_extraction.fill();

    const dataset = await screen.findByTestId("individual-extraction-dataset");
    expect(dataset).toBeDisabled();
    expect(screen.getByText("Could not load the datasets: boom")).toHaveAttribute(
      "id",
      "individual-extraction-dataset-error",
    );
    expect(screen.getByTestId("individual-extraction-submit")).toBeDisabled();
    expect(runPipeline).not.toHaveBeenCalled();
  });

  it("individual extraction asks for the dataset when the taxonomy has several", async () => {
    vi.spyOn(ontologyService, "listDatasets").mockResolvedValue([
      createDataset({ id: "ds-a", taxonomy_id: "Taxonomy-1", identifier: "alpha" }),
      createDataset({ id: "ds-b", taxonomy_id: "Taxonomy-1", identifier: "beta" }),
    ]);
    renderWizard("individual_extraction");
    await FILL.individual_extraction.fill();

    const dataset = await screen.findByTestId("individual-extraction-dataset");
    expect(dataset).toHaveAccessibleName("Dataset");
    await userEvent.click(screen.getByTestId("individual-extraction-submit"));
    expect(screen.getByText("Select a dataset", { selector: "[id$='-error']" })).toHaveAttribute(
      "id",
      "individual-extraction-dataset-error",
    );
    expect(dataset).toHaveClass("select--error");
    expect(runPipeline).not.toHaveBeenCalled();

    // The error goes as soon as a dataset is chosen.
    await userEvent.selectOptions(dataset, "ds-b");
    expect(
      screen.queryByText("Select a dataset", { selector: "[id$='-error']" }),
    ).not.toBeInTheDocument();
    expect(dataset).not.toHaveClass("select--error");

    await userEvent.click(screen.getByTestId("individual-extraction-submit"));
    await waitFor(() => expect(runPipeline).toHaveBeenCalledTimes(1));
    expect(runPipeline.mock.calls[0][1]).toMatchObject({
      dataset_id: "ds-b",
      ontology_id: "Taxonomy-1",
    });
  });
});
