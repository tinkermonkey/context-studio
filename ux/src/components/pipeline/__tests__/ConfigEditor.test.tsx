import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigEditor } from "../ConfigEditor";
import type { PipelineConfiguration as Config } from "@/api/services/pipeline";

const mutations = vi.hoisted(() => ({
  create: vi.fn(),
  update: vi.fn(),
}));

vi.mock("@/api/hooks/pipeline/useConfigurationMutations", () => ({
  useCreateConfiguration: () => ({ mutateAsync: mutations.create, isPending: false }),
  useUpdateConfiguration: () => ({ mutateAsync: mutations.update, isPending: false }),
  useDeleteConfiguration: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("@/components/ui/Toast", () => ({ useToasts: () => ({ toast: vi.fn() }) }));

// The providers the server reports, and the models of the registered configurations.
vi.mock("@/api/hooks/admin/useHealth", () => ({
  useHealth: () => ({ data: { llm_providers_available: ["anthropic", "openrouter"] } }),
}));
// The ranges the server's schema states.
vi.mock("@/api/hooks/pipeline/useParameterBounds", () => ({
  useParameterBounds: () => ({
    temperature: { minimum: 0, maximum: 2 },
    max_tokens: { minimum: 64, maximum: 20000 },
    top_p: { minimum: 0, maximum: 1 },
  }),
}));
vi.mock("@/api/hooks/pipeline/useRegisteredModels", () => ({
  useRegisteredModels: () => [
    { provider: "anthropic", model: "claude-small" },
    { provider: "openrouter", model: "google/gemini-3-flash-preview" },
    { provider: "openrouter", model: "vendor/other-model" },
  ],
}));

const STAGE = {
  key: "disambiguation",
  label: "Disambiguation",
  description: "Splits terms into senses.",
  placeholders: { terms: "The labels" },
  system: "Only split homonyms.",
  user: "Terms: {terms}",
  is_default: false,
};

function makeConfig(overrides: Partial<Config> = {}): Config {
  return {
    id: "cfg-1",
    config_ref: "cfg_copy",
    pipeline_type: "schema_extraction",
    implementation_id: "default",
    name: "Copy",
    description: null,
    provider: "openrouter",
    model: "google/gemini-3-flash-preview",
    stage_prompts: [STAGE],
    parameters: { temperature: 0, max_tokens: 2000, top_p: 0.9 },
    // What it sets itself; `parameters` are the values in effect.
    parameter_settings: { temperature: 0, max_tokens: 2000, top_p: 0.9 },
    enabled: true,
    is_default: false,
    version: 1,
    is_system: false,
    created_at: null,
    updated_at: null,
    ...overrides,
  };
}

const onCreated = vi.fn();

function renderEditor(
  config: Config | null,
  mode: "view" | "edit" | "create" = "view",
  template?: Config,
) {
  return render(
    <ConfigEditor
      pipelineType="schema_extraction"
      implId="default"
      config={config}
      template={template}
      mode={mode}
      onEnterEdit={vi.fn()}
      onDone={vi.fn()}
      onCreated={onCreated}
      onDuplicate={vi.fn()}
      onCancel={vi.fn()}
      onDeleted={vi.fn()}
    />,
  );
}

describe("ConfigEditor stage prompts", () => {
  beforeEach(() => {
    mutations.create.mockReset().mockResolvedValue(makeConfig({ id: "cfg-2" }));
    mutations.update.mockReset();
  });

  it("shows the stage prompts read-only outside edit mode", () => {
    renderEditor(makeConfig());
    expect(screen.getByTestId("stage-prompts-section")).toBeInTheDocument();
    expect(screen.queryByTestId("stage-prompt-system-disambiguation")).not.toBeInTheDocument();
  });

  it("hides the section for implementations without stages", () => {
    renderEditor(makeConfig({ stage_prompts: null }));
    expect(screen.queryByTestId("stage-prompts-section")).not.toBeInTheDocument();
  });

  it("offers Duplicate on a system configuration and copies its prompts", async () => {
    renderEditor(makeConfig({ is_system: true }));
    await userEvent.click(screen.getByRole("button", { name: "Configuration actions" }));
    await userEvent.click(await screen.findByText("Duplicate"));

    expect(mutations.create).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Copy (copy)",
        stage_prompts: { disambiguation: { system: STAGE.system, user: STAGE.user } },
      }),
    );
  });

  it("sends the current stage prompts when another field is saved", async () => {
    mutations.update.mockResolvedValue(makeConfig({ name: "Renamed", version: 2 }));
    renderEditor(makeConfig(), "edit");

    const name = screen.getByTestId("config-name-input");
    await userEvent.clear(name);
    await userEvent.type(name, "Renamed");
    await userEvent.tab();

    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(1));
    expect(mutations.update.mock.calls[0][0].body.stage_prompts).toEqual({
      disambiguation: { system: STAGE.system, user: STAGE.user },
    });
  });

  it("shows what is typed in the name and saves it on blur only when it changed", async () => {
    mutations.update.mockResolvedValue(makeConfig({ name: "Copy two", version: 2 }));
    renderEditor(makeConfig(), "edit");

    const name = screen.getByTestId("config-name-input");
    await userEvent.click(name);
    await userEvent.tab();
    expect(mutations.update).not.toHaveBeenCalled();

    await userEvent.type(name, " two");
    expect(name).toHaveValue("Copy two");
    await userEvent.tab();
    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(1));
    expect(mutations.update.mock.calls[0][0].body.name).toBe("Copy two");
  });

  it("builds each save on the previous save's result", async () => {
    const afterPromptSave = makeConfig({
      version: 2,
      stage_prompts: [{ ...STAGE, system: "Edited." }],
    });
    mutations.update.mockResolvedValueOnce(afterPromptSave).mockResolvedValueOnce(afterPromptSave);
    renderEditor(makeConfig(), "edit");

    const system = screen.getByTestId("stage-prompt-system-disambiguation");
    await userEvent.clear(system);
    await userEvent.type(system, "Edited.");
    // Blur the prompt straight into the name field, change it and blur that too: two saves
    await userEvent.type(screen.getByTestId("config-name-input"), "!");
    await userEvent.tab();

    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(2));
    expect(mutations.update.mock.calls[1][0].body.stage_prompts).toEqual({
      disambiguation: { system: "Edited.", user: STAGE.user },
    });
  });
});

