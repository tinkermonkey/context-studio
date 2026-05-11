import type { components } from "@/api/types";
import { Cpu, Play, Loader } from "lucide-react";
import { usePipelineExecutions, useExecutePipeline } from "@/api/hooks/pipeline";
import { formatRelativeTime, formatDuration } from "@/utils/formatters";
import { Button } from "@/components/ui/Button";
import { useToasts } from "@/components/ui/Toast";
import { useExecutionStore } from "@/stores/executionStore";
import { COPY } from "@/routes/app/pipelines/-copy";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type ExecutionResponse = components["schemas"]["ExecutionResponse"];

interface PipelineCardProps {
  pipeline: PipelineConfigurationResponse;
}

type StatusVariant = "success" | "failed" | "idle" | "disabled";

function mapExecutionStatusToVariant(
  status: ExecutionResponse["status"],
  enabled: boolean,
): StatusVariant {
  if (!enabled) return "disabled";
  switch (status) {
    case "success":
      return "success";
    case "error":
    case "timeout":
      return "failed";
    default:
      return "idle";
  }
}

function getStatusChipClass(variant: StatusVariant): string {
  switch (variant) {
    case "success":
      return "emerald";
    case "failed":
      return "rose";
    case "disabled":
      return "gray";
    case "idle":
      return "gray";
  }
}

function getStatusLabel(variant: StatusVariant): string {
  switch (variant) {
    case "success":
      return "success";
    case "failed":
      return "failed";
    case "disabled":
      return "disabled";
    case "idle":
      return "idle";
  }
}

export function PipelineCard({ pipeline }: PipelineCardProps) {
  const { data: executions = [] } = usePipelineExecutions(pipeline.id);
  const executeMutation = useExecutePipeline();
  const { toast } = useToasts();
  const { startExecution, endExecution } = useExecutionStore();

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

  const lastExecution = executions[0] || null;
  const statusVariant = lastExecution
    ? mapExecutionStatusToVariant(lastExecution.status, pipeline.enabled)
    : !pipeline.enabled
      ? "disabled"
      : "idle";
  const lastRunTime = lastExecution ? formatRelativeTime(new Date(lastExecution.timestamp)) : null;
  const duration = lastExecution ? formatDuration(lastExecution.duration_ms) : null;

  return (
    <div className="pipeline-card" data-testid={`pipeline-card-${pipeline.id}`}>
      <div className="pipeline-card-head">
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", minWidth: 0 }}>
          <Cpu size={16} style={{ color: "var(--accent-violet, #7c3aed)", flexShrink: 0 }} />
          <span className="name">{pipeline.title}</span>
        </div>

        <div className="pipeline-card-actions">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRunPipeline}
            disabled={executeMutation.isPending}
            data-testid="run-pipeline-btn"
            aria-label="Run pipeline"
            title="Run pipeline"
          >
            {executeMutation.isPending ? (
              <Loader size={16} className="spin" />
            ) : (
              <Play size={16} />
            )}
          </Button>
          <div
            className={`chip ${getStatusChipClass(statusVariant)}`}
            data-testid="pipeline-status-chip"
            role="status"
            aria-label={`Pipeline status: ${getStatusLabel(statusVariant)}`}
          >
            <span className="dot" />
            {getStatusLabel(statusVariant)}
          </div>
        </div>
      </div>

      <div className="pipeline-card-flow">
        <span>{pipeline.provider}</span>
        <span>·</span>
        <span>{pipeline.model}</span>
      </div>

      <div className="pipeline-card-foot">
        {lastRunTime && <span>{lastRunTime}</span>}
        {lastRunTime && lastExecution && <span>·</span>}
        {lastExecution && (
          <>
            <span>
              {lastExecution.tokens_in} → {lastExecution.tokens_out} tokens
            </span>
            <span>·</span>
            <span>{duration}</span>
          </>
        )}
        {!lastExecution && (
          <span style={{ color: "var(--canvas-fg-4, var(--canvas-fg-3))" }}>{COPY.NO_PIPELINE_RUNS}</span>
        )}
      </div>
    </div>
  );
}
