import { useState, useMemo } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import {
  Button,
  PageHeader,
  Icon,
  Chip,
  StatusBadge,
} from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { RunDetailDrawer } from "@/components/pipeline/RunDetailDrawer";
import { usePipelineTypes } from "@/api/hooks/pipeline/usePipelineTypes";
import { usePipelineRuns } from "@/api/hooks/pipeline/usePipelineRuns";
import type { components } from "@/api/types";

type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];

interface RunsSearchParams {
  selected?: string;
}

interface FilterState {
  pipelineTypes: string[];
  statuses: string[];
  startDate?: string;
  endDate?: string;
}

const PAGE_SIZE = 20;
const PIPELINE_STATUS_OPTIONS = [
  { value: "PENDING", label: "Pending" },
  { value: "RUNNING", label: "Running" },
  { value: "COMPLETED", label: "Completed" },
  { value: "FAILED", label: "Failed" },
];

function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "—";
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function RunsPageContent({
  selectedId,
  onSelectedIdChange,
}: {
  selectedId?: string;
  onSelectedIdChange: (id: string | undefined) => void;
}) {
  const [filters, setFilters] = useState<FilterState>({
    pipelineTypes: [],
    statuses: [],
  });
  const [pageIndex, setPageIndex] = useState(0);

  const { data: typesData } = usePipelineTypes();
  const types = typesData || [];

  const listParams = useMemo(() => {
    const params: any = {
      limit: PAGE_SIZE,
      offset: pageIndex * PAGE_SIZE,
    };
    if (filters.pipelineTypes.length > 0) {
      params.pipeline_type = filters.pipelineTypes[0];
    }
    if (filters.statuses.length > 0) {
      params.status = filters.statuses[0];
    }
    if (filters.startDate) {
      params.start_date = filters.startDate;
    }
    if (filters.endDate) {
      params.end_date = filters.endDate;
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
        <div className="skeleton" style={{ height: 32, width: 200 }} />
        <div className="skeleton" style={{ height: 40 }} />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 40 }} />
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

  if (total === 0 && !isLoading) {
    return (
      <EmptyState
        title="No pipeline runs yet"
        description="Start your first pipeline run to see execution history here."
        action={{
          label: "Start a run",
          onClick: () => {
            window.location.href = "/app/pipelines";
          },
        }}
      />
    );
  }

  const hasFilters =
    filters.pipelineTypes.length > 0 ||
    filters.statuses.length > 0 ||
    filters.startDate ||
    filters.endDate;
  const showFilteredEmpty = total > 0 && runs.length === 0 && hasFilters;

  if (showFilteredEmpty) {
    return (
      <div className="stack">
        <div data-testid="runs-filter-bar" style={{ padding: "12px 0" }}>
          <div style={{ display: "flex", gap: "12px" }}>
            <div data-testid="filter-pipeline-type">
              <FilterDropdownSelect
                label="Pipeline Type"
                options={types.map((t) => ({
                  value: t.pipeline_type,
                  label: t.pipeline_type
                    .split("_")
                    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                    .join(" "),
                }))}
                selectedValues={filters.pipelineTypes}
                onChange={(values) => handleFilterChange({ pipelineTypes: values })}
                multiSelect
              />
            </div>
            <div data-testid="filter-status">
              <FilterDropdownSelect
                label="Status"
                options={PIPELINE_STATUS_OPTIONS}
                selectedValues={filters.statuses}
                onChange={(values) => handleFilterChange({ statuses: values })}
                multiSelect
              />
            </div>
          </div>
        </div>
        <EmptyState
          title="No runs match your filters"
          description="Try adjusting your filter criteria to find the runs you're looking for."
          action={{
            label: "Clear filters",
            onClick: () => {
              handleFilterChange({
                pipelineTypes: [],
                statuses: [],
                startDate: undefined,
                endDate: undefined,
              });
            },
          }}
        />
      </div>
    );
  }

  return (
    <div data-testid="runs-page" className="stack">
      <div data-testid="runs-filter-bar" style={{ padding: "12px 0", display: "flex", gap: "12px" }}>
        <div data-testid="filter-pipeline-type">
          <FilterDropdownSelect
            label="Pipeline Type"
            options={types.map((t) => ({
              value: t.pipeline_type,
              label: t.pipeline_type
                .split("_")
                .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                .join(" "),
            }))}
            selectedValues={filters.pipelineTypes}
            onChange={(values) => handleFilterChange({ pipelineTypes: values })}
            multiSelect
          />
        </div>
        <div data-testid="filter-status">
          <FilterDropdownSelect
            label="Status"
            options={PIPELINE_STATUS_OPTIONS}
            selectedValues={filters.statuses}
            onChange={(values) => handleFilterChange({ statuses: values })}
            multiSelect
          />
        </div>
        <FilterDropdownDateRange
          label="Date Range"
          startDate={filters.startDate}
          endDate={filters.endDate}
          onChange={(start, end) => handleFilterChange({ startDate: start, endDate: end })}
        />
        <div style={{ marginLeft: "auto", alignSelf: "center", fontSize: "12px", color: "rgb(var(--canvas-fg-3))" }}>
          Showing {runs.length} of {total} runs
        </div>
      </div>

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
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "140px 1fr 120px 160px 90px",
                gap: "16px",
                padding: "12px",
                borderBottom: "1px solid rgb(var(--canvas-border))",
                fontSize: "12px",
                fontWeight: 600,
                color: "rgb(var(--canvas-fg-2))",
              }}
            >
              <div>Pipeline Type</div>
              <div>Implementation</div>
              <div>Status</div>
              <div>Started</div>
              <div>Candidates</div>
            </div>
            {runs.map((run) => (
              <div
                key={run.id}
                onClick={() => onSelectedIdChange(run.id)}
                style={{
                  display: "grid",
                  gridTemplateColumns: "140px 1fr 120px 160px 90px",
                  gap: "16px",
                  padding: "12px",
                  borderBottom: "1px solid rgb(var(--canvas-border))",
                  cursor: "pointer",
                  background:
                    selectedId === run.id
                      ? "rgb(var(--canvas-bg-hover))"
                      : "transparent",
                  transition: "background-color 150ms ease",
                }}
                onMouseEnter={(e) => {
                  if (selectedId !== run.id) {
                    e.currentTarget.style.background = "rgb(var(--canvas-bg-hover))";
                  }
                }}
                onMouseLeave={(e) => {
                  if (selectedId !== run.id) {
                    e.currentTarget.style.background = "transparent";
                  }
                }}
                data-testid={`run-row-${run.id}`}
                role="row"
                aria-selected={selectedId === run.id}
              >
                <div>
                  <Chip variant="neutral">
                    {run.pipeline_type
                      .split("_")
                      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                      .join(" ")}
                  </Chip>
                </div>
                <div>{run.configuration_slug || "—"}</div>
                <div>
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
                <div style={{ fontSize: "12px" }}>{formatDate(run.started_at)}</div>
                <div>
                  <Chip variant="neutral">
                    {(run.output_summary as any)?.candidate_count ?? 0}
                  </Chip>
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

interface FilterDropdownSelectProps {
  label: string;
  options: Array<{ value: string; label: string }>;
  selectedValues: string[];
  onChange: (values: string[]) => void;
  multiSelect?: boolean;
}

function FilterDropdownSelect({
  label,
  options,
  selectedValues,
  onChange,
  multiSelect,
}: FilterDropdownSelectProps) {
  const [isOpen, setIsOpen] = useState(false);

  const toggleOption = (value: string) => {
    if (multiSelect) {
      const newValues = selectedValues.includes(value)
        ? selectedValues.filter((v) => v !== value)
        : [...selectedValues, value];
      onChange(newValues);
    } else {
      onChange(selectedValues.includes(value) ? [] : [value]);
      setIsOpen(false);
    }
  };

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        data-testid={`filter-${label.toLowerCase()}`}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
        }}
      >
        {label}
        {selectedValues.length > 0 && (
          <Chip variant="neutral" style={{ marginLeft: "4px" }}>
            {selectedValues.length}
          </Chip>
        )}
        <Icon name={isOpen ? "chevronUp" : "chevronDown"} size={13} />
      </Button>

      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            zIndex: 10,
            background: "rgb(var(--canvas-bg))",
            border: "1px solid rgb(var(--canvas-border))",
            borderRadius: "4px",
            marginTop: "4px",
            minWidth: "200px",
            boxShadow: "0 2px 8px rgba(0, 0, 0, 0.1)",
          }}
        >
          {options.map((option) => (
            <label
              key={option.value}
              style={{
                display: "flex",
                alignItems: "center",
                padding: "8px 12px",
                cursor: "pointer",
                background: selectedValues.includes(option.value)
                  ? "rgb(var(--canvas-bg-hover))"
                  : "transparent",
                borderBottom: "1px solid rgb(var(--canvas-border))",
              }}
            >
              <input
                type={multiSelect ? "checkbox" : "radio"}
                checked={selectedValues.includes(option.value)}
                onChange={() => toggleOption(option.value)}
                style={{ marginRight: "8px" }}
              />
              {option.label}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

interface FilterDropdownDateRangeProps {
  label: string;
  startDate?: string;
  endDate?: string;
  onChange: (start?: string, end?: string) => void;
}

function FilterDropdownDateRange({
  label,
  startDate,
  endDate,
  onChange,
}: FilterDropdownDateRangeProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        data-testid="filter-date-range"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
        }}
      >
        {label}
        {(startDate || endDate) && (
          <Chip variant="neutral" style={{ marginLeft: "4px" }}>
            1
          </Chip>
        )}
        <Icon name={isOpen ? "chevronUp" : "chevronDown"} size={13} />
      </Button>

      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            zIndex: 10,
            background: "rgb(var(--canvas-bg))",
            border: "1px solid rgb(var(--canvas-border))",
            borderRadius: "4px",
            marginTop: "4px",
            padding: "12px",
            minWidth: "250px",
            boxShadow: "0 2px 8px rgba(0, 0, 0, 0.1)",
          }}
        >
          <div style={{ marginBottom: "8px" }}>
            <label style={{ display: "block", marginBottom: "4px", fontSize: "12px" }}>
              Start Date
            </label>
            <input
              type="date"
              value={startDate ? startDate.split("T")[0] : ""}
              onChange={(e) => onChange(e.target.value || undefined, endDate)}
              style={{
                width: "100%",
                padding: "6px",
                fontSize: "12px",
                border: "1px solid rgb(var(--canvas-border))",
                borderRadius: "4px",
              }}
              data-testid="filter-start-date"
            />
          </div>
          <div>
            <label style={{ display: "block", marginBottom: "4px", fontSize: "12px" }}>
              End Date
            </label>
            <input
              type="date"
              value={endDate ? endDate.split("T")[0] : ""}
              onChange={(e) => onChange(startDate, e.target.value || undefined)}
              style={{
                width: "100%",
                padding: "6px",
                fontSize: "12px",
                border: "1px solid rgb(var(--canvas-border))",
                borderRadius: "4px",
              }}
              data-testid="filter-end-date"
            />
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onChange(undefined, undefined);
              setIsOpen(false);
            }}
            style={{ marginTop: "8px", width: "100%" }}
            data-testid="filter-clear-dates"
          >
            Clear
          </Button>
        </div>
      )}
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

      <RunsPageContent
        selectedId={selectedId}
        onSelectedIdChange={handleSelectedIdChange}
      />
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
