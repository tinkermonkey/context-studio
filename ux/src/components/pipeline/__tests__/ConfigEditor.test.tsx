import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
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
      parameters: { temperature: 0, max_tokens: 2000, top_p: 0.9 },
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
      parameters: { temperature: 0, max_tokens: 2000, top_p: 0.9 },
    });
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: "cfg-2" }));
  });

  it("takes an output-token limit above the old slider's range and saves it on blur", async () => {
    renderEditor(
      makeConfig({ parameters: { temperature: 0, max_tokens: 16000, top_p: 0.9 } }),
      "edit",
    );

    const maxTokens = screen.getByTestId("config-max-tokens-input");
    expect(maxTokens).toHaveValue(16000);
    expect(screen.getByText("Max tokens").closest("label")).toHaveAttribute(
      "for",
      "config-max-tokens",
    );
    await userEvent.clear(maxTokens);
    await userEvent.type(maxTokens, "20000");
    await userEvent.tab();

    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(1));
    expect(mutations.update.mock.calls[0][0].body.parameters).toEqual({
      temperature: 0,
      max_tokens: 20000,
      top_p: 0.9,
    });
  });

  it("refuses an output-token limit outside the API's range until it is corrected", async () => {
    renderEditor(makeConfig(), "edit");

    const maxTokens = screen.getByTestId("config-max-tokens-input");
    await userEvent.clear(maxTokens);
    await userEvent.type(maxTokens, "70000");
    await userEvent.tab();
    expect(screen.getByText("A whole number from 64 to 64000")).toHaveAttribute(
      "id",
      "config-max-tokens-error",
    );
    expect(maxTokens).toHaveAttribute("aria-invalid", "true");
    expect(mutations.update).not.toHaveBeenCalled();

    await userEvent.clear(maxTokens);
    expect(screen.queryByText("A whole number from 64 to 64000")).not.toBeInTheDocument();
    expect(maxTokens).not.toHaveAttribute("aria-invalid", "true");
  });

  it("shows a system configuration's limit read-only", () => {
    renderEditor(
      makeConfig({
        is_system: true,
        parameters: { temperature: 0, max_tokens: 16000, top_p: 0.9 },
      }),
    );
    expect(screen.queryByTestId("config-max-tokens-input")).not.toBeInTheDocument();
    expect(screen.getByTestId("param-slider-max-tokens")).toHaveTextContent("16000");
  });

  it("marks the implementation's default configuration", () => {
    renderEditor(makeConfig({ is_default: true }));
    expect(screen.getByText("default")).toHaveClass("chip--cyan");
  });
});
