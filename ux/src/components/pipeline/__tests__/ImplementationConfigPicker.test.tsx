import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import {
  pipelineService,
  type PipelineConfiguration,
  type PipelineImplementation,
} from "@/api/services/pipeline";
import { usePipelineSelection } from "@/hooks/usePipelineSelection";
import { ImplementationConfigPicker } from "../ImplementationConfigPicker";

const TYPE = "individual_extraction";

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
  enabled: true,
  version: 1,
  is_system: true,
  is_default: false,
  ...overrides,
});

const CONFIGURATIONS: Record<string, PipelineConfiguration[]> = {
  classic: [
    configuration("classic", "classic-alt", { provider: "openrouter", model: "model-b" }),
    configuration("classic", "classic-main", { is_default: true }),
    configuration("classic", "classic-off", { enabled: false }),
  ],
  two_step: [configuration("two_step", "two-step-main", { is_default: true, model: "model-c" })],
};

function Harness({
  legend,
  disabled,
  onChange,
}: {
  legend?: string;
  disabled?: boolean;
  onChange?: () => void;
}) {
  const selection = usePipelineSelection(TYPE);
  return (
    <ImplementationConfigPicker
      selection={selection}
      idPrefix="extract"
      legend={legend}
      disabled={disabled}
      onChange={onChange}
    />
  );
}

function renderPicker(props: Parameters<typeof Harness>[0] = {}) {
  vi.spyOn(pipelineService, "listImplementations").mockResolvedValue(IMPLEMENTATIONS);
  vi.spyOn(pipelineService, "listConfigurations").mockImplementation(
    async (_type, implId) => CONFIGURATIONS[implId],
  );
  return render(<Harness {...props} />);
}

const optionValues = (select: HTMLElement) =>
  within(select)
    .getAllByRole("option")
    .map((o) => o.getAttribute("value"));

describe("ImplementationConfigPicker", () => {
  afterEach(() => vi.restoreAllMocks());

  it("is a labelled group of an Implementation and a Configuration select", async () => {
    renderPicker();
    const picker = screen.getByTestId("extract-picker");
    expect(picker.tagName).toBe("FIELDSET");
    expect(picker).toHaveClass("impl-config-picker");
    expect(picker).toHaveAccessibleName("Implementation and configuration");
    expect(screen.getByRole("group", { name: "Implementation and configuration" })).toBe(picker);

    const implementation = screen.getByTestId("extract-implementation");
    const configuration = screen.getByTestId("extract-configuration");
    expect(implementation).toHaveAccessibleName("Implementation");
    expect(configuration).toHaveAccessibleName("Configuration");
    expect(screen.getByText("Implementation").closest("label")).toHaveAttribute(
      "for",
      "extract-implementation",
    );
    expect(screen.getByText("Configuration").closest("label")).toHaveAttribute(
      "for",
      "extract-configuration",
    );
    await waitFor(() => expect(configuration).toHaveValue("classic-main"));
  });

  it("preselects the API's defaults and offers only enabled configurations", async () => {
    renderPicker();
    const implementation = screen.getByTestId("extract-implementation");
    const configuration = screen.getByTestId("extract-configuration");

    await waitFor(() => expect(implementation).toHaveValue("classic"));
    await waitFor(() => expect(configuration).toHaveValue("classic-main"));
    expect(optionValues(implementation)).toEqual(["two_step", "classic"]);
    expect(optionValues(configuration)).toEqual(["classic-alt", "classic-main"]);
    expect(screen.getByTestId("extract-configuration-model")).toHaveTextContent(
      "anthropic · model-a",
    );
  });

  it("changes the configurations offered with the implementation", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    renderPicker({ onChange });
    const implementation = screen.getByTestId("extract-implementation");
    const configuration = screen.getByTestId("extract-configuration");
    await waitFor(() => expect(configuration).toHaveValue("classic-main"));

    await user.selectOptions(configuration, "classic-alt");
    expect(configuration).toHaveValue("classic-alt");
    expect(screen.getByTestId("extract-configuration-model")).toHaveTextContent(
      "openrouter · model-b",
    );

    await user.selectOptions(implementation, "two_step");
    expect(implementation).toHaveValue("two_step");
    await waitFor(() => expect(configuration).toHaveValue("two-step-main"));
    expect(optionValues(configuration)).toEqual(["two-step-main"]);
    expect(onChange).toHaveBeenCalledTimes(2);
  });

  it("names the run in its legend and in each select's accessible name", async () => {
    renderPicker({ legend: "Schema extraction" });
    const picker = screen.getByTestId("extract-picker");
    expect(picker).toHaveAccessibleName("Schema extraction");
    expect(within(picker).getByText("Schema extraction")).toHaveClass("impl-config-picker__legend");
    expect(screen.getByTestId("extract-implementation")).toHaveAccessibleName(
      "Schema extraction: implementation",
    );
    expect(screen.getByTestId("extract-configuration")).toHaveAccessibleName(
      "Schema extraction: configuration",
    );
    await waitFor(() =>
      expect(screen.getByTestId("extract-configuration")).toHaveValue("classic-main"),
    );
  });

  it("disables both selects when disabled", async () => {
    renderPicker({ disabled: true });
    await waitFor(() =>
      expect(screen.getByTestId("extract-configuration")).toHaveValue("classic-main"),
    );
    expect(screen.getByTestId("extract-implementation")).toBeDisabled();
    expect(screen.getByTestId("extract-configuration")).toBeDisabled();
  });

  it("shows why the implementations are missing and leaves both selects empty", async () => {
    vi.spyOn(pipelineService, "listImplementations").mockRejectedValue(new Error("boom"));
    render(<Harness />);

    const error = await screen.findByText("boom");
    expect(error).toHaveAttribute("id", "extract-implementation-error");
    expect(screen.getByTestId("extract-picker")).toHaveAttribute(
      "aria-describedby",
      "extract-implementation-error",
    );
    const implementation = screen.getByTestId("extract-implementation");
    expect(implementation).toBeDisabled();
    expect(implementation).toHaveClass("select--error");
    expect(within(implementation).queryAllByRole("option")).toHaveLength(0);
    expect(screen.getByTestId("extract-configuration")).toBeDisabled();
    expect(screen.queryByTestId("extract-configuration-model")).not.toBeInTheDocument();
  });
});
