import { useState, useRef, useEffect } from "react";
import { Copy } from "lucide-react";
import { usePipelineExecutions, useUpdatePipeline } from "@/api/hooks/pipeline";
import { Drawer } from "@/components/ui/Drawer";
import { Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useAutosave } from "@/hooks/useAutosave";
import { useToasts } from "@/components/ui/Toast";
import { Chip } from "@/components/ui/Chip";
import { formatRelativeTime, formatDuration } from "@/utils/formatters";
import type { components } from "@/api/types";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type ExecutionResponse = components["schemas"]["ExecutionResponse"];

interface PipelineDetailPanelProps {
  pipeline: PipelineConfigurationResponse;
  onClose: () => void;
}

function getStatusColor(status: ExecutionResponse["status"]): "emerald" | "rose" | "gray" {
  switch (status) {
    case "success":
      return "emerald";
    case "error":
    case "timeout":
      return "rose";
    default:
      return "gray";
  }
}

function getStatusLabel(status: ExecutionResponse["status"]): string {
  return status;
}

export function PipelineDetailPanel({ pipeline, onClose }: PipelineDetailPanelProps) {
  const [isEditingConfig, setIsEditingConfig] = useState(false);
  const [configText, setConfigText] = useState(
    JSON.stringify(pipeline.config || {}, null, 2)
  );
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);
  const lastSavedAtRef = useRef<Date | null>(null);
  const { toast } = useToasts();

  const { data: executions = [], isLoading: executionsLoading } = usePipelineExecutions(pipeline.id);
  const updateMutation = useUpdatePipeline();

  useEffect(() => {
    setConfigText(JSON.stringify(pipeline.config || {}, null, 2));
  }, [pipeline.config]);

  const isDirty = configText !== JSON.stringify(pipeline.config || {}, null, 2);

  const { status: autosaveStatus } = useAutosave({
    data: isEditingConfig ? undefined : configText,
    mutationFn: async () => {
      if (!isDirty) return;
      await updateMutation.mutateAsync({
        id: pipeline.id,
        data: {
          title: pipeline.title,
          enabled: pipeline.enabled,
          config: JSON.parse(configText),
        },
      });
      lastSavedAtRef.current = new Date();
    },
    onError: (error) => {
      toast("error", `Autosave failed: ${error.message}`);
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
      toast("success", "Pipeline configuration saved");
    } catch (error) {
      toast("error", error instanceof Error ? error.message : "Failed to save configuration");
    }
  };

  const handleRevert = () => {
    setConfigText(JSON.stringify(pipeline.config || {}, null, 2));
    setIsEditingConfig(false);
  };

  const lastRun = executions[0];
  const expandedExecution = expandedLogId ? executions.find((e) => e.id === expandedLogId) : null;

  const autosaveState = isEditingConfig ? undefined : autosaveStatus === "idle" ? undefined : (autosaveStatus as "saving" | "saved" | "error");

  return (
    <Drawer
      open={!!pipeline}
      onClose={onClose}
      title={pipeline.title}
      autosaveState={autosaveState}
      isDirty={isDirty && !isEditingConfig}
      lastSavedAt={lastSavedAtRef.current || undefined}
      onRevert={!isEditingConfig ? handleRevert : undefined}
    >
      <div className="stack-lg">
        {/* Definition Editor Section */}
        <div>
          <div className="flex-between">
            <label className="form-group-label">Pipeline Configuration</label>
            {!isEditingConfig && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsEditingConfig(true)}
                data-testid="pipeline-edit-config-button"
              >
                Edit
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
                  Save
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRevert}
                  data-testid="pipeline-revert-config-button"
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <pre
              data-testid="pipeline-config-pre"
              className="pipeline-code-block"
            >
              {configText}
            </pre>
          )}
        </div>

        {/* Last 10 Runs Section */}
        <div>
          <label className="form-group-label">Last 10 Runs</label>
          {executionsLoading ? (
            <div className="stack">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} height={40} />
              ))}
            </div>
          ) : executions.length === 0 ? (
            <div
              className="pipeline-empty-state"
              data-testid="pipeline-no-runs"
            >
              This pipeline has never been run
            </div>
          ) : (
            <div className="stack">
              <table
                className="t"
                data-testid="pipeline-runs-table"
              >
                <thead>
                  <tr>
                    <th style={{ textAlign: "left" }}>Status</th>
                    <th style={{ textAlign: "left" }}>Started</th>
                    <th style={{ textAlign: "left" }}>Duration</th>
                    <th style={{ textAlign: "left" }}>Tokens</th>
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
                      <td>{execution.tokens_in} → {execution.tokens_out}</td>
                      <td style={{ textAlign: "right" }}>
                        {execution.error_message && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              setExpandedLogId(
                                expandedLogId === execution.id ? null : execution.id
                              )
                            }
                            aria-expanded={expandedLogId === execution.id}
                            data-testid={`pipeline-view-log-${execution.id}`}
                          >
                            View log
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
          <div
            data-testid="pipeline-error-log"
            className="pipeline-error-log"
          >
            <div className="flex-between" style={{ marginBottom: "var(--space-2)" }}>
              <span className="error-log-title">Error Details</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  navigator.clipboard.writeText(
                    expandedExecution.error_message || ""
                  );
                  toast("success", "Error copied to clipboard");
                }}
                aria-label="Copy error to clipboard"
                data-testid="pipeline-copy-error-button"
              >
                <Copy size={14} />
              </Button>
            </div>
            <pre className="pipeline-error-message">
              {expandedExecution.error_message}
            </pre>
          </div>
        )}
      </div>
    </Drawer>
  );
}
