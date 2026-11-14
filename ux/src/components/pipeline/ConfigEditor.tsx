import { useState, useEffect, useRef } from "react";
import {
  Panel,
  Field,
  TextInput,
  TextArea,
  NumberInput,
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
import { useRegisteredModels } from "@/api/hooks/pipeline/useRegisteredModels";
import { useHealth } from "@/api/hooks/admin/useHealth";
import type { PipelineConfiguration } from "@/api/services/pipeline";
import { ParamSlider } from "./ParamSlider";
import { StagePromptsSection } from "./StagePromptsSection";
import { stagePromptsBody, type StagePromptsBody } from "./stagePrompts";
import type { components } from "@/api/types";
import "./ConfigEditor.css";

type PipelineConfigurationResponse = PipelineConfiguration;
type PipelineConfigurationParameters = components["schemas"]["PipelineConfigurationParameters"];

const MODEL_REQUIRED = "A model is required";
// The API's bounds on a configuration's output-token limit (PipelineConfigurationParameters.max_tokens).
const MIN_OUTPUT_TOKENS = 64;
const MAX_OUTPUT_TOKENS = 64000;
const MAX_TOKENS_RANGE = `A whole number from ${MIN_OUTPUT_TOKENS} to ${MAX_OUTPUT_TOKENS}`;

/** The output-token limit typed into the field, or undefined when it is not one the API takes. */
function parseMaxTokens(text: string): number | undefined {
  const value = Number(text);
  const valid =
    text.trim() !== "" &&
    Number.isInteger(value) &&
    value >= MIN_OUTPUT_TOKENS &&
    value <= MAX_OUTPUT_TOKENS;
  return valid ? value : undefined;
}

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
  parameters: PipelineConfigurationParameters;
  enabled: boolean;
}

/** The editable copy of a configuration; a new one starts from `template`. */
function makeDraft(
  config: PipelineConfigurationResponse | null,
  template?: PipelineConfigurationResponse | null,
): DraftConfig {
  if (!config) {
    return {
      name: "",
      description: "",
      provider: template?.provider ?? "",
      model: template?.model ?? "",
      parameters: { ...(template?.parameters ?? DEFAULT_PARAMS) },
      enabled: true,
    };
  }
  return {
    name: config.name ?? "",
    description: config.description ?? "",
    provider: config.provider ?? "",
    model: config.model ?? "",
    parameters: config.parameters ?? { ...DEFAULT_PARAMS },
    enabled: config.enabled ?? true,
  };
}

interface ConfigEditorProps {
  pipelineType: string;
  implId: string;
  config: PipelineConfigurationResponse | null;
  /**
   * The configuration a new one starts from (provider, model, parameters):
   * the implementation's default configuration.
   */
  template?: PipelineConfigurationResponse | null;
  mode: "view" | "edit" | "create";
  onEnterEdit: () => void;
  onDone: () => void;
  onCreated: (config: PipelineConfigurationResponse) => void;
  onDuplicate?: (config: PipelineConfigurationResponse) => void;
  onCancel: () => void;
  onDeleted: () => void;
}

