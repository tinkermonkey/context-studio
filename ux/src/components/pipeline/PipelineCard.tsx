import type { components } from "@/api/types";
import { Play, Loader, FileText, Zap, Link, HardDrive } from "lucide-react";
import { usePipelineExecutions, useExecutePipeline } from "@/api/hooks/pipeline";
import { formatRelativeTime, formatDuration } from "@/utils/formatters";
import { Button } from "@tinkermonkey/heimdall-ui";
import { Chip, type ChipColor } from "@/components/ui/Chip";
import { useToasts } from "@/components/ui/Toast";
import { useExecutionStore } from "@/stores/executionStore";
import { COPY } from "@/routes/app/pipelines/-copy";
import type { ReactNode } from "react";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type ExecutionResponse = components["schemas"]["ExecutionResponse"];

interface PipelineCardProps {
  pipeline: PipelineConfigurationResponse;
}

type StatusVariant = "success" | "failed" | "idle" | "disabled" | "running";
type StageKind = "source" | "extract" | "resolve" | "write";

interface Stage {
  kind: StageKind;
  label: string;
  sub: string;
  icon: ReactNode;
}

const PIPELINE_STAGES: Record<string, Stage[]> = {
  individual_extraction: [
    { kind: "source", label: "Input", sub: "text", icon: <FileText size={13} /> },
    { kind: "extract", label: "Extract", sub: "llm", icon: <Zap size={13} /> },
    { kind: "write", label: "Store", sub: "graph", icon: <HardDrive size={13} /> },
  ],
  schema_extraction: [
    { kind: "source", label: "Schema", sub: "nodes", icon: <FileText size={13} /> },
    { kind: "extract", label: "Analyze", sub: "llm", icon: <Zap size={13} /> },
    { kind: "resolve", label: "Ground", sub: "refs", icon: <Link size={13} /> },
    { kind: "write", label: "Store", sub: "graph", icon: <HardDrive size={13} /> },
  ],
  schema_node_grounding: [
    { kind: "source", label: "Nodes", sub: "schema", icon: <FileText size={13} /> },
    { kind: "resolve", label: "Ground", sub: "llm", icon: <Link size={13} /> },
    { kind: "write", label: "Apply", sub: "graph", icon: <HardDrive size={13} /> },
  ],
  schema_node_definition_refinement: [
    { kind: "source", label: "Nodes", sub: "schema", icon: <FileText size={13} /> },
    { kind: "extract", label: "Refine", sub: "llm", icon: <Zap size={13} /> },
    { kind: "write", label: "Apply", sub: "graph", icon: <HardDrive size={13} /> },
  ],
  schema_node_connection_refinement: [
    { kind: "source", label: "Edges", sub: "schema", icon: <FileText size={13} /> },
    { kind: "resolve", label: "Connect", sub: "llm", icon: <Link size={13} /> },
    { kind: "write", label: "Apply", sub: "graph", icon: <HardDrive size={13} /> },
  ],
};

function getDefaultStages(pipeline: PipelineConfigurationResponse): Stage[] {
  return [
    { kind: "source", label: pipeline.provider, sub: "provider", icon: <FileText size={13} /> },
    { kind: "extract", label: pipeline.model, sub: "model", icon: <Zap size={13} /> },
  ];
}

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

function getStatusChipColor(variant: StatusVariant): ChipColor {
  switch (variant) {
    case "success":
      return "emerald";
    case "failed":
      return "rose";
    case "disabled":
    case "idle":
      return "gray";
    case "running":
      return "cyan";
  }
}

function getStatusLabel(variant: StatusVariant): string {
  return variant;
}

export function PipelineCard({ pipeline }: PipelineCardProps) {
  const { data: executions = [] } = usePipelineExecutions(pipeline.id);
  const executeMutation = useExecutePipeline();
  const { toast } = useToasts();
  const { startExecution, endExecution } = useExecutionStore();
  const isRunning = useExecutionStore((state) => state.inFlightPipelineIds.has(pipeline.id));

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
  const statusVariant = isRunning
    ? "running"
    : lastExecution
      ? mapExecutionStatusToVariant(lastExecution.status, pipeline.enabled)
      : !pipeline.enabled
        ? "disabled"
        : "idle";
  const lastRunTime = lastExecution ? formatRelativeTime(new Date(lastExecution.timestamp)) : null;
  const duration = lastExecution ? formatDuration(lastExecution.duration_ms) : null;
  const stages = PIPELINE_STAGES[pipeline.pipeline] ?? getDefaultStages(pipeline);

  return (
    <div className="pipeline-card" data-testid={`pipeline-card-${pipeline.id}`}>
      <div className="pipeline-card-head">
        <span className="name">{pipeline.title}</span>
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
            {executeMutation.isPending ? <Loader size={16} className="spin" /> : <Play size={16} />}
          </Button>
          <Chip
            color={getStatusChipColor(statusVariant)}
            data-testid="pipeline-status-chip"
            role="status"
            aria-label={`Pipeline status: ${getStatusLabel(statusVariant)}`}
          >
            {getStatusLabel(statusVariant)}
          </Chip>
        </div>
      </div>

      <div className="pipeline-card-flow">
        {stages.map((stage, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 0, flex: "none" }}>
            <div className="flow-node" data-kind={stage.kind}>
              <div className="ic">{stage.icon}</div>
              <div>
                <div className="name">{stage.label}</div>
                <div className="sub">{stage.sub}</div>
              </div>
            </div>
            {i < stages.length - 1 && <div className="flow-arrow" />}
          </div>
        ))}
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
          <span className="muted">{COPY.NO_PIPELINE_RUNS}</span>
        )}
      </div>
    </div>
  );
}
