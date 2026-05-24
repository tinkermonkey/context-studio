import { TextArea as Textarea, Button, Select, TextInput as Input, TabBar, KeyValueEditor, TriState, type KeyValueRow, Chip } from "@tinkermonkey/heimdall-ui";
import { useState, useRef, useEffect } from "react";
import { Copy, Play, Loader, CheckCircle, AlertCircle, RotateCcw } from "lucide-react";
import {
  usePipelineExecutions,
  useUpdatePipeline,
  useExecutePipeline,
} from "@/api/hooks/pipeline";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { formatRelativeTime, formatDuration } from "@/utils/formatters";
import { formatTimeAgo } from "@/utils/dateFormatting";
import { getStatusColor } from "@/utils/statusColorUtils";
import { useExecutionStore } from "@/stores/executionStore";
import { COPY } from "@/routes/app/pipelines/-copy";
import type { components } from "@/api/types";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type ExecutionResponse = components["schemas"]["ExecutionResponse"];

type Tab = "prompts" | "config" | "test" | "history";

interface PipelineDetailPanelProps {
  pipeline: PipelineConfigurationResponse;
}

const PROVIDERS = ["anthropic", "openai", "openrouter"] as const;

const MODEL_SUGGESTIONS: Record<string, string[]> = {
  anthropic: ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
  openrouter: ["anthropic/claude-sonnet-4-6", "openai/gpt-4o"],
};

function toRows(config: Record<string, unknown> | undefined | null): KeyValueRow[] {
  return Object.entries(config ?? {}).map(([k, v], i) => ({
    id: String(i),
    key: k,
    value: String(v),
  }));
}

function fromRows(rows: KeyValueRow[]): Record<string, unknown> {
  return Object.fromEntries(rows.filter((r) => r.key.trim()).map((r) => [r.key, r.value]));
}

interface TestOutput {
  text: string;
  status: ExecutionResponse["status"];
  duration: number;
  tokens_in: number;
  tokens_out: number;
  error: string | null;
}

const TABS = [
  { id: "prompts", label: COPY.TAB_PROMPTS },
  { id: "config", label: COPY.TAB_CONFIG },
  { id: "test", label: COPY.TAB_TEST },
  { id: "history", label: COPY.TAB_HISTORY },
];

