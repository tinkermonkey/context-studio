import { Chip, RowMenu, FilterBar } from "@tinkermonkey/heimdall-ui";
import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { ReferenceSourceDrawer } from "@/components/reference/ReferenceSourceDrawer";
import { useReferenceStatus } from "@/api/hooks/reference";
import { COPY } from "./copy";
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

export function SourcesPageContent({ selectedId, onSelectedIdChange }: SourcesPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");

  const { data: statusResponse, isLoading, error, refetch } = useReferenceStatus();
  const sources = (statusResponse?.sources || []).map((source) => ({
    ...source,
    id: source.name,
  }));

  const filteredData = sources.filter((source: SourceWithId) =>
    source.name.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const sourceColumns: Column<SourceWithId>[] = [
    {
      key: "name",
      label: COPY.sourcesTableHeaderName,
      render: (value, row) => (
        <button
          style={{
            background: "none",
            border: "none",
            color: "var(--accent-cyan, #22d3ee)",
            fontWeight: 500,
            cursor: "pointer",
            padding: 0,
          }}
          onClick={() => onSelectedIdChange(row.id)}
          data-testid={`reference-source-name-${row.id}`}
        >
          {value as string}
        </button>
      ),
    },
    {
      key: "available",
      label: COPY.sourcesTableHeaderStatus,
      render: (value) => {
        const available = value as boolean;
        const statusLabel = available ? COPY.statusActive : COPY.statusInactive;
        return <Chip variant={available ? "emerald" : "neutral"}>{statusLabel}</Chip>;
      },
    },
    {
      key: "last_checked",
      label: COPY.sourcesTableHeaderLastChecked,
      render: (value) => {
        const date = value as string | null;
        if (!date) return <span className="opacity-60">—</span>;

        const lastCheckedDate = new Date(date);
        const now = new Date();
        const diffMs = now.getTime() - lastCheckedDate.getTime();
        const diffMins = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        let relativeTime: string;
        if (diffMins < 1) {
          relativeTime = COPY.justNow;
        } else if (diffMins < 60) {
          relativeTime = COPY.minutesAgo(diffMins);
        } else if (diffHours < 24) {
          relativeTime = COPY.hoursAgo(diffHours);
        } else {
          relativeTime = COPY.daysAgo(diffDays);
        }

        return <span className="opacity-60">{relativeTime}</span>;
      },
    },
    {
      key: "id",
      label: "",
      width: "40px",
      render: (_, row) => (
        <RowMenu
          data-testid={`reference-source-row-actions-${row.name}`}
          actions={[
            { id: "configure", label: "Configure", icon: "settings" },
            { id: "sync", label: "Sync now" },
            { type: "separator" },
            { id: "delete", label: "Delete", icon: "trash", danger: true },
          ]}
          onAction={(actionId: string) => {
            console.log(`Action ${actionId} on source ${row.id}`);
          }}
        />
      ),
    },
  ];

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
          message={COPY.failedToLoadReferenceSources}
        />
      </div>
    );
  }

  if (sources.length === 0) {
    return (
      <div data-testid="reference-sources-page">
        <EmptyState
          title={COPY.sourcesEmptyStateTitle}
          description={COPY.sourcesEmptyStateDescription}
        />
      </div>
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = sources.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="reference-sources-page">
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search sources…"
        showingCount={filteredData.length}
        totalCount={sources.length}
      />

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title={COPY.sourcesFilteredEmptyTitle}
            description={COPY.sourcesFilteredEmptyDescription}
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
            selectedId={selectedId}
            tableTestId="reference-sources-table"
          />
        </SchemaPageLayout>
      )}
    </div>
  );
}

export function SourcesPageWrapper() {
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
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>{COPY.sourcesPageTitle}</h1>
      </div>
      <div data-testid="sources-content">
        <SourcesPageContent selectedId={selectedId} onSelectedIdChange={handleSelectedIdChange} />
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
