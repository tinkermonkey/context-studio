import type { components } from "@/api/types";
import { usePipelineExecutions, useExecutePipeline } from "@/api/hooks/pipeline";
import { formatRelativeTime, formatDuration } from "@/utils/formatters";
import { PipelineCard as HeimdallPipelineCard, Button, type FlowNode } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useExecutionStore } from "@/stores/executionStore";
import { COPY } from "@/routes/app/pipelines/-copy";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type ExecutionResponse = components["schemas"]["ExecutionResponse"];

type PipelineStatus = "running" | "success" | "idle" | "failed";

const PIPELINE_FLOW: Record<string, FlowNode[]> = {
  individual_extraction: [
    { id: "source", name: "Input", label: "text", icon: "data" },
    { id: "extract", name: "Extract", label: "llm", icon: "pipeline" },
    { id: "write", name: "Store", label: "graph", icon: "schema" },
  ],
  schema_extraction: [
    { id: "source", name: "Schema", label: "nodes", icon: "schema" },
    { id: "extract", name: "Analyze", label: "llm", icon: "pipeline" },
    { id: "resolve", name: "Ground", label: "refs", icon: "link" },
    { id: "write", name: "Store", label: "graph", icon: "data" },
  ],
  schema_node_grounding: [
    { id: "source", name: "Nodes", label: "schema", icon: "schema" },
    { id: "resolve", name: "Ground", label: "llm", icon: "link" },
    { id: "write", name: "Apply", label: "graph", icon: "data" },
  ],
  schema_node_definition_refinement: [
    { id: "source", name: "Nodes", label: "schema", icon: "schema" },
    { id: "extract", name: "Refine", label: "llm", icon: "pipeline" },
    { id: "write", name: "Apply", label: "graph", icon: "data" },
  ],
  schema_node_connection_refinement: [
    { id: "source", name: "Edges", label: "schema", icon: "schema" },
    { id: "resolve", name: "Connect", label: "llm", icon: "link" },
    { id: "write", name: "Apply", label: "graph", icon: "data" },
  ],
};

function getDefaultFlow(pipeline: PipelineConfigurationResponse): FlowNode[] {
  return [
    { id: "provider", name: pipeline.provider, label: "provider", icon: "settings" },
    { id: "model", name: pipeline.model, label: "model", icon: "pipeline" },
  ];
}

function mapStatus(
  execution: ExecutionResponse | undefined,
  isRunning: boolean,
  enabled: boolean,
): PipelineStatus {
  if (isRunning) return "running";
  if (!enabled) return "idle";
  if (!execution) return "idle";
  if (execution.status === "success") return "success";
  if (execution.status === "error" || execution.status === "timeout") return "failed";
  return "idle";
}

interface PipelineCardProps {
  pipeline: PipelineConfigurationResponse;
  selected?: boolean;
  onClick?: () => void;
}

export function PipelineCard({ pipeline, selected, onClick }: PipelineCardProps) {
  const { data: executions = [] } = usePipelineExecutions(pipeline.id);
  const executeMutation = useExecutePipeline();
  const { toast } = useToasts();
  const { startExecution, endExecution } = useExecutionStore();
  const isRunning = useExecutionStore((state) => state.inFlightPipelineIds.has(pipeline.id));

  const handleRun = async () => {
    try {
      startExecution(pipeline.id);
      const execution = await executeMutation.mutateAsync({ id: pipeline.id, inputText: "" });
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

  const lastExecution = executions[0] ?? undefined;
  const status = mapStatus(lastExecution, isRunning, pipeline.enabled);
  const flow = PIPELINE_FLOW[pipeline.pipeline] ?? getDefaultFlow(pipeline);

  const lastRunTime = lastExecution ? formatRelativeTime(new Date(lastExecution.timestamp)) : null;
  const duration = lastExecution ? formatDuration(lastExecution.duration_ms) : null;

  const errors = lastExecution?.status === "error" || lastExecution?.status === "timeout" ? 1 : 0;

  const footerContent = lastExecution ? (
    <span className="muted">
      {lastRunTime} · {lastExecution.tokens_in} → {lastExecution.tokens_out} tokens · {duration}
    </span>
  ) : (
    <span className="muted">{COPY.NO_PIPELINE_RUNS}</span>
  );

  return (
    <HeimdallPipelineCard
      data-testid={`pipeline-card-${pipeline.id}`}
      selected={selected}
      onClick={onClick}
      onRun={handleRun}
      pipeline={{
        id: pipeline.id,
        name: pipeline.title,
        description: `${pipeline.provider} · ${pipeline.model}`,
        status,
        flow,
        recent: {
          ingested: 0,
          created: 0,
          updated: 0,
          errors,
        },
        lastRun: lastExecution?.timestamp,
      }}
      footerContent={footerContent}
    />
  );
}
