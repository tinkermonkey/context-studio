import { useState, useEffect, useRef } from "react";
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
import { useRegisteredModels } from "@/api/hooks/pipeline/useRegisteredModels";
import { useParameterBounds } from "@/api/hooks/pipeline/useParameterBounds";
import { useHealth } from "@/api/hooks/admin/useHealth";
import type { ParameterSettings, PipelineConfiguration } from "@/api/services/pipeline";
import { ParamNumberField } from "./ParamNumberField";
import { ParamSlider } from "./ParamSlider";
import { StagePromptsSection } from "./StagePromptsSection";
import { stagePromptsBody, type StagePromptsBody } from "./stagePrompts";
import "./ConfigEditor.css";

type PipelineConfigurationResponse = PipelineConfiguration;

const MODEL_REQUIRED = "A model is required";

/** The parameters of a configuration that may be left to the default configuration. */
type InheritableParameter = "temperature" | "max_tokens";

interface DraftConfig {
  name: string;
  description: string;
  provider: string;
  model: string;
  /**
   * What the configuration itself sets: a null temperature or max_tokens is
   * left to the implementation's default configuration. Null as a whole for a
   * pipeline whose runs take no LLM parameters.
   */
  parameters: ParameterSettings | null;
  enabled: boolean;
}

/**
 * The editable copy of a configuration. A new one takes its provider and model
 * from `template` (the implementation's default configuration) and sets no
 * temperature or output limit of its own, so it follows the default's.
 */
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
      parameters: template?.parameters
        ? { temperature: null, max_tokens: null, top_p: template.parameters.top_p }
        : null,
      enabled: true,
    };
  }
  return {
    name: config.name ?? "",
    description: config.description ?? "",
    provider: config.provider ?? "",
    model: config.model ?? "",
    parameters: config.parameter_settings ?? null,
    enabled: config.enabled ?? true,
  };
}

