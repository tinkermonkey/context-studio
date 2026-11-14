import type { ComponentType } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { pipelineService, type PipelineConfiguration } from "@/api/services/pipeline";
import { ontologyService } from "@/api/services/ontology";
import { createDataset } from "@/api/services/__tests__/fixtures/ontology.fixtures";
import type { components } from "@/api/types";
import { RUN_WIZARDS } from "../index";

const navigate = vi.hoisted(() => vi.fn());
vi.mock("@tanstack/react-router", async () => ({
  ...(await vi.importActual("@tanstack/react-router")),
  useNavigate: () => navigate,
}));

// Picking an entity is the picker's own concern: here one click picks a fixed one.
vi.mock("../../EntitySearchPicker", () => ({
  EntitySearchPicker: ({
    entityType,
    onSelect,
    "data-testid": testId,
  }: {
    entityType: string;
    onSelect?: (entity: { id: string; label: string }) => void;
    "data-testid"?: string;
  }) => (
    <button
      type="button"
      data-testid={testId}
      onClick={() => onSelect?.({ id: `${entityType}-1`, label: `${entityType} one` })}
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
      await userEvent.click(screen.getByTestId("schema-grounding-source-dbpedia"));
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

      await waitFor(() => expect(runPipeline).toHaveBeenCalledTimes(1));
      const [runType, body] = runPipeline.mock.calls[0];
      expect(runType).toBe(type);
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

  it("grounding sends what the server reads: one node, its label and type, and source names", async () => {
    renderWizard("schema_node_grounding");
    await waitFor(() =>
      expect(screen.getByTestId("schema-grounding-configuration")).toHaveValue("base-main"),
    );
    await userEvent.click(screen.getByRole("radio", { name: "Property Definition" }));
    await FILL.schema_node_grounding.fill();
    await userEvent.click(screen.getByTestId("schema-grounding-submit"));

    await waitFor(() => expect(runPipeline).toHaveBeenCalledTimes(1));
    expect(runPipeline.mock.calls[0][1]).toEqual({
      implementation_id: "base",
      configuration_ref: "base-main",
      // Started in the background: the run drawer follows it.
      async: true,
      node_id: "PropertyDefinition-1",
      node_label: "PropertyDefinition one",
      node_type: "PropertyDefinition",
      // The adapter's own, case-sensitive source names.
      sources: ["DBpedia", "schema.org"],
    });
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
