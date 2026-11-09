import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfigEditor } from "../ConfigEditor";
import type { components } from "@/api/types";

type Config = components["schemas"]["PipelineConfigurationResponse"];

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
    version: 1,
    is_system: false,
    created_at: null,
    updated_at: null,
    ...overrides,
  };
}

function renderEditor(config: Config, mode: "view" | "edit" = "view") {
  return render(
    <ConfigEditor
      pipelineType="schema_extraction"
      implId="default"
      config={config}
      mode={mode}
      onEnterEdit={vi.fn()}
      onDone={vi.fn()}
      onCreated={vi.fn()}
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
    // Blur the prompt straight into the name field and blur that too: two saves
    await userEvent.click(screen.getByTestId("config-name-input"));
    await userEvent.tab();

    await waitFor(() => expect(mutations.update).toHaveBeenCalledTimes(2));
    expect(mutations.update.mock.calls[1][0].body.stage_prompts).toEqual({
      disambiguation: { system: "Edited.", user: STAGE.user },
    });
  });
});
