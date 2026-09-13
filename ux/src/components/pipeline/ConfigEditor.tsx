import { useState, useEffect } from "react";
import {
  Panel,
  Field,
  TextInput,
  TextArea,
  Select,
  Chip,
  VersionPill,
  Icon,
  Button,
  SegmentedControl,
  FormCallout,
  ConfirmDialog,
  RowMenu,
} from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import {
  useCreateConfiguration,
  useUpdateConfiguration,
  useDeleteConfiguration,
} from "@/api/hooks/pipeline/useConfigurationMutations";
import { ParamSlider } from "./ParamSlider";
import { VariableChips } from "./VariableChips";
import type { components } from "@/api/types";
import "./ConfigEditor.css";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type PipelineConfigurationParameters = components["schemas"]["PipelineConfigurationParameters"];

const PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
];

const MODELS: Record<string, string[]> = {
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
  anthropic: ["claude-3-5-sonnet", "claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
};

const DEFAULT_PARAMS: PipelineConfigurationParameters = {
  temperature: 0.4,
  max_tokens: 800,
  top_p: 0.9,
};

interface DraftConfig {
  name: string;
  description: string;
  provider: string;
  model: string;
  system_prompt: string;
  user_prompt_template: string;
  parameters: PipelineConfigurationParameters;
  enabled: boolean;
}

function makeDraft(config: PipelineConfigurationResponse | null): DraftConfig {
  if (!config) {
    return {
      name: "",
      description: "",
      provider: "openai",
      model: "gpt-4o",
      system_prompt: "",
      user_prompt_template: "",
      parameters: { ...DEFAULT_PARAMS },
      enabled: true,
    };
  }
  return {
    name: config.name ?? "",
    description: config.description ?? "",
    provider: config.provider ?? "openai",
    model: config.model ?? MODELS[config.provider ?? "openai"]?.[0] ?? "",
    system_prompt: config.system_prompt ?? "",
    user_prompt_template: config.user_prompt_template ?? "",
    parameters: config.parameters ?? { ...DEFAULT_PARAMS },
    enabled: config.enabled ?? true,
  };
}

interface ConfigEditorProps {
  pipelineType: string;
  implId: string;
  config: PipelineConfigurationResponse | null;
  mode: "view" | "edit" | "create";
  onEnterEdit: () => void;
  onDone: () => void;
  onCreated: (id: string) => void;
  onDuplicate?: (id: string) => void;
  onCancel: () => void;
  onDeleted: () => void;
}

export function ConfigEditor({
  pipelineType,
  implId,
  config,
  mode,
  onEnterEdit,
  onDone,
  onCreated,
  onDuplicate,
  onCancel,
  onDeleted,
}: ConfigEditorProps) {
  const { toast } = useToasts();
  const isCreate = mode === "create";
  const isEdit = mode === "edit";
  const active = isCreate || isEdit;

  const [draft, setDraft] = useState<DraftConfig>(() => makeDraft(config));
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const createMutation = useCreateConfiguration(pipelineType, implId);
  const updateMutation = useUpdateConfiguration(pipelineType, implId);
  const deleteMutation = useDeleteConfiguration(pipelineType, implId);

  useEffect(() => {
    setDraft(makeDraft(isCreate ? null : config));
  }, [config?.id, mode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Current display values: draft for create, config for view/edit
  const displayName = isCreate ? draft.name : (config?.name ?? "");
  const displayDesc = isCreate ? draft.description : (config?.description ?? "");
  const displayProvider = isCreate ? draft.provider : (config?.provider ?? "openai");
  const displayModel = isCreate ? draft.model : (config?.model ?? "");
  const displaySystemPrompt = isCreate ? draft.system_prompt : (config?.system_prompt ?? "");
  const displayUserPrompt = isCreate
    ? draft.user_prompt_template
    : (config?.user_prompt_template ?? "");
  const displayEnabled = isCreate ? draft.enabled : (config?.enabled ?? true);
  const displayParams = isCreate ? draft.parameters : (config?.parameters ?? DEFAULT_PARAMS);

  const setField = (k: keyof DraftConfig, v: unknown) => setDraft((d) => ({ ...d, [k]: v }));

  const setParam = (k: keyof PipelineConfigurationParameters, v: number) =>
    setDraft((d) => ({ ...d, parameters: { ...d.parameters, [k]: v } }));

  const handleProviderChange = (v: string) => {
    const firstModel = MODELS[v]?.[0] ?? "";
    setField("provider", v);
    setField("model", firstModel);
    if (!isCreate) void handleSaveField({ provider: v, model: firstModel });
  };

  const handleSaveField = async (patch: Partial<DraftConfig>) => {
    if (isCreate || !config || config.is_system) return;
    const current = makeDraft(config);
    const updated = { ...current, ...patch };
    try {
      await updateMutation.mutateAsync({
        configId: config.id,
        body: {
          name: updated.name,
          description: updated.description || undefined,
          provider: updated.provider,
          model: updated.model,
          system_prompt: updated.system_prompt || undefined,
          user_prompt_template: updated.user_prompt_template,
          parameters: updated.parameters,
          enabled: updated.enabled,
        },
      });
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to save");
    }
  };

  const handleCreate = async () => {
    try {
      const result = await createMutation.mutateAsync({
        name: draft.name,
        description: draft.description || undefined,
        provider: draft.provider,
        model: draft.model,
        system_prompt: draft.system_prompt || undefined,
        user_prompt_template: draft.user_prompt_template,
        parameters: draft.parameters,
        enabled: draft.enabled,
      });
      onCreated(result.id);
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to create configuration");
    }
  };

  const handleDelete = async () => {
    if (!config || config.is_system) return;
    try {
      await deleteMutation.mutateAsync(config.id);
      setShowDeleteConfirm(false);
      onDeleted();
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to delete configuration");
    }
  };

  const handleDuplicate = async () => {
    if (!config || config.is_system) return;
    try {
      const result = await createMutation.mutateAsync({
        name: `${config.name} (copy)`,
        description: config.description || undefined,
        provider: config.provider ?? "openai",
        model: config.model ?? "",
        system_prompt: config.system_prompt || undefined,
        user_prompt_template: config.user_prompt_template ?? "",
        parameters: config.parameters ?? { ...DEFAULT_PARAMS },
        enabled: config.enabled,
      });
      onDuplicate?.(result.id);
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to duplicate configuration");
    }
  };

  const insertVar = (v: string) => {
    const t = displayUserPrompt;
    const next = t + (t.endsWith(" ") || t === "" ? "" : " ") + `{{${v}}}`;
    if (isCreate) setField("user_prompt_template", next);
    else void handleSaveField({ user_prompt_template: next });
  };

  const isSystemConfig = !isCreate && (config?.is_system ?? false);
  const validNew = isCreate && draft.name.trim() !== "" && draft.user_prompt_template.trim() !== "";
  const modelOptions = MODELS[displayProvider] ?? [];

  const rowMenuActions = isSystemConfig
    ? []
    : [
        { id: "edit", label: "Edit", icon: "edit" as const },
        { id: "duplicate", label: "Duplicate", icon: "copy" as const },
        { type: "separator" as const },
        { id: "delete", label: "Delete…", icon: "trash" as const, danger: true },
      ];

  const headerActions = isCreate ? null : isEdit ? (
    <Button variant="primary" size="sm" onClick={onDone} data-testid="config-editor-done-btn">
      <Icon name="check" size={13} /> Done
    </Button>
  ) : (
    <div className="ce-header-actions">
      {!isSystemConfig && (
        <RowMenu
          actions={rowMenuActions}
          onAction={(actionId) => {
            if (actionId === "edit") onEnterEdit();
            if (actionId === "duplicate") void handleDuplicate();
            if (actionId === "delete") setShowDeleteConfirm(true);
          }}
          triggerLabel="Configuration actions"
          data-testid="config-editor-menu-btn"
        />
      )}
    </div>
  );

  return (
    <>
      <Panel
        data-testid="config-editor"
        title={isCreate ? "New configuration" : (config?.name ?? "")}
        subtitle={isCreate ? `Under ${pipelineType}` : undefined}
        headerAction={
          <div className="ce-header-right">
            {!isCreate && (
              <>
                {displayEnabled ? (
                  <Chip variant="emerald">enabled</Chip>
                ) : (
                  <Chip variant="neutral">disabled</Chip>
                )}
                <VersionPill>{config?.version ?? 1}</VersionPill>
              </>
            )}
            {headerActions}
          </div>
        }
      >
        <div className="cfg-editor">
          {isEdit && !isSystemConfig && (
            <FormCallout variant="info" icon="info">
              Editing — changes save automatically on blur.
            </FormCallout>
          )}
          {isSystemConfig && (
            <FormCallout variant="info" icon="info">
              System configuration — read-only.
            </FormCallout>
          )}

          {/* Identity */}
          <section>
            <div className="cfg-section-title">Identity</div>
            <div className="cfg-identity-fields">
              <Field label="Name" required={isCreate}>
                {active && !isSystemConfig ? (
                  <TextInput
                    value={isCreate ? draft.name : (config?.name ?? "")}
                    onChange={(e) => setField("name", e.target.value)}
                    onBlur={(e) => {
                      void handleSaveField({ name: e.target.value });
                    }}
                    placeholder="Configuration name"
                    autoFocus={isCreate}
                    data-testid="config-name-input"
                  />
                ) : (
                  <span className="cfg-view-text">{displayName || "—"}</span>
                )}
              </Field>
              <Field label="Description">
                {active && !isSystemConfig ? (
                  <TextArea
                    value={isCreate ? draft.description : (config?.description ?? "")}
                    onChange={(e) => setField("description", e.target.value)}
                    onBlur={(e) => {
                      void handleSaveField({ description: e.target.value });
                    }}
                    placeholder="Optional description"
                    rows={2}
                    data-testid="config-description-input"
                  />
                ) : (
                  <span className="cfg-view-text">{displayDesc || "—"}</span>
                )}
              </Field>
              <div className="cfg-editor__grid2">
                <Field label="Provider">
                  {active && !isSystemConfig ? (
                    <Select
                      value={displayProvider}
                      onChange={handleProviderChange}
                      data-testid="config-provider-select"
                    >
                      {PROVIDERS.map((p) => (
                        <Select.Item key={p.value} value={p.value}>
                          {p.label}
                        </Select.Item>
                      ))}
                    </Select>
                  ) : (
                    <span className="cfg-mono-text">{displayProvider || "—"}</span>
                  )}
                </Field>
                <Field label="Model">
                  {active && !isSystemConfig ? (
                    <Select
                      value={displayModel}
                      onChange={(v) => {
                        setField("model", v);
                        void handleSaveField({ model: v });
                      }}
                      data-testid="config-model-select"
                    >
                      {modelOptions.map((m) => (
                        <Select.Item key={m} value={m}>
                          {m}
                        </Select.Item>
                      ))}
                    </Select>
                  ) : (
                    <span className="cfg-mono-text">{displayModel || "—"}</span>
                  )}
                </Field>
              </div>
              <Field label="Status">
                {active && !isSystemConfig ? (
                  <SegmentedControl
                    value={displayEnabled ? "on" : "off"}
                    onChange={(v) => {
                      const enabled = v === "on";
                      setField("enabled", enabled);
                      void handleSaveField({ enabled });
                    }}
                    options={[
                      { value: "on", label: "Enabled" },
                      { value: "off", label: "Disabled" },
                    ]}
                    data-testid="config-status-control"
                  />
                ) : displayEnabled ? (
                  <Chip variant="emerald">enabled</Chip>
                ) : (
                  <Chip variant="neutral">disabled</Chip>
                )}
              </Field>
            </div>
          </section>

          {/* Prompts */}
          <section>
            <div className="cfg-section-title">Prompts</div>
            <div className="cfg-prompts-fields">
              <Field label="System prompt">
                {active && !isSystemConfig ? (
                  <TextArea
                    className="cfg-prompt"
                    mono
                    value={isCreate ? draft.system_prompt : (config?.system_prompt ?? "")}
                    rows={3}
                    onChange={(e) => setField("system_prompt", e.target.value)}
                    onBlur={(e) => {
                      void handleSaveField({ system_prompt: e.target.value });
                    }}
                    data-testid="config-system-prompt-input"
                  />
                ) : (
                  <pre className="cfg-prompt-preview">{displaySystemPrompt || "—"}</pre>
                )}
              </Field>
              <Field label="User prompt template" hint="Jinja2 · {{variables}}">
                {active && !isSystemConfig ? (
                  <TextArea
                    className="cfg-prompt"
                    mono
                    value={
                      isCreate ? draft.user_prompt_template : (config?.user_prompt_template ?? "")
                    }
                    rows={4}
                    onChange={(e) => setField("user_prompt_template", e.target.value)}
                    onBlur={(e) => {
                      void handleSaveField({ user_prompt_template: e.target.value });
                    }}
                    data-testid="config-user-prompt-input"
                  />
                ) : (
                  <pre className="cfg-prompt-preview">{displayUserPrompt || "—"}</pre>
                )}
                <VariableChips
                  template={displayUserPrompt}
                  onInsert={active && !isSystemConfig ? insertVar : undefined}
                />
              </Field>
            </div>
          </section>

          {/* Parameters */}
          <section>
            <div className="cfg-section-title">Parameters</div>
            <div className="cfg-params-grid">
              <ParamSlider
                active={active && !isSystemConfig}
                label="Temperature"
                value={displayParams.temperature ?? 0.4}
                min={0}
                max={2}
                step={0.05}
                fmt={(v) => v.toFixed(2)}
                onChange={(v) => {
                  setParam("temperature", v);
                  void handleSaveField({ parameters: { ...displayParams, temperature: v } });
                }}
              />
              <ParamSlider
                active={active && !isSystemConfig}
                label="Max tokens"
                value={displayParams.max_tokens ?? 800}
                min={64}
                max={4096}
                step={32}
                fmt={(v) => Math.round(v)}
                onChange={(v) => {
                  const rounded = Math.round(v);
                  setParam("max_tokens", rounded);
                  void handleSaveField({ parameters: { ...displayParams, max_tokens: rounded } });
                }}
              />
              <ParamSlider
                active={active && !isSystemConfig}
                label="Top-p"
                value={displayParams.top_p ?? 0.9}
                min={0}
                max={1}
                step={0.01}
                fmt={(v) => v.toFixed(2)}
                onChange={(v) => {
                  setParam("top_p", v);
                  void handleSaveField({ parameters: { ...displayParams, top_p: v } });
                }}
              />
            </div>
          </section>

          {/* Create actions */}
          {isCreate && (
            <div className="cfg-create-actions">
              <Button
                variant="primary"
                onClick={() => {
                  void handleCreate();
                }}
                disabled={!validNew || createMutation.isPending}
                data-testid="config-create-btn"
              >
                <Icon name="check" size={13} />
                {createMutation.isPending ? "Creating…" : "Create configuration"}
              </Button>
              <Button variant="ghost" onClick={onCancel} data-testid="config-cancel-btn">
                Cancel
              </Button>
            </div>
          )}

          {!isCreate && (
            <div className="cfg-id-footer">
              {config?.is_system ? "system-defined" : `id: ${config?.id ?? "—"}`}
            </div>
          )}
        </div>
      </Panel>

      {showDeleteConfirm && config && (
        <ConfirmDialog
          isOpen
          onClose={() => setShowDeleteConfirm(false)}
          onConfirm={() => {
            void handleDelete();
          }}
          variant="danger"
          title={`Delete "${config.name}"?`}
          subtitle="This configuration will be removed. Pipeline runs already executed with it keep their records."
          message={
            <span className="cfg-delete-msg">
              Configuration <code>{config.config_ref}</code> will be deleted.
            </span>
          }
          confirmLabel="Delete configuration"
        />
      )}
    </>
  );
}