const optionValues = (el: HTMLElement) =>
  within(el)
    .getAllByRole("option", { hidden: true })
    .map((o) => o.getAttribute("value"));

describe("ConfigEditor provider and model", () => {
  beforeEach(() => {
    mutations.create.mockReset().mockResolvedValue(makeConfig({ id: "cfg-2" }));
    mutations.update
      .mockReset()
      .mockImplementation(async ({ body }) =>
        makeConfig({ provider: body.provider, model: body.model }),
      );
    onCreated.mockReset();
  });

  it("offers the server's providers and suggests the registered models of the chosen one", () => {
    renderEditor(makeConfig(), "edit");

    const provider = screen.getByTestId("config-provider-select");
    expect(provider).toHaveAccessibleName("Provider");
    expect(provider).toHaveValue("openrouter");
    expect(optionValues(provider)).toEqual(["anthropic", "openrouter"]);

    const model = screen.getByTestId("config-model-input");
    expect(model).toHaveValue("google/gemini-3-flash-preview");
    expect(model).toHaveAttribute("list", "config-model-options");
    expect(optionValues(screen.getByTestId("config-model-options"))).toEqual([
      "google/gemini-3-flash-preview",
      "vendor/other-model",
    ]);
  });

  it("keeps a provider the server no longer reports selectable", () => {
    renderEditor(makeConfig({ provider: "retired" }), "edit");
    expect(optionValues(screen.getByTestId("config-provider-select"))).toEqual([
      "anthropic",
      "openrouter",
      "retired",
    ]);
  });

  it("saves any typed model on blur, and a changed provider without touching the model", async () => {
    renderEditor(makeConfig(), "edit");

    const model = screen.getByTestId("config-model-input");
    await userEvent.clear(model);
    await userEvent.type(model, "vendor/brand-new-model");
    await userEvent.tab();
    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(1));
    expect(mutations.update.mock.calls[0][0].body).toMatchObject({
      provider: "openrouter",
      model: "vendor/brand-new-model",
    });

    await userEvent.selectOptions(screen.getByTestId("config-provider-select"), "anthropic");
    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(2));
    expect(mutations.update.mock.calls[1][0].body).toMatchObject({
      provider: "anthropic",
      model: "vendor/brand-new-model",
    });
  });

  it("does not save an empty model, and clears the error as soon as one is typed", async () => {
    renderEditor(makeConfig(), "edit");

    const model = screen.getByTestId("config-model-input");
    await userEvent.clear(model);
    await userEvent.tab();
    expect(screen.getByText("A model is required")).toHaveAttribute("id", "config-model-error");
    expect(model).toHaveAttribute("aria-invalid", "true");
    expect(model).toHaveClass("text-input--error");
    expect(mutations.update).not.toHaveBeenCalled();

    await userEvent.type(model, "c");
    expect(screen.queryByText("A model is required")).not.toBeInTheDocument();
    expect(model).not.toHaveClass("text-input--error");
  });

  it("starts a new configuration from the template and creates it with the typed model", async () => {
    const template = makeConfig({
      provider: "anthropic",
      model: "claude-small",
      parameters: { temperature: 0, max_tokens: 16000, top_p: 0.8 },
    });
    renderEditor(null, "create", template);

    expect(screen.getByTestId("config-provider-select")).toHaveValue("anthropic");
    const model = screen.getByTestId("config-model-input");
    expect(model).toHaveValue("claude-small");
    expect(screen.getByTestId("config-create-btn")).toBeDisabled();

    await userEvent.type(screen.getByTestId("config-name-input"), "Mine");
    await userEvent.clear(model);
    expect(screen.getByTestId("config-create-btn")).toBeDisabled();
    await userEvent.type(model, "claude-other");
    await userEvent.click(screen.getByTestId("config-create-btn"));

    await waitFor(() => expect(mutations.create).toHaveBeenCalledTimes(1));
    expect(mutations.create.mock.calls[0][0]).toMatchObject({
      name: "Mine",
      provider: "anthropic",
      model: "claude-other",
      // Nothing was typed: the temperature and output limit stay the default configuration's.
      parameters: { temperature: null, max_tokens: null, top_p: 0.8 },
    });
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: "cfg-2" }));
  });

  it("marks the implementation's default configuration", () => {
    renderEditor(makeConfig({ is_default: true }));
    expect(screen.getByText("default")).toHaveClass("chip--cyan");
  });
});