/** A change to save: parameters are merged one by one onto the latest saved ones. */
type SavePatch = Partial<Omit<DraftConfig, "parameters">> & {
  parameters?: Partial<ParameterSettings>;
};

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

  // Bumped when a failed save puts the form back to what is saved, so typed fields start over.
  const [resets, setResets] = useState(0);
  const [draft, setDraft] = useState<DraftConfig>(() =>
    makeDraft(isCreate ? null : config, template),
  );
  const [modelError, setModelError] = useState<string>();
  // Parameter fields holding text the API would refuse: nothing is created while any does.
  const [invalidParams, setInvalidParams] = useState<ReadonlySet<InheritableParameter>>(new Set());
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Providers are the server's; models are suggestions only (any id may be typed).
  const { data: health } = useHealth();
  const registeredModels = useRegisteredModels(pipelineType);
  const bounds = useParameterBounds();

  const createMutation = useCreateConfiguration(pipelineType, implId);
  const updateMutation = useUpdateConfiguration(pipelineType, implId);
  const deleteMutation = useDeleteConfiguration(pipelineType, implId);

  useEffect(() => {
    setDraft(makeDraft(isCreate ? null : config, template));
    setModelError(undefined);
    setInvalidParams(new Set());
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

  // Current display values: the draft while creating or editing, the configuration otherwise
  const displayName = isCreate ? draft.name : (config?.name ?? "");
  const displayDesc = isCreate ? draft.description : (config?.description ?? "");
  const displayProvider = isCreate ? draft.provider : (config?.provider ?? "");
  const displayModel = isCreate ? draft.model : (config?.model ?? "");
  const displayEnabled = isCreate ? draft.enabled : (config?.enabled ?? true);
  // The values in effect: shown read-only, and as what an unset field inherits.
  const effective = config?.parameters ?? null;
  const inherited = template?.parameters ?? effective;

  const setField = (k: keyof DraftConfig, v: unknown) => setDraft((d) => ({ ...d, [k]: v }));

  const setParam = <K extends keyof ParameterSettings>(k: K, v: ParameterSettings[K]) =>
    setDraft((d) => (d.parameters ? { ...d, parameters: { ...d.parameters, [k]: v } } : d));

  /** Save a temperature or output limit (null: back to the default's), unless it is what is saved. */
  const commitParam = (k: InheritableParameter, v: number | null) => {
    const saved = (latestSaved.current ?? config)?.parameter_settings;
    if (isCreate || (saved?.[k] ?? null) === v) return;
    void handleSaveField({ parameters: { [k]: v } });
  };

  const setParamValid = (k: InheritableParameter, valid: boolean) =>
    setInvalidParams((prev) => {
      if (prev.has(k) !== valid) return prev;
      const next = new Set(prev);
      if (valid) next.delete(k);
      else next.add(k);
      return next;
    });

  const handleProviderChange = (v: string) => {
    setField("provider", v);
    if (!isCreate) void handleSaveField({ provider: v });
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

  /**
   * Save a change; stagePrompts replaces every stage's prompts when given.
   * Every save starts from the latest saved configuration, read when its turn
   * in the queue comes: an update replaces the whole configuration, so a save
   * built from an older copy would undo the save before it.
   */
  const handleSaveField = (patch: SavePatch, stagePrompts?: StagePromptsBody) => {
    if (isCreate || !config || config.is_system) return Promise.resolve();
    saveQueue.current = saveQueue.current.then(async () => {
      const base = latestSaved.current ?? config;
      const saved = makeDraft(base);
      const updated = {
        ...saved,
        ...patch,
        // What the configuration sets, never the values in effect: an
        // inherited temperature or output limit stays inherited.
        parameters: saved.parameters ? { ...saved.parameters, ...patch.parameters } : null,
      };
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
            parameters: updated.parameters ?? undefined,
            enabled: updated.enabled,
          },
        });
      } catch (err) {
        toast("error", err instanceof Error ? err.message : "Failed to save");
        // The change was not saved: show what is, so the form and the server
        // agree and the next save does not quietly drop what the form shows.
        setDraft(makeDraft(latestSaved.current ?? config));
        setInvalidParams(new Set());
        setResets((n) => n + 1);
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
        parameters: draft.parameters ?? undefined,
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
        // The copy sets what the original sets, and inherits what it inherits.
        parameters: config.parameter_settings ?? undefined,
        enabled: config.enabled,
      });
      onDuplicate?.(result);
    } catch (err) {
      toast("error", err instanceof Error ? err.message : "Failed to duplicate configuration");
    }
  };

  const isSystemConfig = !isCreate && (config?.is_system ?? false);
  const editable = active && !isSystemConfig;
  // Typed parameter fields start over with another configuration or mode.
  const fieldsKey = `${config?.id ?? "new"}-${mode}-${resets}`;
  /**
   * Says a value in effect is not the configuration's own: the default
   * configuration's, or none at all when that sets none either.
   */
  const inheritedNote = (k: InheritableParameter) => {
    if (!config?.parameter_settings || config.parameter_settings[k] != null) return undefined;
    return effective?.[k] == null ? "none set" : "inherited";
  };
  const validNew =
    isCreate &&
    draft.name.trim() !== "" &&
    draft.provider !== "" &&
    draft.model.trim() !== "" &&
    invalidParams.size === 0;
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
              // Starts over from the saved prompts when a failed save resets the form.
              key={`stage-prompts-${fieldsKey}`}
              stages={config.stage_prompts}
              editable={isEdit && !isSystemConfig}
              onSave={(body) => {
                void handleSaveField({}, body);
              }}
            />
          )}

          {/* Parameters: none for a pipeline whose runs take no temperature or output limit */}
          {editable && draft.parameters && (
            <section data-testid="config-parameters">
              <div className="cfg-section-title">Parameters</div>
              <div className="cfg-params-grid">
                <ParamNumberField
                  key={`temperature-${fieldsKey}`}
                  id="config-temperature"
                  label="Temperature"
                  value={draft.parameters.temperature ?? null}
                  inherited={inherited?.temperature}
                  bounds={bounds.temperature}
                  onChange={(v) => setParam("temperature", v)}
                  onValidChange={(valid) => setParamValid("temperature", valid)}
                  onCommit={(v) => commitParam("temperature", v)}
                />
                <ParamNumberField
                  key={`max-tokens-${fieldsKey}`}
                  id="config-max-tokens"
                  label="Max tokens"
                  integer
                  value={draft.parameters.max_tokens ?? null}
                  inherited={inherited?.max_tokens}
                  bounds={bounds.max_tokens}
                  onChange={(v) => setParam("max_tokens", v)}
                  onValidChange={(valid) => setParamValid("max_tokens", valid)}
                  onCommit={(v) => commitParam("max_tokens", v)}
                />
                <ParamSlider
                  active
                  label="Top-p"
                  value={draft.parameters.top_p}
                  min={bounds.top_p?.minimum ?? 0}
                  max={bounds.top_p?.maximum ?? 1}
                  step={0.01}
                  fmt={(v) => v.toFixed(2)}
                  onChange={(v) => {
                    setParam("top_p", v);
                    void handleSaveField({ parameters: { top_p: v } });
                  }}
                />
              </div>
              <p className="cfg-params-note">
                An empty Temperature or Max tokens follows the implementation&apos;s default
                configuration.
              </p>
            </section>
          )}
          {!editable && effective && (
            <section data-testid="config-parameters">
              <div className="cfg-section-title">Parameters</div>
              <div className="cfg-params-grid">
                <ParamSlider
                  label="Temperature"
                  value={effective.temperature ?? null}
                  min={bounds.temperature?.minimum ?? 0}
                  max={bounds.temperature?.maximum ?? Math.max(effective.temperature ?? 0, 1)}
                  step={0.05}
                  fmt={(v) => v.toFixed(2)}
                  note={inheritedNote("temperature")}
                  onChange={() => {}}
                />
                <ParamSlider
                  label="Max tokens"
                  value={effective.max_tokens ?? null}
                  min={bounds.max_tokens?.minimum ?? 0}
                  max={bounds.max_tokens?.maximum ?? effective.max_tokens ?? 0}
                  step={1}
                  fmt={(v) => Math.round(v)}
                  note={inheritedNote("max_tokens")}
                  onChange={() => {}}
                />
                <ParamSlider
                  label="Top-p"
                  value={effective.top_p}
                  min={bounds.top_p?.minimum ?? 0}
                  max={bounds.top_p?.maximum ?? 1}
                  step={0.01}
                  fmt={(v) => v.toFixed(2)}
                  onChange={() => {}}
                />
              </div>
            </section>
          )}

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
