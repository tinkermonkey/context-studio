import { useState, useMemo } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { usePipelines } from "@/api/hooks/pipeline";
import { PipelineCard } from "@/components/pipeline/PipelineCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import type { components } from "@/api/types";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];

type StatusFilter = "all" | "enabled" | "disabled";

interface PipelinesSearchParams {
  selected?: string;
}

function PipelinesContent() {
  const navigate = useNavigate();
  const { selected: selectedId } = useSearch({ from: "/app/pipelines/" });
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

  const handleNewPipeline = () => {
    navigate({ to: "/app/pipelines" });
  };

  const handlePipelineClick = (pipelineId: string) => {
    navigate({
      to: "/app/pipelines",
      search: (prev: PipelinesSearchParams) => ({ ...prev, selected: pipelineId }),
      replace: true,
    });
  };

  if (isLoading) {
    return (
      <div className="stack">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Skeleton width={200} height={32} />
          <Skeleton width={120} height={32} />
        </div>
        <Skeleton height={40} />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, 1fr)",
            gap: "var(--space-4)",
          }}
        >
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} height={120} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="stack">
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
      <EmptyState
        title="No pipelines yet"
        description="Create your first pipeline to get started with extraction and processing."
        action={{
          label: "Create Pipeline",
          onClick: handleNewPipeline,
        }}
      />
    );
  }

  const hasFilters = !!searchFilter || statusFilter !== "all";
  const showFilteredEmpty = pipelines.length > 0 && filteredPipelines.length === 0 && hasFilters;

  return (
    <div data-testid="pipelines-page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-6)" }}>
        <h1 style={{ margin: 0, fontSize: "var(--text-2xl)", fontWeight: 600 }}>
          Pipelines
        </h1>
        <Button variant="primary" onClick={handleNewPipeline}>
          <Plus size={16} style={{ marginRight: "4px" }} />
          New Pipeline
        </Button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginBottom: "var(--space-6)" }}>
        <Input
          type="text"
          placeholder="Search by name, provider, or model…"
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
          data-testid="pipelines-search-input"
        />
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          {(
            [
              { label: "All", value: "all" },
              { label: "Enabled", value: "enabled" },
              { label: "Disabled", value: "disabled" },
            ] as const
          ).map((option) => (
            <button
              key={option.value}
              onClick={() => setStatusFilter(option.value)}
              style={{
                padding: "4px 12px",
                borderRadius: "var(--radius-md, 6px)",
                border: "1px solid var(--canvas-bd)",
                background:
                  statusFilter === option.value
                    ? "var(--canvas-bg-2)"
                    : "transparent",
                color: "var(--canvas-fg)",
                fontSize: "var(--text-xs)",
                cursor: "pointer",
                fontWeight: statusFilter === option.value ? 600 : 500,
                transition: "background 0.15s",
              }}
              data-testid={`status-filter-${option.value}`}
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
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, 1fr)",
            gap: "var(--space-4)",
          }}
        >
          {filteredPipelines.map((pipeline) => (
            <div
              key={pipeline.id}
              onClick={() => handlePipelineClick(pipeline.id)}
              style={{ cursor: "pointer" }}
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
  validateSearch: (search: Record<string, unknown>): PipelinesSearchParams => ({
    selected: search.selected as string | undefined,
  }),
  component: PipelinesContent,
});
