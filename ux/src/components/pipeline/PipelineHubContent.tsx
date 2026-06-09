import { PipelineTypeCard } from "./PipelineTypeCard";
import type { components } from "@/api/types";
import "./PipelineHubContent.css";

type PipelineTypeResponse = components["schemas"]["PipelineTypeResponse"];
type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];

interface PipelineHubContentProps {
  types: PipelineTypeResponse[];
  runsByType: Map<string, PipelineRunResponse>;
  isLoading: boolean;
  isRunsLoading: boolean;
}

export function PipelineHubContent({
  types,
  runsByType,
  isLoading,
  isRunsLoading,
}: PipelineHubContentProps) {
  if (isLoading) {
    return (
      <div
        className="pipeline-hub-grid"
        data-testid="pipeline-types-grid"
        role="region"
        aria-label="Pipeline types loading"
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={`skeleton-${i}`} className="pipeline-skeleton-card" />
        ))}
      </div>
    );
  }

  return (
    <div
      className="pipeline-hub-grid"
      data-testid="pipeline-types-grid"
      role="region"
      aria-label="Pipeline types"
    >
      {types.map((type) => (
        <PipelineTypeCard
          key={type.pipeline_type}
          type={type}
          latestRun={runsByType.get(type.pipeline_type)}
          isRunsLoading={isRunsLoading}
        />
      ))}
    </div>
  );
}
