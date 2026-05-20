import { TextArea as Textarea, Button } from "@tinkermonkey/heimdall-ui";
import { useState, useRef, useEffect } from "react";
import { Copy, Play, Loader } from "lucide-react";
import { usePipelineExecutions, useUpdatePipeline, useExecutePipeline } from "@/api/hooks/pipeline";
import { Drawer } from "@/components/ui/Drawer";

import { Skeleton } from "@/components/ui/Skeleton";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { Chip } from "@/components/ui/Chip";
import { formatRelativeTime, formatDuration } from "@/utils/formatters";
import { getStatusColor } from "@/utils/statusColorUtils";
import { useExecutionStore } from "@/stores/executionStore";
import { COPY } from "@/routes/app/pipelines/-copy";
import type { components } from "@/api/types";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type ExecutionResponse = components["schemas"]["ExecutionResponse"];

interface PipelineDetailPanelProps {
  pipeline: PipelineConfigurationResponse;
  onClose: () => void;
}

function getStatusLabel(status: ExecutionResponse["status"]): string {
  return status;
}

export function PipelineDetailPanel({ pipeline, onClose }: PipelineDetailPanelProps) {
  const [isEditingConfig, setIsEditingConfig] = useState(false);
  const [configText, setConfigText] = useState(JSON.stringify(pipeline.config || {}, null, 2));
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);
  const lastSavedAtRef = useRef<Date | null>(null);
  const { toast } = useToasts();

  const { data: executions = [], isLoading: executionsLoading } = usePipelineExecutions(
    pipeline.id,
  );
  const updateMutation = useUpdatePipeline();
  const executeMutation = useExecutePipeline();
  const { startExecution, endExecution } = useExecutionStore();

  useEffect(() => {
    setConfigText(JSON.stringify(pipeline.config || {}, null, 2));
  }, [pipeline.config]);

  const isDirty = configText !== JSON.stringify(pipeline.config || {}, null, 2);

  const { status: autosaveStatus } = useAutosave({
    data: isEditingConfig ? undefined : configText,
    mutationFn: async () => {
      if (!isDirty) return;
      try {
        const parsed = JSON.parse(configText);
        await updateMutation.mutateAsync({
          id: pipeline.id,
          data: {
            title: pipeline.title,
            enabled: pipeline.enabled,
            config: parsed,
          },
        });
        lastSavedAtRef.current = new Date();
      } catch (error) {
        if (error instanceof SyntaxError) {
          throw new Error("Invalid JSON in pipeline configuration", { cause: error });
        }
        throw error;
      }
    },
    onError: (error) => {
      toast("error", COPY.AUTOSAVE_FAILED(error.message));
    },
  });

  const handleSaveClick = async () => {
    try {
      await updateMutation.mutateAsync({
        id: pipeline.id,
        data: {
          title: pipeline.title,
          enabled: pipeline.enabled,
          config: JSON.parse(configText),
        },
      });
      lastSavedAtRef.current = new Date();
      setIsEditingConfig(false);
      toast("success", COPY.PIPELINE_CONFIG_SAVED);
    } catch (error) {
      toast("error", error instanceof Error ? error.message : COPY.PIPELINE_CONFIG_SAVE_ERROR);
    }
  };

  const handleRevert = () => {
    setConfigText(JSON.stringify(pipeline.config || {}, null, 2));
    setIsEditingConfig(false);
  };

  const handleRunPipeline = async () => {
    try {
      startExecution(pipeline.id);
      const execution = await executeMutation.mutateAsync({
        id: pipeline.id,
        inputText: "",
      });
      if (execution.status === "success") {
        toast("success", COPY.PIPELINE_COMPLETED(pipeline.title));
      } else if (execution.status === "error" || execution.status === "timeout") {
        toast("error", COPY.PIPELINE_FAILED(pipeline.title));
      }
    } catch (error) {
      toast("error", error instanceof Error ? error.message : COPY.PIPELINE_RUN_ERROR);
    } finally {
      endExecution(pipeline.id);
    }
  };

  const expandedExecution = expandedLogId ? executions.find((e) => e.id === expandedLogId) : null;

  const autosaveState = isEditingConfig
    ? undefined
    : autosaveStatus === "idle"
      ? undefined
      : (autosaveStatus as "saving" | "saved" | "error");

  return (
    <Drawer
      open={!!pipeline}
      onClose={onClose}
      title={pipeline.title}
      autosaveState={autosaveState}
      isDirty={isDirty && !isEditingConfig}
      lastSavedAt={lastSavedAtRef.current || undefined}
      onRevert={!isEditingConfig ? handleRevert : undefined}
      headerAction={
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRunPipeline}
          disabled={executeMutation.isPending}
          data-testid="run-pipeline-btn"
          aria-label="Run pipeline"
          title="Run pipeline"
        >
          {executeMutation.isPending ? <Loader size={16} className="spin" /> : <Play size={16} />}
        </Button>
      }
    >
      <div className="stack-lg">
        {/* Definition Editor Section */}
        <div>
          <div className="flex-between">
            <label className="form-group-label">{COPY.PIPELINE_CONFIGURATION_LABEL}</label>
            {!isEditingConfig && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsEditingConfig(true)}
                data-testid="pipeline-edit-config-button"
              >
                {COPY.PIPELINE_EDIT_BUTTON}
              </Button>
            )}
          </div>

          {isEditingConfig ? (
            <div className="stack">
              <Textarea
                value={configText}
                onChange={(e) => setConfigText(e.target.value)}
                rows={10}
                mono
                data-testid="pipeline-config-textarea"
              />
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleSaveClick}
                  disabled={updateMutation.isPending || !isDirty}
                  data-testid="pipeline-save-config-button"
                >
                  {COPY.PIPELINE_SAVE_BUTTON}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRevert}
                  data-testid="pipeline-revert-config-button"
                >
                  {COPY.PIPELINE_CANCEL_BUTTON}
                </Button>
              </div>
            </div>
          ) : (
            <pre data-testid="pipeline-config-pre" className="pipeline-code-block">
              {configText}
            </pre>
          )}
        </div>

        {/* Last 10 Runs Section */}
        <div>
          <label className="form-group-label">{COPY.LAST_10_RUNS_LABEL}</label>
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
            <div className="stack">
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
                        <Chip color={getStatusColor(execution.status)}>
                          {getStatusLabel(execution.status)}
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
                            size="sm"
                            onClick={() =>
                              setExpandedLogId(expandedLogId === execution.id ? null : execution.id)
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
            </div>
          )}
        </div>

        {/* Error Log Panel */}
        {expandedExecution && expandedExecution.error_message && (
          <div data-testid="pipeline-error-log" className="pipeline-error-log">
            <div className="flex-between" style={{ marginBottom: "var(--space-2)" }}>
              <span className="error-log-title">{COPY.ERROR_DETAILS_TITLE}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(expandedExecution.error_message || "");
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
    </Drawer>
  );
}
