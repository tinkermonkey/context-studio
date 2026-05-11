import type { components } from "@/api/types";
import { Cpu } from "lucide-react";
import { usePipelineExecutions } from "@/api/hooks/pipeline";
import { formatRelativeTime, formatDuration } from "@/utils/formatters";

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
          <span style={{ color: "var(--canvas-fg-4, var(--canvas-fg-3))" }}>No runs yet</span>
        )}
      </div>
    </div>
  );
}
