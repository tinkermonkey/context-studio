import { useState, useMemo } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { ExternalLink } from "lucide-react";
import { useAllPipelineExecutions } from "@/api/hooks/pipeline";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { COPY } from "./-copy";
import type { components } from "@/api/types";

type ExecutionWithPipeline = components["schemas"]["ExecutionWithPipelineResponse"];

type StatusFilter = "all" | "success" | "error" | "timeout" | "running";

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

type ChipColor = "emerald" | "rose" | "amber" | "gray";

function getStatusColor(status: string): ChipColor {
  switch (status) {
    case "success":
      return "emerald";
    case "error":
      return "rose";
    case "timeout":
      return "amber";
    default:
      return "gray";
  }
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

  const runColumns: ColumnDef<ExecutionWithPipeline>[] = [
    {
      accessorKey: "status",
      header: COPY.RUN_STATUS_HEADER,
      size: 100,
      cell: (info) => {
        const status = info.getValue() as string;
        return (
          <Chip color={getStatusColor(status)} data-testid={`status-chip-${status}`}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </Chip>
        );
      },
    },
    {
      accessorKey: "pipeline_title",
      header: COPY.RUN_PIPELINE_HEADER,
      cell: (info) => {
        const title = info.getValue() as string;
        const pipelineId = info.row.original.pipeline_config_id;
        return (
          <span
            className="runs-pipeline-link"
            onClick={() => navigate({ to: `/app/pipelines/${pipelineId}` })}
            data-testid={`pipeline-link-${pipelineId}`}
            role="button"
          >
            {title}
          </span>
        );
      },
    },
    {
      accessorKey: "timestamp",
      header: COPY.RUN_STARTED_HEADER,
      cell: (info) => {
        const timestamp = info.getValue() as string;
        return (
          <span
            title={formatTimestamp(timestamp)}
            data-testid={`timestamp-${info.row.original.id}`}
          >
            {new Date(timestamp).toLocaleDateString()}
          </span>
        );
      },
    },
    {
      accessorKey: "duration_ms",
      header: COPY.RUN_DURATION_HEADER,
      cell: (info) => {
        const duration = info.getValue() as number;
        return (
          <span className="mono" data-testid={`duration-${info.row.original.id}`}>
            {formatDuration(duration)}
          </span>
        );
      },
    },
    {
      id: "tokens",
      header: COPY.RUN_TOKENS_HEADER,
      cell: ({ row }) => {
        const total = (row.original.tokens_in || 0) + (row.original.tokens_out || 0);
        return (
          <span className="mono" data-testid={`tokens-${row.original.id}`}>
            {total}
          </span>
        );
      },
    },
    {
      id: "actions",
      header: "",
      size: 60,
      cell: ({ row }) => (
        <a
          href={`/app/pipelines/${row.original.pipeline_config_id}?execution=${row.original.id}`}
          data-testid={`view-log-${row.original.id}`}
          className="runs-view-log-link"
        >
          {COPY.PIPELINE_VIEW_LOG}
          <ExternalLink size={12} />
        </a>
      ),
    },
  ];

  let content;

  if (isLoading) {
    content = (
      <div className="stack">
        <Skeleton height={32} width={200} />
        <Skeleton height={40} />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} height={40} />
        ))}
      </div>
    );
  } else if (error) {
    content = (
      <div className="stack">
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message={COPY.RUNS_LOAD_ERROR}
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  } else if (totalCount === 0) {
    content = <EmptyState title={COPY.NO_RUNS_TITLE} description={COPY.NO_RUNS_DESCRIPTION} />;
  } else {
    const hasFilters = !!searchFilter || statusFilter !== "all";
    const showFilteredEmpty = totalCount > 0 && filteredExecutions.length === 0 && hasFilters;

    content = (
      <>
        <div className="page-head">
          <h1>{COPY.RUN_HISTORY_PAGE_TITLE}</h1>
        </div>

        <div className="stack runs-filter-bar">
          <Input
            type="text"
            placeholder={COPY.SEARCH_RUNS_PLACEHOLDER}
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            data-testid="runs-search-input"
          />
          <div role="radiogroup" aria-label={COPY.FILTER_RUNS_LABEL} className="runs-filter-group">
            {(
              [
                { label: COPY.FILTER_ALL, value: "all" },
                { label: COPY.STATUS_FILTER_SUCCESS, value: "success" },
                { label: COPY.STATUS_FILTER_ERROR, value: "error" },
                { label: COPY.STATUS_FILTER_TIMEOUT, value: "timeout" },
              ] as const
            ).map((option) => (
              <button
                key={option.value}
                role="radio"
                aria-checked={statusFilter === option.value}
                onClick={() => {
                  setStatusFilter(option.value);
                  setCurrentPage(0);
                }}
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
            title={COPY.NO_RUNS_FILTERED_TITLE}
            description={COPY.NO_RUNS_FILTERED_DESCRIPTION}
          />
        ) : (
          <>
            <div data-testid="pipeline-runs-table">
              <SchemaTable columns={runColumns} data={filteredExecutions} testIdPrefix="run" />
            </div>

            {totalCount > pageSize && (
              <div className="runs-pagination-container">
                <Button
                  variant="ghost"
                  disabled={currentPage === 0}
                  onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                  data-testid="pagination-prev"
                >
                  {COPY.PAGINATION_PREVIOUS}
                </Button>
                <span className="runs-page-counter">
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
      </>
    );
  }

  return <div data-testid="pipeline-runs-page">{content}</div>;
}

export const Route = createFileRoute("/app/pipelines/runs")({
  component: RunsPageContent,
});