export function PipelineDetailPanel({ pipeline }: PipelineDetailPanelProps) {
  const [activeTab, setActiveTab] = useState<Tab>("prompts");

  // Prompts state
  const [systemPrompt, setSystemPrompt] = useState(pipeline.system_prompt);
  const [userPrompt, setUserPrompt] = useState(pipeline.user_prompt);

  // Config state
  const [provider, setProvider] = useState(pipeline.provider);
  const [model, setModel] = useState(pipeline.model);
  const [enabled, setEnabled] = useState(pipeline.enabled);
  const [configRows, setConfigRows] = useState<KeyValueRow[]>(() => toRows(pipeline.config));
  const [configSaving, setConfigSaving] = useState(false);

  // Test state
  const [testInput, setTestInput] = useState("");
  const [testOutput, setTestOutput] = useState<TestOutput | null>(null);

  // History state
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);

  // Refs for fresh values in async callbacks
  const pipelineRef = useRef(pipeline);
  pipelineRef.current = pipeline;
  const systemPromptRef = useRef(systemPrompt);
  systemPromptRef.current = systemPrompt;
  const userPromptRef = useRef(userPrompt);
  userPromptRef.current = userPrompt;

  const { toast } = useToasts();
  const { data: executions = [], isLoading: executionsLoading } = usePipelineExecutions(pipeline.id);
  const updateMutation = useUpdatePipeline();
  const executeMutation = useExecutePipeline();
  const { startExecution, endExecution } = useExecutionStore();

  // Reset all state when switching to a different pipeline
  useEffect(() => {
    setSystemPrompt(pipeline.system_prompt);
    setUserPrompt(pipeline.user_prompt);
    setProvider(pipeline.provider);
    setModel(pipeline.model);
    setEnabled(pipeline.enabled);
    setConfigRows(toRows(pipeline.config));
    setConfigSaving(false);
    setTestOutput(null);
    setExpandedLogId(null);
    setActiveTab("prompts");
  }, [pipeline.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Prompts autosave — tracks both prompts as a single string key
  const promptsKey = `${systemPrompt} ${userPrompt}`;
  const { status: promptsStatus, lastSavedAt: promptsLastSavedAt } = useAutosave({
    data: promptsKey,
    mutationFn: async () => {
      const sp = systemPromptRef.current;
      const up = userPromptRef.current;
      const p = pipelineRef.current;
      if (sp === p.system_prompt && up === p.user_prompt) return;
      await updateMutation.mutateAsync({
        id: p.id,
        data: { system_prompt: sp, user_prompt: up },
      });
    },
    onError: (err) => toast("error", COPY.AUTOSAVE_FAILED(err.message)),
  });

  const isPromptsDirty =
    systemPrompt !== pipeline.system_prompt || userPrompt !== pipeline.user_prompt;

  const isConfigDirty =
    provider !== pipeline.provider ||
    model !== pipeline.model ||
    enabled !== pipeline.enabled ||
    JSON.stringify(fromRows(configRows)) !== JSON.stringify(pipeline.config ?? {});

  const handleRevertPrompts = () => {
    setSystemPrompt(pipeline.system_prompt);
    setUserPrompt(pipeline.user_prompt);
  };

  const handleSaveConfig = async () => {
    setConfigSaving(true);
    try {
      await updateMutation.mutateAsync({
        id: pipeline.id,
        data: { provider, model, enabled, config: fromRows(configRows) },
      });
      toast("success", COPY.PIPELINE_CONFIG_SAVED);
    } catch (err) {
      toast("error", err instanceof Error ? err.message : COPY.PIPELINE_CONFIG_SAVE_ERROR);
    } finally {
      setConfigSaving(false);
    }
  };

  const handleRunTest = async () => {
    startExecution(pipeline.id);
    setTestOutput(null);
    try {
      const execution = await executeMutation.mutateAsync({
        id: pipeline.id,
        inputText: testInput,
      });
      setTestOutput({
        text: execution.output_text,
        status: execution.status,
        duration: execution.duration_ms,
        tokens_in: execution.tokens_in,
        tokens_out: execution.tokens_out,
        error: execution.error_message ?? null,
      });
      if (execution.status !== "success") {
        toast("error", COPY.PIPELINE_FAILED(pipeline.title));
      }
    } catch (err) {
      toast("error", err instanceof Error ? err.message : COPY.PIPELINE_RUN_ERROR);
    } finally {
      endExecution(pipeline.id);
    }
  };

  const expandedExecution = expandedLogId
    ? executions.find((e) => e.id === expandedLogId)
    : null;

  const showAutosave = activeTab === "prompts" && promptsStatus !== "idle";

  return (
    <div data-testid="schema-drawer-container" className="stack">

      {/* Toolbar: autosave status + run shortcut */}
      <div className="pipeline-panel-toolbar">
        <div className="drawer-autosave-status" data-testid="drawer-autosave-status">
          {showAutosave && promptsStatus === "saving" && (
            <>
              <Loader size={14} className="spin" />
              <span className="autosave-label">Saving…</span>
            </>
          )}
          {showAutosave && promptsStatus === "saved" && promptsLastSavedAt && (
            <>
              <CheckCircle size={14} className="autosave-icon-saved" />
              <span className="autosave-label">Saved {formatTimeAgo(promptsLastSavedAt)}</span>
            </>
          )}
          {showAutosave && promptsStatus === "error" && (
            <>
              <AlertCircle size={14} className="autosave-icon-error" />
              <span className="autosave-label">Save failed</span>
            </>
          )}
          {activeTab === "prompts" && isPromptsDirty && (
            <Button
              variant="ghost"
              onClick={handleRevertPrompts}
              data-testid="drawer-revert-button"
            >
              <RotateCcw size={13} />
              Revert
            </Button>
          )}
        </div>
        <Button
          variant="ghost"
          onClick={() => { setActiveTab("test"); handleRunTest(); }}
          disabled={executeMutation.isPending}
          data-testid="run-pipeline-btn"
          aria-label="Run pipeline"
          title="Run pipeline"
        >
          {executeMutation.isPending ? <Loader size={16} className="spin" /> : <Play size={16} />}
        </Button>
      </div>

      <TabBar
        tabs={TABS}
        activeTabId={activeTab}
        onSelectTab={(id) => setActiveTab(id as Tab)}
      />

      {/* Prompts tab */}
      {activeTab === "prompts" && (
        <div className="stack">
          <div className="form-group">
            <label className="form-group-label">{COPY.SYSTEM_PROMPT_LABEL}</label>
            <Textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={9}
              mono
              placeholder={COPY.SYSTEM_PROMPT_PLACEHOLDER}
              data-testid="pipeline-system-prompt"
            />
          </div>
          <div className="form-group">
            <label className="form-group-label">{COPY.USER_PROMPT_LABEL}</label>
            <Textarea
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              rows={7}
              mono
              placeholder={COPY.USER_PROMPT_PLACEHOLDER}
              data-testid="pipeline-user-prompt"
            />
          </div>
        </div>
      )}

      {/* Config tab */}
      {activeTab === "config" && (
        <div className="stack">
          <div style={{ display: "flex", gap: "var(--space-3)" }}>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-group-label">{COPY.PROVIDER_LABEL}</label>
              <Select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                data-testid="pipeline-provider-select"
              >
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </Select>
            </div>
            <div className="form-group" style={{ flex: 2 }}>
              <label className="form-group-label">{COPY.MODEL_LABEL}</label>
              <Input
                value={model}
                onChange={(e) => setModel(e.target.value)}
                list="pipeline-edit-model-suggestions"
                data-testid="pipeline-model-input"
              />
              <datalist id="pipeline-edit-model-suggestions">
                {(MODEL_SUGGESTIONS[provider] ?? []).map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
            </div>
          </div>

          <div className="pipeline-enabled-row">
            <TriState
              id="pipeline-edit-enabled"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              data-testid="pipeline-enabled-toggle"
            />
            <label htmlFor="pipeline-edit-enabled" className="form-group-label">
              {COPY.ENABLED_LABEL}
            </label>
          </div>

          <div className="form-group">
            <label className="form-group-label">{COPY.PIPELINE_CONFIGURATION_LABEL}</label>
            <KeyValueEditor
              rows={configRows}
              onChange={setConfigRows}
              data-testid="pipeline-config-editor"
            />
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <Button
              variant="primary"
              onClick={handleSaveConfig}
              disabled={configSaving || !isConfigDirty}
              data-testid="pipeline-save-config-button"
            >
              {configSaving ? COPY.SAVING_LABEL : COPY.PIPELINE_SAVE_BUTTON}
            </Button>
          </div>
        </div>
      )}

      {/* Test tab */}
      {activeTab === "test" && (
        <div className="stack">
          <div className="form-group">
            <label className="form-group-label">{COPY.TEST_INPUT_LABEL}</label>
            <Textarea
              value={testInput}
              onChange={(e) => setTestInput(e.target.value)}
              rows={5}
              placeholder={COPY.TEST_INPUT_PLACEHOLDER}
              data-testid="pipeline-test-input"
            />
          </div>

          <Button
            variant="primary"
            onClick={handleRunTest}
            disabled={executeMutation.isPending}
            data-testid="pipeline-run-test-button"
          >
            {executeMutation.isPending ? (
              <>
                <Loader size={14} className="spin" style={{ marginRight: "var(--space-1)" }} />
                {COPY.RUNNING_LABEL}
              </>
            ) : (
              <>
                <Play size={14} style={{ marginRight: "var(--space-1)" }} />
                {COPY.RUN_TEST_BUTTON}
              </>
            )}
          </Button>

          {testOutput ? (
            <div className="pipeline-test-output" data-testid="pipeline-test-output">
              <div className="pipeline-test-output-header">
                <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
                  <Chip variant={getStatusColor(testOutput.status)}>{testOutput.status}</Chip>
                  <span className="pipeline-test-meta">
                    {formatDuration(testOutput.duration)} ·{" "}
                    {testOutput.tokens_in} → {testOutput.tokens_out} tokens
                  </span>
                </div>
                <Button
                  variant="ghost"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(testOutput.text || testOutput.error || "");
                      toast("success", COPY.OUTPUT_COPIED);
                    } catch {
                      toast("error", COPY.CLIPBOARD_COPY_ERROR);
                    }
                  }}
                  aria-label="Copy output"
                  data-testid="pipeline-copy-output-button"
                >
                  <Copy size={14} />
                </Button>
              </div>
              <pre className="pipeline-test-output-text" data-testid="pipeline-test-output-text">
                {testOutput.text || testOutput.error || "(no output)"}
              </pre>
            </div>
          ) : (
            <div className="pipeline-empty-state" data-testid="pipeline-test-no-output">
              {COPY.TEST_NO_OUTPUT}
            </div>
          )}
        </div>
      )}

      {/* History tab */}
      {activeTab === "history" && (
        <div className="stack">
          {executionsLoading ? (
            <div className="stack">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} height={40} />
              ))}
            </div>
          ) : executions.length === 0 ? (
            <div className="pipeline-empty-state" data-testid="pipeline-no-runs">
              {COPY.PIPELINE_NO_RUNS}
            </div>
          ) : (
            <table className="t" data-testid="pipeline-runs-table">
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>{COPY.RUN_STATUS_HEADER}</th>
                  <th style={{ textAlign: "left" }}>{COPY.RUN_STARTED_HEADER}</th>
                  <th style={{ textAlign: "left" }}>{COPY.RUN_DURATION_HEADER}</th>
                  <th style={{ textAlign: "left" }}>{COPY.RUN_TOKENS_HEADER}</th>
                  <th style={{ textAlign: "right", width: 40 }} />
                </tr>
              </thead>
              <tbody>
                {executions.slice(0, 10).map((execution) => (
                  <tr key={execution.id}>
                    <td>
                      <Chip variant={getStatusColor(execution.status)}>
                        {execution.status}
                      </Chip>
                    </td>
                    <td>{formatRelativeTime(execution.timestamp)}</td>
                    <td>{formatDuration(execution.duration_ms)}</td>
                    <td>
                      {execution.tokens_in} → {execution.tokens_out}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      {execution.error_message && (
                        <Button
                          variant="ghost"
                          onClick={() =>
                            setExpandedLogId(
                              expandedLogId === execution.id ? null : execution.id,
                            )
                          }
                          aria-expanded={expandedLogId === execution.id}
                          data-testid={`pipeline-view-log-${execution.id}`}
                        >
                          {COPY.PIPELINE_VIEW_LOG}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {expandedExecution?.error_message && (
            <div data-testid="pipeline-error-log" className="pipeline-error-log">
              <div className="flex-between" style={{ marginBottom: "var(--space-2)" }}>
                <span className="error-log-title">{COPY.ERROR_DETAILS_TITLE}</span>
                <Button
                  variant="ghost"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(expandedExecution.error_message ?? "");
                      toast("success", COPY.ERROR_COPIED);
                    } catch {
                      toast("error", COPY.CLIPBOARD_COPY_ERROR);
                    }
                  }}
                  aria-label="Copy error to clipboard"
                  data-testid="pipeline-copy-error-button"
                >
                  <Copy size={14} />
                </Button>
              </div>
              <pre className="pipeline-error-message">{expandedExecution.error_message}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
