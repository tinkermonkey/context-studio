import { useNavigate } from "@tanstack/react-router";
import { Button, Icon, Chip } from "@tinkermonkey/heimdall-ui";
import type { components } from "@/api/types";
import "./PipelineTypeCard.css";

type PipelineTypeResponse = components["schemas"]["PipelineTypeResponse"];
type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];

interface PipelineTypeCardProps {
  type: PipelineTypeResponse;
  latestRun?: PipelineRunResponse;
  isRunsLoading?: boolean;
}

type StatusVariant = "emerald" | "rose" | "cyan" | "amber" | "neutral";

const getRunStatusDisplay = (status: string): { label: string; variant: StatusVariant } => {
  switch (status.toUpperCase()) {
    case "COMPLETED":
      return { label: "Completed", variant: "emerald" };
    case "FAILED":
      return { label: "Failed", variant: "rose" };
    case "RUNNING":
      return { label: "Running", variant: "cyan" };
    case "PENDING":
      return { label: "Pending", variant: "amber" };
    default:
      return { label: status, variant: "neutral" };
  }
};

const formatTimestamp = (dateString?: string | null) => {
  if (!dateString) return null;
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
};

export function PipelineTypeCard({ type, latestRun, isRunsLoading }: PipelineTypeCardProps) {
  const navigate = useNavigate();

  const handleCardClick = () => {
    navigate({ to: `/app/pipelines/types/${type.pipeline_type}` });
  };

  const handleRunClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate({ to: `/app/pipelines/types/${type.pipeline_type}/run` });
  };

  const handleCardKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleCardClick();
    }
  };

  const statusDisplay = latestRun ? getRunStatusDisplay(latestRun.status) : null;
  const runTimestamp = latestRun ? formatTimestamp(latestRun.created_at) : null;

  return (
    <div
      className="pipeline-type-card"
      data-testid={`pipeline-type-card-${type.pipeline_type}`}
      role="article"
    >
      <div className="pipeline-card-body" onClick={handleCardClick} onKeyDown={handleCardKeyDown} role="button" tabIndex={0}>
        <div className="pipeline-card-header">
          <div className="pipeline-type-info">
            <div className="pipeline-type-name">{type.pipeline_type}</div>
            <div className="pipeline-description">{type.description}</div>
          </div>
        </div>

        <div className="pipeline-card-footer">
          {isRunsLoading ? (
            <div className="pipeline-skeleton-run-status" />
          ) : latestRun ? (
            <div
              className="pipeline-run-status"
              data-testid={`pipeline-run-status-${type.pipeline_type}`}
            >
              {statusDisplay && (
                <Chip variant={statusDisplay.variant}>
                  {statusDisplay.label}
                </Chip>
              )}
              {runTimestamp && <span className="pipeline-run-timestamp">{runTimestamp}</span>}
            </div>
          ) : (
            <span className="pipeline-no-runs-text">No runs yet</span>
          )}
        </div>
      </div>

      <div className="pipeline-card-actions">
        <Button
          variant="primary"
          size="sm"
          onClick={handleRunClick}
          data-testid={`pipeline-run-button-${type.pipeline_type}`}
          aria-label={`Run ${type.pipeline_type} pipeline`}
        >
          <Icon name="chevronRight" size={14} />
          Run
        </Button>
      </div>
    </div>
  );
}