export function ConfigEditor({
  pipelineType,
  implId,
  config,
  template,
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

  const [draft, setDraft] = useState<DraftConfig>(() =>
    makeDraft(isCreate ? null : config, template),
  );
  const [modelError, setModelError] = useState<string>();
  const [maxTokensText, setMaxTokensText] = useState(() => String(draft.parameters.max_tokens));
  const [maxTokensError, setMaxTokensError] = useState<string>();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Providers are the server's; models are suggestions only (any id may be typed).
  const { data: health } = useHealth();
  const registeredModels = useRegisteredModels(pipelineType);

  const createMutation = useCreateConfiguration(pipelineType, implId);
  const updateMutation = useUpdateConfiguration(pipelineType, implId);
  const deleteMutation = useDeleteConfiguration(pipelineType, implId);

  useEffect(() => {
    const next = makeDraft(isCreate ? null : config, template);
    setDraft(next);
    setMaxTokensText(String(next.parameters.max_tokens));
    setModelError(undefined);
    setMaxTokensError(undefined);
  }, [config?.id, mode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Saves run one after another, each built on the previous save's result:
  // an update replaces the whole configuration, so two overlapping saves built
  // from the same stale copy would undo each other's change.
  const saveQueue = useRef<Promise<void>>(Promise.resolve());
  const latestSaved = useRef(config);
  useEffect(() => {
    if (!latestSaved.current || config?.id !== latestSaved.current.id) {
      latestSaved.current = config;
    } else if (config && config.version > latestSaved.current.version) {
      latestSaved.current = config;
    }
  }, [config]);

  // Current display values: draft for create, config for view/edit
  const displayName = isCreate ? draft.name : (config?.name ?? "");
  const displayDesc = isCreate ? draft.description : (config?.description ?? "");
  const displayProvider = isCreate ? draft.provider : (config?.provider ?? "");
  const displayModel = isCreate ? draft.model : (config?.model ?? "");
  const displayEnabled = isCreate ? draft.enabled : (config?.enabled ?? true);
  const displayParams = isCreate ? draft.parameters : (config?.parameters ?? DEFAULT_PARAMS);

  const setField = (k: keyof DraftConfig, v: unknown) => setDraft((d) => ({ ...d, [k]: v }));

  const setParam = (k: keyof PipelineConfigurationParameters, v: number) =>
    setDraft((d) => ({ ...d, parameters: { ...d.parameters, [k]: v } }));

  const handleProviderChange = (v: string) => {
    setField("provider", v);
    if (!isCreate) void handleSaveField({ provider: v });
  };

  const handleMaxTokensBlur = () => {
    const maxTokens = parseMaxTokens(maxTokensText);
    if (maxTokens === undefined) {
      setMaxTokensError(MAX_TOKENS_RANGE);
      return;
    }
    const saved = (latestSaved.current ?? config)?.parameters;
    if (isCreate || maxTokens === saved?.max_tokens) return;
    void handleSaveField({ parameters: { ...(saved ?? displayParams), max_tokens: maxTokens } });
  };

  /** Save a text field on blur, unless it still holds what was last saved. */
  const saveIfChanged = (field: "name" | "description", value: string) => {
    const saved = latestSaved.current ?? config;
    if (isCreate || !saved || value === (saved[field] ?? "")) return;
    void handleSaveField({ [field]: value });
  };

  const handleModelBlur = (value: string) => {
    const model = value.trim();
    if (!model) {
      setModelError(MODEL_REQUIRED);
      return;
    }
    setField("model", model);
    if (model !== (latestSaved.current ?? config)?.model) void handleSaveField({ model });
  };

  /** Save a change; stagePrompts replaces every stage's prompts when given. */
  const handleSaveField = (patch: Partial<DraftConfig>, stagePrompts?: StagePromptsBody) => {
    if (isCreate || !config || config.is_system) return Promise.resolve();
    saveQueue.current = saveQueue.current.then(async () => {
      const base = latestSaved.current ?? config;
      const updated = { ...makeDraft(base), ...patch };
      try {
        latestSaved.current = await updateMutation.mutateAsync({
          configId: base.id,
          body: {
            name: updated.name,
            description: updated.description || undefined,
            provider: updated.provider,
            model: updated.model,
            // Always sent: the update replaces the whole configuration
            stage_prompts: stagePrompts ?? stagePromptsBody(base.stage_prompts),
            parameters: updated.parameters,
            enabled: updated.enabled,
          },
        });
      } catch (err) {
        toast("error", err instanceof Error ? err.message : "Failed to save");
      }
    });
    return saveQueue.current;
  };

  const handleCreate = async () => {
    try {
      const result = await createMutation.mutateAsync({
        name: draft.name,
        description: draft.description || undefined,
        provider: draft.provider,
        model: draft.model.trim(),
        parameters: draft.parameters,
        enabled: draft.enabled,
      });
      onCreated(result);
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
    if (!config) return;
    try {
      const result = await createMutation.mutateAsync({
        name: `${config.name} (copy)`,
        description: config.description || undefined,
        provider: config.provider ?? "",
        model: config.model ?? "",
        stage_prompts: stagePromptsBody(config.stage_prompts),
        parameters: config.parameters ?? { ...DEFAULT_PARAMS },
        enabled: config.enabled,
      });
      onDuplicate?.(result);
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to duplicate configuration");
    }
  };

  const isSystemConfig = !isCreate && (config?.is_system ?? false);
  const validNew =
    isCreate &&
    draft.name.trim() !== "" &&
    draft.provider !== "" &&
    draft.model.trim() !== "" &&
    parseMaxTokens(maxTokensText) !== undefined;
  // The server's providers, plus this configuration's own if the server no longer lists it.
  const providerOptions = [
    ...new Set([
      ...(health?.llm_providers_available ?? []),
      ...(draft.provider ? [draft.provider] : []),
    ]),
  ];
  const ofProvider = registeredModels.filter((m) => m.provider === draft.provider);
  const modelSuggestions = [
    ...new Set((ofProvider.length ? ofProvider : registeredModels).map((m) => m.model)),
  ];

  // A system configuration is read-only: duplicate it to get an editable copy
  const rowMenuActions = isSystemConfig
    ? [{ id: "duplicate", label: "Duplicate", icon: "copy" as const }]
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
                {config?.is_default && <Chip variant="cyan">default</Chip>}
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
              System configuration — read-only. Duplicate it to edit a copy.
            </FormCallout>
          )}

          {/* Identity */}
          <section>
            <div className="cfg-section-title">Identity</div>
            <div className="cfg-identity-fields">
              <Field label="Name" required={isCreate}>
                {active && !isSystemConfig ? (
                  <TextInput
                    value={draft.name}
                    onChange={(e) => setField("name", e.target.value)}
                    onBlur={(e) => saveIfChanged("name", e.target.value)}
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
                    value={draft.description}
                    onChange={(e) => setField("description", e.target.value)}
                    onBlur={(e) => saveIfChanged("description", e.target.value)}
                    placeholder="Optional description"
                    rows={2}
                    data-testid="config-description-input"
                  />
                ) : (
                  <span className="cfg-view-text">{displayDesc || "—"}</span>
                )}
              </Field>
              <div className="cfg-editor__grid2">
                <Field label="Provider" htmlFor="config-provider" required={isCreate}>
                  {active && !isSystemConfig ? (
                    <Select
                      id="config-provider"
                      value={draft.provider}
                      onChange={handleProviderChange}
                      placeholder="Choose a provider"
                      ariaLabel="Provider"
                      data-testid="config-provider-select"
                    >
                      {providerOptions.map((p) => (
                        <Select.Item key={p} value={p}>
                          {p}
                        </Select.Item>
                      ))}
                    </Select>
                  ) : (
                    <span className="cfg-mono-text">{displayProvider || "—"}</span>
                  )}
                </Field>
                <Field
                  label="Model"
                  htmlFor="config-model"
                  required={isCreate}
                  error={modelError}
                  errorId="config-model-error"
                >
                  {active && !isSystemConfig ? (
                    <>
                      <TextInput
                        id="config-model"
                        mono
                        list="config-model-options"
                        value={draft.model}
                        onChange={(e) => {
                          setField("model", e.target.value);
                          setModelError(undefined);
                        }}
                        onBlur={(e) => {
                          if (!isCreate) handleModelBlur(e.target.value);
                        }}
                        placeholder="Model id"
                        error={!!modelError}
                        aria-invalid={!!modelError}
                        aria-describedby={modelError ? "config-model-error" : undefined}
                        data-testid="config-model-input"
                      />
                      <datalist id="config-model-options" data-testid="config-model-options">
                        {modelSuggestions.map((m) => (
                          <option key={m} value={m} />
                        ))}
                      </datalist>
                    </>
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

          {!isCreate && config?.stage_prompts && (
            <StagePromptsSection
              stages={config.stage_prompts}
              editable={isEdit && !isSystemConfig}
              onSave={(body) => {
                void handleSaveField({}, body);
              }}
            />
          )}

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
              {active && !isSystemConfig ? (
                // A limit runs to tens of thousands: typed, not dragged.
                <Field
                  label="Max tokens"
                  htmlFor="config-max-tokens"
                  error={maxTokensError}
                  errorId="config-max-tokens-error"
                  className="cfg-param-field"
                >
                  <NumberInput
                    id="config-max-tokens"
                    mono
                    min={MIN_OUTPUT_TOKENS}
                    max={MAX_OUTPUT_TOKENS}
                    step={1}
                    value={maxTokensText}
                    onChange={(e) => {
                      setMaxTokensText(e.target.value);
                      setMaxTokensError(undefined);
                      const maxTokens = parseMaxTokens(e.target.value);
                      if (maxTokens !== undefined) setParam("max_tokens", maxTokens);
                    }}
                    onBlur={handleMaxTokensBlur}
                    error={!!maxTokensError}
                    aria-invalid={!!maxTokensError}
                    aria-describedby={maxTokensError ? "config-max-tokens-error" : undefined}
                    data-testid="config-max-tokens-input"
                  />
                </Field>
              ) : (
                <ParamSlider
                  label="Max tokens"
                  value={displayParams.max_tokens ?? 800}
                  min={MIN_OUTPUT_TOKENS}
                  max={MAX_OUTPUT_TOKENS}
                  step={1}
                  fmt={(v) => Math.round(v)}
                  onChange={() => {}}
                />
              )}
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
