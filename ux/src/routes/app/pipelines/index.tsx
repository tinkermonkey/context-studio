import { useState, useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { usePipelines } from "@/api/hooks/pipeline";
import { PipelineCard } from "@/components/pipeline/PipelineCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";

type StatusFilter = "all" | "enabled" | "disabled";

function PipelinesContent() {
  const { data: pipelines = [], isLoading, error, refetch } = usePipelines();
  const [searchFilter, setSearchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const filteredPipelines = useMemo(() => {
    let result = pipelines;

    if (searchFilter) {
      const query = searchFilter.toLowerCase();
      result = result.filter(
        (p) =>
          p.title.toLowerCase().includes(query) ||
          p.pipeline.toLowerCase().includes(query) ||
          p.provider.toLowerCase().includes(query) ||
          p.model.toLowerCase().includes(query)
      );
    }

    if (statusFilter !== "all") {
      result = result.filter((p) =>
        statusFilter === "enabled" ? p.enabled : !p.enabled
      );
    }

    return result.sort(
      (a, b) =>
        new Date(b.last_updated).getTime() - new Date(a.last_updated).getTime()
    );
  }, [pipelines, searchFilter, statusFilter]);

  if (isLoading) {
    return (
      <div data-testid="pipelines-page" className="stack">
        <div className="flex-between">
          <Skeleton width={200} height={32} />
          <Skeleton width={120} height={32} />
        </div>
        <Skeleton height={40} />
        <div className="grid-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} height={120} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="pipelines-page" className="stack">
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message="Failed to load pipelines"
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  }

  if (pipelines.length === 0) {
    return (
      <div data-testid="pipelines-page">
        <EmptyState
          title="No pipelines yet"
          description="Create your first pipeline to get started with extraction and processing."
          action={{
            label: "Create Pipeline",
            onClick: () => {
              /* Pipeline creation route not yet implemented */
            },
          }}
        />
      </div>
    );
  }

  const hasFilters = !!searchFilter || statusFilter !== "all";
  const showFilteredEmpty = pipelines.length > 0 && filteredPipelines.length === 0 && hasFilters;

  return (
    <div data-testid="pipelines-page">
      <div className="page-head">
        <h1>Pipelines</h1>
        <Button
          variant="primary"
          disabled
          title="Pipeline creation is not yet implemented"
        >
          <Plus size={16} style={{ marginRight: "4px" }} />
          New Pipeline
        </Button>
      </div>

      <div className="stack" style={{ marginBottom: "var(--space-6)" }}>
        <Input
          type="text"
          placeholder="Search by name, provider, or model…"
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
          data-testid="pipelines-search-input"
        />
        <div
          role="radiogroup"
          aria-label="Filter pipelines by status"
          style={{ display: "flex", gap: "var(--space-2)" }}
        >
          {(
            [
              { label: "All", value: "all" },
              { label: "Enabled", value: "enabled" },
              { label: "Disabled", value: "disabled" },
            ] as const
          ).map((option) => (
            <button
              key={option.value}
              role="radio"
              aria-checked={statusFilter === option.value}
              onClick={() => setStatusFilter(option.value)}
              className="status-filter-chip"
              data-testid={`status-filter-${option.value}`}
              data-active={statusFilter === option.value}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {showFilteredEmpty ? (
        <EmptyState
          title="No pipelines match your filters"
          description="Try adjusting your search or filter criteria."
        />
      ) : (
        <div
          data-testid="pipelines-grid"
          className="grid-2"
        >
          {filteredPipelines.map((pipeline) => (
            <div
              key={pipeline.id}
              data-testid={`pipeline-card-${pipeline.id}`}
            >
              <PipelineCard pipeline={pipeline} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export const Route = createFileRoute("/app/pipelines/")({
  component: PipelinesContent,
});
