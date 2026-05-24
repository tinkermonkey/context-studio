import { Button, Chip, PageHeader, FilterBar, SegmentedControl } from "@tinkermonkey/heimdall-ui";
import { useState, useMemo } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ExternalLink } from "lucide-react";
import { useAllPipelineExecutions } from "@/api/hooks/pipeline";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";

import { getStatusColor } from "@/utils/statusColorUtils";
import { COPY } from "./-copy";
import type { components } from "@/api/types";

type ExecutionWithPipeline = components["schemas"]["ExecutionWithPipelineResponse"];

type StatusFilter = "all" | "success" | "error" | "timeout";

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds % 60}s`;
}

function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleString();
}

function RunsPageContent() {
  const navigate = useNavigate();
  const [searchFilter, setSearchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [currentPage, setCurrentPage] = useState(0);
  const pageSize = 50;

  const {
    data: executionsResponse,
    isLoading,
    error,
    refetch,
  } = useAllPipelineExecutions(
    statusFilter !== "all" ? statusFilter : undefined,
    pageSize,
    currentPage * pageSize,
  );

  const executions = useMemo(() => executionsResponse?.items || [], [executionsResponse?.items]);
  const totalCount = executionsResponse?.total || 0;

  const filteredExecutions = useMemo(() => {
    if (!searchFilter) return executions;
    const query = searchFilter.toLowerCase();
    return executions.filter(
      (exec) =>
        exec.pipeline_title.toLowerCase().includes(query) || exec.id.toLowerCase().includes(query),
    );
  }, [executions, searchFilter]);

  const runColumns: Column<ExecutionWithPipeline>[] = [
    {
      key: "status",
      label: COPY.RUN_STATUS_HEADER,
      width: "100px",
      render: (value) => {
        const status = value as ExecutionWithPipeline["status"];
        return (
          <Chip variant={getStatusColor(status)} data-testid={`status-chip-${status}`}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </Chip>
        );
      },
    },
    {
      key: "pipeline_title",
      label: COPY.RUN_PIPELINE_HEADER,
      render: (value, row) => (
        <span
          className="text-cyan-400 font-medium cursor-pointer"
          onClick={() => navigate({ to: `/app/pipelines/${row.pipeline_config_id}` })}
          data-testid={`pipeline-link-${row.pipeline_config_id}`}
          role="button"
        >
          {value as string}
        </span>
      ),
    },
    {
      key: "timestamp",
      label: COPY.RUN_STARTED_HEADER,
      render: (value, row) => {
        const timestamp = value as string;
        return (
          <span title={formatTimestamp(timestamp)} data-testid={`timestamp-${row.id}`}>
            {new Date(timestamp).toLocaleDateString()}
          </span>
        );
      },
    },
    {
      key: "duration_ms",
      label: COPY.RUN_DURATION_HEADER,
      render: (value, row) => (
        <code className="font-mono text-xs" data-testid={`duration-${row.id}`}>
          {formatDuration(value as number)}
        </code>
      ),
    },
    {
      key: "id",
      label: COPY.RUN_TOKENS_HEADER,
      render: (_, row) => {
        const total = (row.tokens_in || 0) + (row.tokens_out || 0);
        return (
          <code className="font-mono text-xs" data-testid={`tokens-${row.id}`}>
            {total}
          </code>
        );
      },
    },
    {
      key: "id",
      label: "",
      width: "60px",
      render: (_, row) => (
        <a
          href={`/app/pipelines/${row.pipeline_config_id}?execution=${row.id}`}
          data-testid={`view-log-${row.id}`}
          className="flex items-center gap-1 text-xs opacity-60 hover:opacity-100"
        >
          {COPY.PIPELINE_VIEW_LOG}
          <ExternalLink size={12} />
        </a>
      ),
    },
  ];

  if (isLoading) {
    return (
      <div data-testid="pipeline-runs-page" className="stack">
        <Skeleton height={32} width={200} />
        <Skeleton height={40} />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} height={40} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="pipeline-runs-page" className="stack">
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message={COPY.RUNS_LOAD_ERROR}
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  }

  const hasFilters = !!searchFilter || statusFilter !== "all";
  const showFilteredEmpty = totalCount > 0 && filteredExecutions.length === 0 && hasFilters;

  return (
    <div data-testid="pipeline-runs-page" className="stack">
      <PageHeader
        eyebrow="Pipelines"
        title={COPY.RUN_HISTORY_PAGE_TITLE}
        idChip="/pipelines/runs"
      />

      <FilterBar
        searchPlaceholder={COPY.SEARCH_RUNS_PLACEHOLDER}
        onSearchChange={(v) => {
          setSearchFilter(v);
          setCurrentPage(0);
        }}
        showingCount={filteredExecutions.length}
        totalCount={totalCount}
        data-testid="runs-filter-bar"
      />

      <SegmentedControl
        value={statusFilter}
        onChange={(v) => {
          setStatusFilter(v as StatusFilter);
          setCurrentPage(0);
        }}
        options={[
          { value: "all", label: COPY.FILTER_ALL },
          { value: "success", label: COPY.STATUS_FILTER_SUCCESS },
          { value: "error", label: COPY.STATUS_FILTER_ERROR },
          { value: "timeout", label: COPY.STATUS_FILTER_TIMEOUT },
        ]}
        aria-label={COPY.FILTER_RUNS_LABEL}
        data-testid="runs-status-filter"
      />

      {totalCount === 0 ? (
        <EmptyState title={COPY.NO_RUNS_TITLE} description={COPY.NO_RUNS_DESCRIPTION} />
      ) : showFilteredEmpty ? (
        <EmptyState
          title={COPY.NO_RUNS_FILTERED_TITLE}
          description={COPY.NO_RUNS_FILTERED_DESCRIPTION}
        />
      ) : (
        <>
          <div data-testid="pipeline-runs-table">
            <SchemaTable columns={runColumns} data={filteredExecutions} testIdPrefix="run" />
          </div>

          {totalCount > pageSize && (
            <div className="flex items-center justify-center gap-4">
              <Button
                variant="ghost"
                disabled={currentPage === 0}
                onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                data-testid="pagination-prev"
              >
                {COPY.PAGINATION_PREVIOUS}
              </Button>
              <span className="text-xs opacity-60">
                Page {currentPage + 1} of {Math.ceil(totalCount / pageSize)}
              </span>
              <Button
                variant="ghost"
                disabled={(currentPage + 1) * pageSize >= totalCount}
                onClick={() => setCurrentPage(currentPage + 1)}
                data-testid="pagination-next"
              >
                {COPY.PAGINATION_NEXT}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export const Route = createFileRoute("/app/pipelines/runs")({
  component: RunsPageContent,
});
