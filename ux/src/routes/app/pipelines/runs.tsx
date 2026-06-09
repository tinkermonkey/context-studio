import { useState, useMemo } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import {
  Button,
  PageHeader,
  Icon,
  Chip,
  StatusBadge,
  FilterDropdown,
} from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { RunDetailDrawer } from "@/components/pipeline/RunDetailDrawer";
import { usePipelineTypes } from "@/api/hooks/pipeline/usePipelineTypes";
import { usePipelineRuns } from "@/api/hooks/pipeline/usePipelineRuns";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";
import { formatDate } from "@/utils/dateFormatting";
import type { RunListParams } from "@/api/services/pipeline";
import "./runs.css";

interface RunsSearchParams {
  selected?: string;
}

interface FilterState {
  pipelineType?: string;
  status?: string;
  startDate?: string;
  endDate?: string;
  implementation?: string;
  applied?: "applied" | "not-applied";
}

const PAGE_SIZE = 20;
const PIPELINE_STATUS_OPTIONS = [
  { value: "PENDING", label: "Pending" },
  { value: "RUNNING", label: "Running" },
  { value: "COMPLETED", label: "Completed" },
  { value: "FAILED", label: "Failed" },
];

function RunsPageContent({
  selectedId,
  onSelectedIdChange,
}: {
  selectedId?: string;
  onSelectedIdChange: (id: string | undefined) => void;
}) {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<FilterState>({});
  const [pageIndex, setPageIndex] = useState(0);

  const { data: typesData } = usePipelineTypes();
  const types = typesData || [];

  const { data: implementationsData } = usePipelineImplementations(filters.pipelineType || "");
  const implementations = implementationsData || [];

  const listParams: RunListParams = useMemo(() => {
    const params: RunListParams = {
      limit: PAGE_SIZE,
      offset: pageIndex * PAGE_SIZE,
    };
    if (filters.pipelineType) {
      params.pipeline_type = filters.pipelineType;
    }
    if (filters.status) {
      params.status = filters.status;
    }
    if (filters.startDate) {
      params.start_date = filters.startDate;
    }
    if (filters.endDate) {
      params.end_date = filters.endDate;
    }
    if (filters.implementation) {
      params.implementation_id = filters.implementation;
    }
    if (filters.applied) {
      params.applied = filters.applied;
    }
    return params;
  }, [filters, pageIndex]);

  const { data: runsResponse, isLoading, error, refetch } = usePipelineRuns(listParams);
  const runs = runsResponse?.items || [];
  const total = runsResponse?.total || 0;
  const pageCount = Math.ceil(total / PAGE_SIZE);

  const handleFilterChange = (newFilters: Partial<FilterState>) => {
    setFilters((prev) => ({ ...prev, ...newFilters }));
    setPageIndex(0);
  };

  if (isLoading && runs.length === 0) {
    return (
      <div className="stack">
        <div className="skeleton runs-loading-header" />
        <div className="skeleton runs-loading-row" />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton runs-loading-row" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="stack">
        <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load runs" />
      </div>
    );
  }

  const hasFilters = !!(
    filters.pipelineType ||
    filters.status ||
    filters.startDate ||
    filters.endDate ||
    filters.implementation ||
    filters.applied
  );
  const isGenuinelyEmpty = total === 0 && !hasFilters;
  const isFilteredEmpty = total === 0 && hasFilters;

  if (isGenuinelyEmpty && !isLoading) {
    return (
      <EmptyState
        title="No pipeline runs yet"
        description="Start your first pipeline run to see execution history here."
        action={{
          label: "Start a run",
          onClick: () => {
            navigate({ to: "/app/pipelines" });
          },
        }}
      />
    );
  }

  if (isFilteredEmpty) {
    return (
      <div className="stack">
        <FilterBarContent
          types={types}
          filters={filters}
          onFilterChange={handleFilterChange}
          total={total}
          count={runs.length}
          implementations={implementations}
        />
        <EmptyState
          title="No runs match your filters"
          description="Try adjusting your filter criteria to find the runs you're looking for."
          action={{
            label: "Clear filters",
            onClick: () => {
              handleFilterChange({
                pipelineType: undefined,
                status: undefined,
                startDate: undefined,
                endDate: undefined,
                implementation: undefined,
                applied: undefined,
              });
            },
          }}
        />
      </div>
    );
  }

  return (
    <div data-testid="runs-page" className="stack">
      <FilterBarContent
        types={types}
        filters={filters}
        onFilterChange={handleFilterChange}
        total={total}
        count={runs.length}
        implementations={implementations}
      />

      <SchemaPageLayout
        data={runs}
        selectedId={selectedId}
        renderInspectorContent={(run) => (
          <RunDetailDrawer
            key={run.id}
            runId={run.id}
            onClose={() => onSelectedIdChange(undefined)}
          />
        )}
      >
        <div className="schema-table-wrap" data-testid="runs-table">
          <div className="runs-table-grid">
            <div className="runs-table-header">
              <div className="runs-table-header-cell">Pipeline Type</div>
              <div className="runs-table-header-cell">Implementation</div>
              <div className="runs-table-header-cell">Status</div>
              <div className="runs-table-header-cell">Started</div>
              <div className="runs-table-header-cell">Candidates</div>
            </div>
            {runs.map((run) => (
              <div
                key={run.id}
                onClick={() => onSelectedIdChange(run.id)}
                className={`runs-table-row ${selectedId === run.id ? "runs-table-row--selected" : ""}`}
                data-testid={`run-row-${run.id}`}
                role="row"
                aria-selected={selectedId === run.id}
              >
                <div className="runs-table-cell">
                  <Chip variant="neutral">
                    {run.pipeline_type
                      .split("_")
                      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                      .join(" ")}
                  </Chip>
                </div>
                <div className="runs-table-cell">{run.configuration_slug || "—"}</div>
                <div className="runs-table-cell">
                  <StatusBadge
                    color={
                      run.status === "PENDING"
                        ? "amber"
                        : run.status === "RUNNING"
                          ? "cyan"
                          : run.status === "COMPLETED"
                            ? "emerald"
                            : run.status === "FAILED"
                              ? "rose"
                              : "neutral"
                    }
                  >
                    {run.status}
                  </StatusBadge>
                </div>
                <div className="runs-table-cell runs-table-cell--date">
                  {formatDate(run.started_at)}
                </div>
                <div className="runs-table-cell">
                  <Chip variant="neutral">{(run.output_summary as any)?.candidate_count ?? 0}</Chip>
                </div>
              </div>
            ))}
          </div>

          {pageCount > 1 && (
            <div className="schema-table-footer">
              <span>
                Page {pageIndex + 1} of {pageCount}
              </span>
              <div className="schema-table-footer__actions">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
                  disabled={pageIndex === 0}
                  data-testid="runs-pagination-prev"
                >
                  <Icon name="chevronLeft" size={13} />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setPageIndex((p) => Math.min(pageCount - 1, p + 1))}
                  disabled={pageIndex >= pageCount - 1}
                  data-testid="runs-pagination-next"
                >
                  <Icon name="chevronRight" size={13} />
                </Button>
              </div>
            </div>
          )}
        </div>
      </SchemaPageLayout>
    </div>
  );
}