describe("ConfigEditor parameters", () => {
  // A user configuration that sets its own temperature and inherits the output limit.
  const inheriting = () =>
    makeConfig({
      parameters: { temperature: 0.3, max_tokens: 16000, top_p: 0.9 },
      parameter_settings: { temperature: 0.3, max_tokens: null, top_p: 0.9 },
    });
  const defaultConfig = makeConfig({
    id: "cfg-default",
    is_system: true,
    is_default: true,
    parameters: { temperature: 0, max_tokens: 16000, top_p: 0.9 },
  });

  beforeEach(() => {
    mutations.create.mockReset().mockResolvedValue(makeConfig({ id: "cfg-2" }));
    // The server answers with what was sent as the settings.
    mutations.update
      .mockReset()
      .mockImplementation(async ({ body }) =>
        makeConfig({ name: body.name, parameter_settings: body.parameters, version: 2 }),
      );
    onCreated.mockReset();
  });

  it("shows an unset output limit as inherited, with the value in effect", () => {
    renderEditor(inheriting(), "edit", defaultConfig);

    const temperature = screen.getByTestId("config-temperature-input");
    expect(temperature).toHaveValue(0.3);
    expect(screen.getByTestId("config-temperature")).not.toHaveTextContent("inherited");

    const maxTokens = screen.getByTestId("config-max-tokens-input");
    expect(maxTokens).toHaveValue(null);
    expect(maxTokens).toHaveAttribute("placeholder", "16000");
    expect(screen.getByTestId("config-max-tokens")).toHaveTextContent("inherited");
    expect(screen.getByText("Max tokens").closest("label")).toHaveAttribute(
      "for",
      "config-max-tokens",
    );
    // The API's range, from its schema.
    expect(maxTokens).toHaveAttribute("min", "64");
    expect(maxTokens).toHaveAttribute("max", "20000");
  });

  it("keeps an inherited value inherited when another field is saved", async () => {
    renderEditor(inheriting(), "edit", defaultConfig);

    await userEvent.type(screen.getByTestId("config-name-input"), "!");
    await userEvent.tab();
    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(1));
    // The settings go back as they are: not the 16000 in effect.
    expect(mutations.update.mock.calls[0][0].body.parameters).toEqual({
      temperature: 0.3,
      max_tokens: null,
      top_p: 0.9,
    });
  });

  it("saves a typed output limit, and unsets it again when the field is emptied", async () => {
    renderEditor(inheriting(), "edit", defaultConfig);

    const maxTokens = screen.getByTestId("config-max-tokens-input");
    await userEvent.type(maxTokens, "20000");
    expect(screen.getByTestId("config-max-tokens")).not.toHaveTextContent("inherited");
    await userEvent.tab();
    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(1));
    expect(mutations.update.mock.calls[0][0].body.parameters).toEqual({
      temperature: 0.3,
      max_tokens: 20000,
      top_p: 0.9,
    });

    await userEvent.clear(maxTokens);
    expect(screen.getByTestId("config-max-tokens")).toHaveTextContent("inherited");
    await userEvent.tab();
    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(2));
    expect(mutations.update.mock.calls[1][0].body.parameters).toEqual({
      temperature: 0.3,
      max_tokens: null,
      top_p: 0.9,
    });
  });

  it("keeps a saved output limit when a slider is moved afterwards", async () => {
    // The configuration prop still holds the old values for both saves: nothing refetched yet.
    renderEditor(
      makeConfig({
        parameters: { temperature: 0.4, max_tokens: 800, top_p: 0.9 },
        parameter_settings: { temperature: 0.4, max_tokens: 800, top_p: 0.9 },
      }),
      "edit",
    );

    const maxTokens = screen.getByTestId("config-max-tokens-input");
    await userEvent.clear(maxTokens);
    await userEvent.type(maxTokens, "16000");
    await userEvent.tab();
    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(1));
    expect(mutations.update.mock.calls[0][0].body.parameters).toEqual({
      temperature: 0.4,
      max_tokens: 16000,
      top_p: 0.9,
    });

    fireEvent.change(screen.getByRole("slider", { name: "Top-p" }), { target: { value: "0.5" } });
    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(2));
    expect(mutations.update.mock.calls[1][0].body.parameters).toEqual({
      temperature: 0.4,
      max_tokens: 16000,
      top_p: 0.5,
    });
    expect(maxTokens).toHaveValue(16000);
  });

  it("refuses a value outside the API's range until it is corrected", async () => {
    renderEditor(makeConfig(), "edit");

    const maxTokens = screen.getByTestId("config-max-tokens-input");
    await userEvent.clear(maxTokens);
    await userEvent.type(maxTokens, "20001");
    await userEvent.tab();
    expect(screen.getByText("A whole number from 64 to 20000")).toHaveAttribute(
      "id",
      "config-max-tokens-error",
    );
    expect(maxTokens).toHaveAttribute("aria-invalid", "true");
    expect(maxTokens).toHaveClass("number-input--error");
    expect(mutations.update).not.toHaveBeenCalled();

    // The error goes with the first keystroke, before the field is left.
    await userEvent.type(maxTokens, "{Backspace}");
    expect(screen.queryByText("A whole number from 64 to 20000")).not.toBeInTheDocument();
    expect(maxTokens).not.toHaveClass("number-input--error");

    const temperature = screen.getByTestId("config-temperature-input");
    await userEvent.clear(temperature);
    await userEvent.type(temperature, "2.5");
    await userEvent.tab();
    expect(screen.getByText("A number from 0 to 2")).toHaveAttribute(
      "id",
      "config-temperature-error",
    );
  });

  it("creates nothing while a parameter holds a value the API would refuse", async () => {
    renderEditor(null, "create", defaultConfig);
    await userEvent.type(screen.getByTestId("config-name-input"), "Mine");
    expect(screen.getByTestId("config-create-btn")).toBeEnabled();

    const maxTokens = screen.getByTestId("config-max-tokens-input");
    expect(maxTokens).toHaveAttribute("placeholder", "16000");
    await userEvent.type(maxTokens, "5");
    expect(screen.getByTestId("config-create-btn")).toBeDisabled();
    await userEvent.type(maxTokens, "000");
    expect(screen.getByTestId("config-create-btn")).toBeEnabled();

    await userEvent.click(screen.getByTestId("config-create-btn"));
    await waitFor(() => expect(mutations.create).toHaveBeenCalledTimes(1));
    expect(mutations.create.mock.calls[0][0].parameters).toEqual({
      temperature: null,
      max_tokens: 5000,
      top_p: 0.9,
    });
  });

  it("marks an inherited value in the read-only view", () => {
    renderEditor(inheriting());
    expect(screen.queryByTestId("config-max-tokens-input")).not.toBeInTheDocument();
    expect(screen.getByTestId("param-slider-max-tokens")).toHaveTextContent("16000 · inherited");
    expect(screen.getByTestId("param-slider-temperature")).toHaveTextContent("0.30");
    expect(screen.getByTestId("param-slider-temperature")).not.toHaveTextContent("inherited");
  });

  it("shows no parameters for a pipeline whose configurations carry none", async () => {
    const bare = makeConfig({
      provider: null,
      model: null,
      parameters: null,
      parameter_settings: null,
      stage_prompts: null,
    });
    const { unmount } = renderEditor(bare);
    expect(screen.queryByTestId("config-parameters")).not.toBeInTheDocument();
    expect(screen.queryByText("Max tokens")).not.toBeInTheDocument();
    unmount();

    // A new configuration of such a pipeline sends no parameters either.
    renderEditor(null, "create", bare);
    expect(screen.queryByTestId("config-parameters")).not.toBeInTheDocument();
    await userEvent.type(screen.getByTestId("config-name-input"), "Mine");
    await userEvent.selectOptions(screen.getByTestId("config-provider-select"), "anthropic");
    await userEvent.type(screen.getByTestId("config-model-input"), "claude-small");
    await userEvent.click(screen.getByTestId("config-create-btn"));
    await waitFor(() => expect(mutations.create).toHaveBeenCalledTimes(1));
    expect(mutations.create.mock.calls[0][0].parameters).toBeUndefined();
  });
});
