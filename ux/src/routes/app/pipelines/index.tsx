import { Button, TextInput as Input } from "@tinkermonkey/heimdall-ui";
import { useState, useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { usePipelines, useAllPipelineExecutions } from "@/api/hooks/pipeline";
import { PipelineCard } from "@/components/pipeline/PipelineCard";


import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { COPY } from "./-copy";

type StatusFilter = "all" | "enabled" | "disabled";

export function PipelinesContent() {
  const { data: pipelines = [], isLoading, error, refetch } = usePipelines();
  const { data: allExecutions, error: executionsError } = useAllPipelineExecutions(undefined, 50);
  const [searchFilter, setSearchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const filteredPipelines = useMemo(() => {
    const getPipelineFailedStatus = (pipelineId: string): boolean => {
      if (!allExecutions?.items) return false;
      const executionsForPipeline = allExecutions.items.filter(
        (e) => e.pipeline_config_id === pipelineId,
      );
      if (executionsForPipeline.length === 0) return false;
      const latestExecution = executionsForPipeline.reduce((latest, current) =>
        new Date(current.timestamp).getTime() > new Date(latest.timestamp).getTime()
          ? current
          : latest,
      );
      return latestExecution.status === "error" || latestExecution.status === "timeout";
    };

    let result = pipelines;

    if (searchFilter) {
      const query = searchFilter.toLowerCase();
      result = result.filter(
        (p) =>
          p.title.toLowerCase().includes(query) ||
          p.pipeline.toLowerCase().includes(query) ||
          p.provider.toLowerCase().includes(query) ||
          p.model.toLowerCase().includes(query),
      );
    }

    if (statusFilter !== "all") {
      result = result.filter((p) => (statusFilter === "enabled" ? p.enabled : !p.enabled));
    }

    return result.sort((a, b) => {
      const aFailed = getPipelineFailedStatus(a.id) ? 1 : 0;
      const bFailed = getPipelineFailedStatus(b.id) ? 1 : 0;

      if (aFailed !== bFailed) {
        return bFailed - aFailed;
      }

      return new Date(b.last_updated).getTime() - new Date(a.last_updated).getTime();
    });
  }, [pipelines, searchFilter, statusFilter, allExecutions]);

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
          message={COPY.PIPELINES_LOAD_ERROR}
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  }

  if (pipelines.length === 0) {
    return (
      <div data-testid="pipelines-page">
        <EmptyState
          title={COPY.NO_PIPELINES_TITLE}
          description={COPY.NO_PIPELINES_DESCRIPTION}
          action={{
            label: COPY.CREATE_PIPELINE_CTA,
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
        <h1>{COPY.PIPELINES_PAGE_TITLE}</h1>
        <Button variant="primary" disabled title="Pipeline creation is not yet implemented">
          <Plus size={16} style={{ marginRight: "4px" }} />
          {COPY.NEW_PIPELINE_BUTTON}
        </Button>
      </div>

      <div className="stack" style={{ marginBottom: "var(--space-6)" }}>
        <Input
          type="text"
          placeholder={COPY.SEARCH_PIPELINES_PLACEHOLDER}
          value={searchFilter}
          onChange={(e) => setSearchFilter(e.target.value)}
          data-testid="pipelines-search-input"
        />
        <div
          role="radiogroup"
          aria-label={COPY.FILTER_PIPELINES_LABEL}
          style={{ display: "flex", gap: "var(--space-2)" }}
        >
          {(
            [
              { label: COPY.FILTER_ALL, value: "all" },
              { label: COPY.FILTER_ENABLED, value: "enabled" },
              { label: COPY.FILTER_DISABLED, value: "disabled" },
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

      {executionsError && (
        <div style={{ marginBottom: "var(--space-6)" }}>
          <ErrorBanner
            error={executionsError}
            message={COPY.EXECUTIONS_LOAD_ERROR}
            daemonLogPath="/local-server/logs/context_studio.log"
          />
        </div>
      )}

      {showFilteredEmpty ? (
        <EmptyState
          title={COPY.NO_PIPELINES_FILTERED_TITLE}
          description={COPY.NO_PIPELINES_FILTERED_DESCRIPTION}
        />
      ) : (
        <div data-testid="pipelines-grid" className="grid-2">
          {filteredPipelines.map((pipeline) => (
            <PipelineCard key={pipeline.id} pipeline={pipeline} />
          ))}
        </div>
      )}
    </div>
  );
}

export const Route = createFileRoute("/app/pipelines/")({
  component: PipelinesContent,
});
