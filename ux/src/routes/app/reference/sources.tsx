import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { MoreVertical } from "lucide-react";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Chip } from "@/components/ui/Chip";
import { FilterBar } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { ReferenceSourceDrawer } from "@/components/reference/ReferenceSourceDrawer";
import { useReferenceStatus } from "@/api/hooks/reference";
import type { components } from "@/api/types";

type ReferenceSourceStatusSchema = components["schemas"]["ReferenceSourceStatusSchema"];

interface SourcesSearchParams {
  selected?: string;
}

interface SourceWithId extends ReferenceSourceStatusSchema {
  id: string;
}

interface SourcesPageContentProps {
  selectedId?: string;
  onSelectedIdChange: (id: string | undefined) => void;
}

function SourcesPageContent({
  selectedId,
  onSelectedIdChange,
}: SourcesPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");

  const { data: statusResponse, isLoading, error, refetch } = useReferenceStatus();
  const sources = (statusResponse?.sources || []).map((source) => ({
    ...source,
    id: source.name,
  }));

  const filteredData = sources.filter(
    (source: SourceWithId) =>
      source.name.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const sourceColumns: ColumnDef<SourceWithId>[] = [
    {
      accessorKey: "name",
      header: "Name",
      cell: (info) => {
        const sourceId = info.row.original.id;
        return (
          <button
            style={{
              background: "none",
              border: "none",
              color: "var(--cyan-600, #0891b2)",
              fontWeight: 500,
              cursor: "pointer",
              padding: 0,
            }}
            onClick={() => onSelectedIdChange(sourceId)}
            data-testid={`reference-source-name-${sourceId}`}
          >
            {info.getValue() as string}
          </button>
        );
      },
    },
    {
      accessorKey: "available",
      header: "Status",
      cell: (info) => {
        const available = info.getValue() as boolean;
        const statusLabel = available ? "Active" : "Inactive";

        return (
          <Chip color={available ? "emerald" : "gray"}>
            {statusLabel}
          </Chip>
        );
      },
    },
    {
      accessorKey: "last_checked",
      header: "Last Checked",
      cell: (info) => {
        const date = info.getValue() as string | null;
        if (!date) return <span className="muted-text">—</span>;

        const lastCheckedDate = new Date(date);
        const now = new Date();
        const diffMs = now.getTime() - lastCheckedDate.getTime();
        const diffMins = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        let relativeTime = "";
        if (diffMins < 1) {
          relativeTime = "just now";
        } else if (diffMins < 60) {
          relativeTime = `${diffMins}m ago`;
        } else if (diffHours < 24) {
          relativeTime = `${diffHours}h ago`;
        } else {
          relativeTime = `${diffDays}d ago`;
        }

        return <span className="muted-text">{relativeTime}</span>;
      },
    },
  ];

  const renderRowActions = (source: SourceWithId) => (
    <button
      onClick={() => onSelectedIdChange(source.id)}
      aria-label="Actions"
      data-testid={`reference-source-row-actions-${source.name}`}
      className="btn btn-icon"
    >
      <MoreVertical size={16} style={{ color: "var(--canvas-fg-3)" }} />
    </button>
  );

  if (isLoading) {
    return (
      <div data-testid="reference-sources-page" className="stack">
        <Skeleton height={32} width={200} />
        <Skeleton height={40} />
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} height={40} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="reference-sources-page" className="stack">
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message="Failed to load reference sources"
        />
      </div>
    );
  }

  if (sources.length === 0) {
    return (
      <div data-testid="reference-sources-page">
        <EmptyState
          title="No reference sources"
          description="Reference sources are configured in Settings"
        />
      </div>
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = sources.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="reference-sources-page">
      <FilterBar searchValue={searchFilter} onSearchChange={setSearchFilter} />

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title="No sources match your search"
            description="Try a different search term"
          />
        </div>
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderDrawerContent={(source) => (
            <ReferenceSourceDrawer
              key={source.name}
              source={source}
              onClose={() => onSelectedIdChange(undefined)}
            />
          )}
        >
          <SchemaTable
            columns={sourceColumns}
            data={filteredData}
            onRowSelect={(id) => onSelectedIdChange(id)}
            renderRowActions={renderRowActions}
            selectedId={selectedId}
            tableTestId="reference-sources-table"
          />
        </SchemaPageLayout>
      )}
    </div>
  );
}

function SourcesPageWrapper() {
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/reference/sources" });
  const selectedId = searchParams.selected;

  const handleSelectedIdChange = (id: string | undefined) => {
    navigate({
      to: "/app/reference/sources",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  return (
    <div className="stack">
      <div className="flex-between">
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>Reference Sources</h1>
      </div>
      <div data-testid="sources-content">
        <SourcesPageContent
          selectedId={selectedId}
          onSelectedIdChange={handleSelectedIdChange}
        />
      </div>
    </div>
  );
}

export function SourcesPage() {
  return <SourcesPageWrapper />;
}

export const Route = createFileRoute("/app/reference/sources")({
  component: SourcesPage,
  validateSearch: (search: Record<string, unknown>): SourcesSearchParams => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});
