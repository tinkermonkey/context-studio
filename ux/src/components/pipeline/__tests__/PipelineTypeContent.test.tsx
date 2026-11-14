import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import {
  pipelineService,
  type PipelineConfiguration,
  type PipelineImplementation,
} from "@/api/services/pipeline";
import { adminService } from "@/api/services/admin";
import { PipelineTypeContent } from "../PipelineTypeContent";

const TYPE = "individual_extraction";

// The default implementation is not first and is not called "default".
const IMPLEMENTATIONS: PipelineImplementation[] = [
  {
    id: "two_step",
    pipeline_type: TYPE,
    is_default: false,
    default_configuration: "two-step-main",
    extracts_sources: false,
  },
  {
    id: "classic",
    pipeline_type: TYPE,
    is_default: true,
    default_configuration: "classic-main",
    extracts_sources: false,
  },
];

const configuration = (
  implementationId: string,
  configRef: string,
  overrides: Partial<PipelineConfiguration> = {},
): PipelineConfiguration => ({
  id: `${implementationId}:${configRef}`,
  config_ref: configRef,
  pipeline_type: TYPE,
  implementation_id: implementationId,
  name: configRef,
  provider: "anthropic",
  model: "model-a",
  parameters: { temperature: 0, max_tokens: 2000, top_p: 0.9 },
  enabled: true,
  version: 1,
  is_system: true,
  is_default: false,
  ...overrides,
});

const CONFIGURATIONS: Record<string, PipelineConfiguration[]> = {
  classic: [
    configuration("classic", "classic-alt", { is_system: false, enabled: false }),
    configuration("classic", "classic-main", { is_default: true }),
  ],
  two_step: [configuration("two_step", "two-step-main", { is_default: true, model: "model-c" })],
};

function renderContent(props: Partial<Parameters<typeof PipelineTypeContent>[0]> = {}) {
  vi.spyOn(pipelineService, "listImplementations").mockResolvedValue(IMPLEMENTATIONS);
  vi.spyOn(pipelineService, "listConfigurations").mockImplementation(
    async (_type, implId) => CONFIGURATIONS[implId],
  );
  vi.spyOn(adminService, "getHealth").mockResolvedValue({
    llm_providers_available: ["anthropic"],
  } as Awaited<ReturnType<typeof adminService.getHealth>>);
  const onSelect = vi.fn();
  render(<PipelineTypeContent pipelineType={TYPE} onSelect={onSelect} {...props} />);
  return { onSelect };
}

describe("PipelineTypeContent", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows the default implementation's configurations and marks both defaults", async () => {
    renderContent();

    const implementation = screen.getByTestId("pipeline-implementation");
    expect(implementation).toHaveAccessibleName("Implementation");
    await waitFor(() => expect(implementation).toHaveValue("classic"));
    expect(
      within(implementation)
        .getAllByRole("option")
        .map((o) => o.getAttribute("value")),
    ).toEqual(["two_step", "classic"]);
    expect(screen.getByTestId("pipeline-implementation-default")).toHaveClass("chip--cyan");

    // Every configuration is listed here, disabled ones too: this is where they are curated.
    const list = await screen.findByTestId("pipeline-cfg-list");
    expect(list).toHaveAttribute("role", "listbox");
    expect(list).toHaveAccessibleName("Configurations of classic");
    const rows = within(list).getAllByRole("option");
    expect(rows.map((r) => r.getAttribute("data-testid"))).toEqual([
      "pipeline-cfg-row-classic-alt",
      "pipeline-cfg-row-classic-main",
    ]);
    expect(within(rows[0]).queryByText("default")).not.toBeInTheDocument();
    expect(within(rows[1]).getByText("default")).toHaveClass("chip--cyan");
    expect(rows[1]).toHaveAttribute("aria-selected", "false");
    expect(screen.getByTestId("pipeline-cfg-empty-inspector")).toBeInTheDocument();
  });

  it("shows another implementation's configurations when the page names it", async () => {
    renderContent({ implementationId: "two_step", configRef: "two-step-main" });

    const implementation = screen.getByTestId("pipeline-implementation");
    await waitFor(() => expect(implementation).toHaveValue("two_step"));
    expect(screen.queryByTestId("pipeline-implementation-default")).not.toBeInTheDocument();
    const row = await screen.findByTestId("pipeline-cfg-row-two-step-main");
    expect(row).toHaveAttribute("aria-selected", "true");
    expect(row).toHaveClass("pipeline-cfg-row--active");
    // The named configuration is open in the editor.
    expect(await screen.findByTestId("config-editor")).toHaveTextContent("model-c");
    expect(pipelineService.listConfigurations).toHaveBeenCalledWith(TYPE, "two_step");
  });

  it("reports the implementation and configuration the user picks", async () => {
    const { onSelect } = renderContent();
    const implementation = screen.getByTestId("pipeline-implementation");
    await waitFor(() => expect(implementation).toHaveValue("classic"));

    await userEvent.click(await screen.findByTestId("pipeline-cfg-row-classic-main"));
    expect(onSelect).toHaveBeenLastCalledWith({ impl: "classic", config: "classic-main" });

    await userEvent.selectOptions(implementation, "two_step");
    expect(onSelect).toHaveBeenLastCalledWith({ impl: "two_step" });
  });

  it("creates a configuration under the implementation shown, starting from its default", async () => {
    const created = configuration("two_step", "mine", { id: "cfg-new", is_system: false });
    vi.spyOn(pipelineService, "createConfiguration").mockResolvedValue(created);
    const { onSelect } = renderContent({ implementationId: "two_step" });

    const add = await screen.findByTestId("pipeline-new-config-btn");
    expect(add).toHaveAccessibleName("New configuration of two_step");
    await userEvent.click(add);
    expect(screen.getByTestId("config-model-input")).toHaveValue("model-c");

    await userEvent.type(screen.getByTestId("config-name-input"), "Mine");
    await userEvent.click(screen.getByTestId("config-create-btn"));
    await waitFor(() =>
      expect(pipelineService.createConfiguration).toHaveBeenCalledWith(
        TYPE,
        "two_step",
        expect.objectContaining({ name: "Mine", provider: "anthropic", model: "model-c" }),
      ),
    );
    await waitFor(() =>
      expect(onSelect).toHaveBeenLastCalledWith({ impl: "two_step", config: "mine" }),
    );
  });

  it("offers Run only for a type that has a run wizard", async () => {
    const onRun = vi.fn();
    renderContent({ onRun });
    const run = screen.getByTestId("pipeline-run-btn");
    expect(run).toHaveAccessibleName(`Run ${TYPE}`);
    await userEvent.click(run);
    expect(onRun).toHaveBeenCalledTimes(1);
  });

  it("has no Run action without a wizard", () => {
    renderContent();
    expect(screen.queryByTestId("pipeline-run-btn")).not.toBeInTheDocument();
  });
});
