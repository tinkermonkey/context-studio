import { useState } from "react";
import { Button, TextInput as Input, TextArea as Textarea, Select, TriState } from "@tinkermonkey/heimdall-ui";
import { COPY } from "@/routes/app/pipelines/-copy";
import type { components } from "@/api/types";

type PipelineConfigurationCreate = components["schemas"]["PipelineConfigurationCreate"];

const PROVIDERS = ["anthropic", "openai", "openrouter"] as const;

const PIPELINE_TYPES = [
  { value: "schema_extraction", label: "Schema Extraction" },
  { value: "individual_extraction", label: "Individual Extraction" },
  { value: "schema_node_grounding", label: "Schema Node Grounding" },
  { value: "schema_node_definition_refinement", label: "Definition Refinement" },
  { value: "schema_node_connection_refinement", label: "Connection Refinement" },
] as const;

const MODEL_SUGGESTIONS: Record<string, string[]> = {
  anthropic: ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
  openrouter: ["anthropic/claude-sonnet-4-6", "openai/gpt-4o"],
};

interface PipelineCreateFormProps {
  onSubmit: (data: PipelineConfigurationCreate) => Promise<void>;
  onCancel: () => void;
  isLoading: boolean;
}

export function PipelineCreateForm({ onSubmit, onCancel, isLoading }: PipelineCreateFormProps) {
  const [title, setTitle] = useState("");
  const [pipeline, setPipeline] = useState("schema_extraction");
  const [provider, setProvider] = useState<string>("anthropic");
  const [model, setModel] = useState("claude-sonnet-4-6");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const clearError = (field: string) =>
    setErrors((prev) => ({ ...prev, [field]: "" }));

  const validate = (): boolean => {
    const next: Record<string, string> = {};
    if (!title.trim()) next.title = COPY.VALIDATION_TITLE_REQUIRED;
    if (!model.trim()) next.model = COPY.VALIDATION_MODEL_REQUIRED;
    if (!systemPrompt.trim()) next.system_prompt = COPY.VALIDATION_SYSTEM_PROMPT_REQUIRED;
    if (!userPrompt.trim()) next.user_prompt = COPY.VALIDATION_USER_PROMPT_REQUIRED;
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleProviderChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    setProvider(next);
    setModel(MODEL_SUGGESTIONS[next]?.[0] ?? "");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    await onSubmit({
      title: title.trim(),
      pipeline,
      provider,
      model: model.trim(),
      system_prompt: systemPrompt,
      user_prompt: userPrompt,
      enabled,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="stack" data-testid="pipeline-create-form">
      <div className="form-group">
        <label className="form-group-label">{COPY.CREATE_FORM_TITLE_LABEL}</label>
        <Input
          value={title}
          onChange={(e) => { setTitle(e.target.value); clearError("title"); }}
          placeholder={COPY.CREATE_FORM_TITLE_PLACEHOLDER}
          data-testid="pipeline-create-title"
        />
        {errors.title && <span className="form-error">{errors.title}</span>}
      </div>

      <div className="form-group">
        <label className="form-group-label">{COPY.CREATE_FORM_PIPELINE_TYPE_LABEL}</label>
        <Select
          value={pipeline}
          onChange={(e) => setPipeline(e.target.value)}
          data-testid="pipeline-create-type"
        >
          {PIPELINE_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </Select>
      </div>

      <div style={{ display: "flex", gap: "var(--space-3)" }}>
        <div className="form-group" style={{ flex: 1 }}>
          <label className="form-group-label">{COPY.CREATE_FORM_PROVIDER_LABEL}</label>
          <Select
            value={provider}
            onChange={handleProviderChange}
            data-testid="pipeline-create-provider"
          >
            {PROVIDERS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </Select>
        </div>

        <div className="form-group" style={{ flex: 2 }}>
          <label className="form-group-label">{COPY.CREATE_FORM_MODEL_LABEL}</label>
          <Input
            value={model}
            onChange={(e) => { setModel(e.target.value); clearError("model"); }}
            list="pipeline-create-model-suggestions"
            placeholder={COPY.CREATE_FORM_MODEL_PLACEHOLDER}
            data-testid="pipeline-create-model"
          />
          <datalist id="pipeline-create-model-suggestions">
            {(MODEL_SUGGESTIONS[provider] ?? []).map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          {errors.model && <span className="form-error">{errors.model}</span>}
        </div>
      </div>

      <div className="form-group">
        <label className="form-group-label">{COPY.CREATE_FORM_SYSTEM_PROMPT_LABEL}</label>
        <Textarea
          value={systemPrompt}
          onChange={(e) => { setSystemPrompt(e.target.value); clearError("system_prompt"); }}
          rows={5}
          mono
          placeholder={COPY.CREATE_FORM_SYSTEM_PROMPT_PLACEHOLDER}
          data-testid="pipeline-create-system-prompt"
        />
        {errors.system_prompt && <span className="form-error">{errors.system_prompt}</span>}
      </div>

      <div className="form-group">
        <label className="form-group-label">{COPY.CREATE_FORM_USER_PROMPT_LABEL}</label>
        <Textarea
          value={userPrompt}
          onChange={(e) => { setUserPrompt(e.target.value); clearError("user_prompt"); }}
          rows={4}
          mono
          placeholder={COPY.CREATE_FORM_USER_PROMPT_PLACEHOLDER}
          data-testid="pipeline-create-user-prompt"
        />
        {errors.user_prompt && <span className="form-error">{errors.user_prompt}</span>}
      </div>

      <div className="pipeline-enabled-row">
        <TriState
          id="pipeline-create-enabled"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          data-testid="pipeline-create-enabled"
        />
        <label htmlFor="pipeline-create-enabled" className="form-group-label">
          {COPY.CREATE_FORM_ENABLED_LABEL}
        </label>
      </div>

      <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
        <Button
          variant="ghost"
          size="sm"
          type="button"
          onClick={onCancel}
          data-testid="pipeline-create-cancel"
        >
          {COPY.PIPELINE_CANCEL_BUTTON}
        </Button>
        <Button
          variant="primary"
          size="sm"
          type="submit"
          disabled={isLoading}
          data-testid="pipeline-create-submit"
        >
          {isLoading ? COPY.CREATE_FORM_CREATING : COPY.CREATE_FORM_SUBMIT}
        </Button>
      </div>
    </form>
  );
}
