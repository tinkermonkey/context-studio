import { useMemo } from "react";
import type { components } from "@/api/types";
import { Cpu } from "lucide-react";
import { usePipelineExecutions } from "@/api/hooks/pipeline";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type ExecutionResponse = components["schemas"]["ExecutionResponse"];

interface PipelineCardProps {
  pipeline: PipelineConfigurationResponse;
  onExecute?: (id: string) => void;
}

type StatusVariant = "success" | "failed" | "idle";

function mapExecutionStatusToVariant(status: ExecutionResponse["status"]): StatusVariant {
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

function getStatusChipColor(variant: StatusVariant): string {
  switch (variant) {
    case "success":
      return "color-mix(in oklab, var(--accent-emerald, #10b981) 15%, transparent)";
    case "failed":
      return "color-mix(in oklab, var(--accent-rose, #f43f5e) 15%, transparent)";
    case "idle":
      return "var(--canvas-bd)";
  }
}

function getStatusChipBorder(variant: StatusVariant): string {
  switch (variant) {
    case "success":
      return "color-mix(in oklab, var(--accent-emerald, #10b981) 30%, transparent)";
    case "failed":
      return "color-mix(in oklab, var(--accent-rose, #f43f5e) 30%, transparent)";
    case "idle":
      return "var(--canvas-bd-2)";
  }
}

function getStatusChipText(variant: StatusVariant): string {
  switch (variant) {
    case "success":
      return "var(--accent-emerald, #10b981)";
    case "failed":
      return "var(--accent-rose, #f43f5e)";
    case "idle":
      return "var(--canvas-fg-3)";
  }
}

function getDotColor(variant: StatusVariant): string {
  switch (variant) {
    case "success":
      return "var(--accent-emerald, #10b981)";
    case "failed":
      return "var(--accent-rose, #f43f5e)";
    case "idle":
      return "transparent";
  }
}

function formatRelativeTime(date: Date): string {
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`;
  }
  const seconds = (ms / 1000).toFixed(1);
  return `${seconds}s`;
}

export function PipelineCard({ pipeline, onExecute }: PipelineCardProps) {
  const { data: executions = [] } = usePipelineExecutions(pipeline.id);

  const lastExecution = useMemo(() => executions[0] || null, [executions]);
  const statusVariant = lastExecution ? mapExecutionStatusToVariant(lastExecution.status) : "idle";
  const lastRunTime = lastExecution ? formatRelativeTime(new Date(lastExecution.timestamp)) : null;
  const duration = lastExecution ? formatDuration(lastExecution.duration_ms) : null;

  const statusLabel = statusVariant === "success" ? "success" : statusVariant === "failed" ? "failed" : null;

  return (
    <div
      className="pipeline-card"
      data-testid={`pipeline-card-${pipeline.id}`}
      style={{
        background: "var(--canvas-card)",
        border: "1px solid var(--canvas-bd)",
        borderRadius: "var(--radius-lg, 10px)",
        padding: "var(--space-4)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3)",
      }}
    >
      {/* Head: Title + Status Chip */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-2)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", minWidth: 0 }}>
          <Cpu size={16} style={{ color: "var(--accent-violet, #7c3aed)", flexShrink: 0 }} />
          <span
            style={{
              fontSize: "var(--text-sm)",
              fontWeight: 600,
              color: "var(--canvas-fg)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {pipeline.title}
          </span>
        </div>

        {/* Status Chip */}
        <div
          data-testid="pipeline-status-chip"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "var(--text-xs)",
            padding: "4px 10px",
            borderRadius: "999px",
            background: getStatusChipColor(statusVariant),
            color: getStatusChipText(statusVariant),
            border: `1px solid ${getStatusChipBorder(statusVariant)}`,
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}
        >
          {/* Status Dot */}
          <span
            style={{
              display: "inline-block",
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              backgroundColor: getDotColor(statusVariant),
            }}
          />
          {statusLabel || "idle"}
        </div>
      </div>

      {/* Flow Strip: Provider · Model */}
      <div
        style={{
          display: "flex",
          gap: "var(--space-2)",
          fontSize: "var(--text-xs)",
          color: "var(--canvas-fg-3)",
          fontFamily: "var(--mono)",
        }}
      >
        <span>{pipeline.provider}</span>
        <span>·</span>
        <span>{pipeline.model}</span>
      </div>

      {/* Footer Stats: Last run · Duration · Tokens */}
      <div
        style={{
          display: "flex",
          gap: "var(--space-2)",
          fontSize: "var(--text-xs)",
          color: "var(--canvas-fg-3)",
          fontFamily: "var(--mono)",
          paddingTop: "var(--space-2)",
          borderTop: "1px solid var(--canvas-bd)",
        }}
      >
        {lastRunTime && <span>{lastRunTime}</span>}
        {lastRunTime && lastExecution && <span>·</span>}
        {lastExecution && (
          <>
            <span>{lastExecution.tokens_in} → {lastExecution.tokens_out} tokens</span>
            <span>·</span>
            <span>{duration}</span>
          </>
        )}
        {!lastExecution && <span style={{ color: "var(--canvas-fg-4, var(--canvas-fg-3))" }}>No runs yet</span>}
      </div>
    </div>
  );
}
