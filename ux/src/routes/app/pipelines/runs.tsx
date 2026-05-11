import { useState, useMemo } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { ExternalLink } from "lucide-react";
import { useAllPipelineExecutions, usePipelines } from "@/api/hooks/pipeline";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
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

  const { data: pipelines = [] } = usePipelines();
  const pipelineMap = new Map(pipelines.map((p) => [p.id, p.title]));

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

  const executions = executionsResponse?.items || [];
  const totalCount = executionsResponse?.total || 0;

  const filteredExecutions = useMemo(() => {
    if (!searchFilter) return executions;
    const query = searchFilter.toLowerCase();
    return executions.filter(
      (exec) =>
        exec.pipeline_title.toLowerCase().includes(query) ||
        exec.id.toLowerCase().includes(query),
    );
  }, [executions, searchFilter]);

  const runColumns: ColumnDef<ExecutionWithPipeline>[] = [
    {
      accessorKey: "status",
      header: "Status",
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
      header: "Pipeline",
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
      header: "Started",
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
      header: "Duration",
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
      header: "Records",
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
          View log
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
          message="Failed to load pipeline runs"
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  } else if (totalCount === 0) {
    content = (
      <EmptyState
        title="No pipeline runs yet"
        description="Execute a pipeline to see run history here."
      />
    );
  } else {
    const hasFilters = !!searchFilter || statusFilter !== "all";
    const showFilteredEmpty = totalCount > 0 && filteredExecutions.length === 0 && hasFilters;

    content = (
      <>
        <div className="page-head">
          <h1>Run History</h1>
        </div>

        <div className="stack runs-filter-bar">
          <Input
            type="text"
            placeholder="Search by pipeline name…"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            data-testid="runs-search-input"
          />
          <div
            role="radiogroup"
            aria-label="Filter runs by status"
            className="runs-filter-group"
          >
            {(
              [
                { label: "All", value: "all" },
                { label: "Success", value: "success" },
                { label: "Error", value: "error" },
                { label: "Timeout", value: "timeout" },
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
            title="No runs match your filter"
            description="Try adjusting your search or filter criteria."
          />
        ) : (
          <>
            <div data-testid="pipeline-runs-table">
              <SchemaTable
                columns={runColumns}
                data={filteredExecutions}
                testIdPrefix="run"
              />
            </div>

            {totalCount > pageSize && (
              <div className="runs-pagination-container">
                <Button
                  variant="ghost"
                  disabled={currentPage === 0}
                  onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                  data-testid="pagination-prev"
                >
                  Previous
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
                  Next
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