interface FilterBarContentProps {
  types: Array<{ pipeline_type: string }>;
  filters: FilterState;
  onFilterChange: (newFilters: Partial<FilterState>) => void;
  total: number;
  count: number;
  implementations?: Array<{ id: string }>;
}

function FilterBarContent({
  types,
  filters,
  onFilterChange,
  total,
  count,
  implementations,
}: FilterBarContentProps) {
  return (
    <div data-testid="runs-filter-bar" className="runs-filter-bar">
      <div className="runs-filter-controls">
        <FilterDropdown
          mode="radio"
          value={filters.pipelineType ? [filters.pipelineType] : []}
          onChange={(values) =>
            onFilterChange({
              pipelineType: values[0] || undefined,
              implementation: undefined,
            })
          }
        >
          <FilterDropdown.Trigger
            label="Pipeline Type"
            summary={filters.pipelineType || "All"}
            data-testid="filter-pipeline-type"
          />
          <FilterDropdown.Panel>
            <FilterDropdown.Section>
              {types.map((type) => (
                <FilterDropdown.Radio
                  key={type.pipeline_type}
                  value={type.pipeline_type}
                  label={type.pipeline_type
                    .split("_")
                    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                    .join(" ")}
                />
              ))}
            </FilterDropdown.Section>
          </FilterDropdown.Panel>
        </FilterDropdown>

        <FilterDropdown
          mode="radio"
          value={filters.status ? [filters.status] : []}
          onChange={(values) => onFilterChange({ status: values[0] || undefined })}
        >
          <FilterDropdown.Trigger
            label="Status"
            summary={filters.status || "All"}
            data-testid="filter-status"
          />
          <FilterDropdown.Panel>
            <FilterDropdown.Section>
              {PIPELINE_STATUS_OPTIONS.map((option) => (
                <FilterDropdown.Radio
                  key={option.value}
                  value={option.value}
                  label={option.label}
                />
              ))}
            </FilterDropdown.Section>
          </FilterDropdown.Panel>
        </FilterDropdown>

        <FilterDropdown mode="checkbox" value={[]} onChange={() => {}}>
          <FilterDropdown.Trigger
            label="Date Range"
            summary={filters.startDate || filters.endDate ? "Set" : "Any"}
            data-testid="filter-date-range"
          />
          <FilterDropdown.Panel>
            <div className="date-filter-content">
              <div className="date-filter-field">
                <label>Start Date</label>
                <input
                  type="date"
                  value={filters.startDate ? filters.startDate.split("T")[0] : ""}
                  onChange={(e) => onFilterChange({ startDate: e.target.value || undefined })}
                  data-testid="filter-start-date"
                />
              </div>
              <div className="date-filter-field">
                <label>End Date</label>
                <input
                  type="date"
                  value={filters.endDate ? filters.endDate.split("T")[0] : ""}
                  onChange={(e) => onFilterChange({ endDate: e.target.value || undefined })}
                  data-testid="filter-end-date"
                />
              </div>
              {(filters.startDate || filters.endDate) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onFilterChange({ startDate: undefined, endDate: undefined })}
                  data-testid="filter-clear-dates"
                  className="date-filter-clear"
                >
                  Clear
                </Button>
              )}
            </div>
          </FilterDropdown.Panel>
        </FilterDropdown>

        {filters.pipelineType && implementations && implementations.length > 0 && (
          <FilterDropdown
            mode="radio"
            value={filters.implementation ? [filters.implementation] : []}
            onChange={(values) => onFilterChange({ implementation: values[0] || undefined })}
          >
            <FilterDropdown.Trigger
              label="Implementation"
              summary={filters.implementation || "All"}
              data-testid="filter-implementation"
            />
            <FilterDropdown.Panel>
              <FilterDropdown.Section>
                {implementations.map((impl) => (
                  <FilterDropdown.Radio
                    key={impl.id}
                    value={impl.id}
                    label={impl.id
                      .split("_")
                      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                      .join(" ")}
                  />
                ))}
              </FilterDropdown.Section>
            </FilterDropdown.Panel>
          </FilterDropdown>
        )}

        <FilterDropdown
          mode="radio"
          value={filters.applied ? [filters.applied] : []}
          onChange={(values) =>
            onFilterChange({ applied: (values[0] as "applied" | "not-applied") || undefined })
          }
        >
          <FilterDropdown.Trigger
            label="Applied"
            summary={
              filters.applied === "applied"
                ? "Applied"
                : filters.applied === "not-applied"
                  ? "Not Applied"
                  : "All"
            }
            data-testid="filter-applied"
          />
          <FilterDropdown.Panel>
            <FilterDropdown.Section>
              <FilterDropdown.Radio value="applied" label="Applied" />
              <FilterDropdown.Radio value="not-applied" label="Not Applied" />
            </FilterDropdown.Section>
          </FilterDropdown.Panel>
        </FilterDropdown>
      </div>

      <div className="runs-filter-summary">
        Showing {count} of {total} runs
      </div>
    </div>
  );
}

function RunsPageWrapper() {
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/pipelines/runs" as any });
  const selectedId = searchParams.selected;

  const handleSelectedIdChange = (id: string | undefined) => {
    navigate({
      to: "/app/pipelines/runs" as any,
      search: id ? { selected: id } : ({} as any),
      replace: true,
    });
  };

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Pipelines"
        title="Runs"
        subtitle="View execution history and results from your pipeline runs."
      />

      <RunsPageContent selectedId={selectedId} onSelectedIdChange={handleSelectedIdChange} />
    </div>
  );
}

export function RunsPage() {
  return <RunsPageWrapper />;
}

export const Route = createFileRoute("/app/pipelines/runs")({
  component: RunsPage,
  validateSearch: (search: Record<string, unknown>): RunsSearchParams => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});
