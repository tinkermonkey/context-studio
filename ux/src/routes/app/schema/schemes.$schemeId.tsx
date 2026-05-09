import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { MoreVertical } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { useScheme } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import type { components } from "@/api/types";

type ClassResponse = components["schemas"]["ClassResponse"];

interface SchemeDetailContentProps {
  schemeId: string;
}

function SchemeDetailContent({ schemeId }: SchemeDetailContentProps) {
  const [selectedId, setSelectedId] = useState<string>();
  const [searchFilter, setSearchFilter] = useState("");

  const { data: scheme, isLoading: schemeLoading, error: schemeError, refetch: refetchScheme } = useScheme(schemeId);
  const { data: classesResponse, isLoading: classesLoading, error: classesError, refetch: refetchClasses } = useClasses({
    concept_scheme_id: schemeId,
  });

  const classes = classesResponse?.items || [];

  const filteredData = classes.filter((cls: ClassResponse) =>
    cls.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
    cls.description?.toLowerCase().includes(searchFilter.toLowerCase()) ||
    cls.id.toLowerCase().includes(searchFilter.toLowerCase())
  );

  const classColumns: ColumnDef<ClassResponse>[] = [
    {
      accessorKey: "id",
      header: "ID",
      size: 100,
      cell: (info) => (
        <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
          {(info.getValue() as string).slice(0, 8)}
        </span>
      ),
    },
    {
      accessorKey: "title",
      header: "Name",
      cell: (info) => (
        <span
          style={{
            color: "var(--cyan-600, #0891b2)",
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          {info.getValue() as string}
        </span>
      ),
    },
    {
      accessorKey: "description",
      header: "Description",
      cell: (info) => (
        <span style={{ color: "var(--canvas-fg-2)" }}>
          {(info.getValue() as string) || "—"}
        </span>
      ),
    },
    {
      accessorKey: "last_modified",
      header: "Updated",
      cell: (info) => {
        const date = info.getValue() as string | null;
        return date ? new Date(date).toLocaleDateString() : "—";
      },
    },
    {
      id: "actions",
      header: "",
      size: 40,
      cell: ({ row }) => (
        <button
          data-testid={`class-row-actions-${row.original.id}`}
          style={{
            background: "none",
            border: "none",
            padding: 0,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <MoreVertical size={16} style={{ color: "var(--canvas-fg-3)" }} />
        </button>
      ),
    },
  ];

  const isLoading = schemeLoading || classesLoading;
  const error = schemeError || classesError;

  if (isLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
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
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <ErrorBanner
          error={error}
          onRetry={() => {
            refetchScheme();
            refetchClasses();
          }}
          message="Failed to load scheme"
        />
      </div>
    );
  }

  if (!scheme) {
    return (
      <EmptyState
        title="Concept scheme not found"
        description="The concept scheme you're looking for doesn't exist."
      />
    );
  }

  if (classes.length === 0) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>{scheme.title}</h1>
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title="No classes yet"
            description="Classes are the core concepts within this concept scheme."
            action={{
              label: "+ New class",
              onClick: () => {
                // TODO: Open create class dialog
              },
            }}
          />
        </div>
      </div>
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = classes.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="scheme-detail-page">
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>{scheme.title}</h1>
          <Button
            variant="primary"
            onClick={() => {
              // TODO: Open create class dialog
            }}
            data-testid="scheme-detail-add-class-button"
          >
            + New class
          </Button>
        </div>

        <FilterBar
          searchValue={searchFilter}
          onSearchChange={setSearchFilter}
        />

        {showFilteredEmpty ? (
          <div style={{ marginTop: "var(--space-6)" }}>
            <EmptyState
              title="No matching classes"
              description="Try adjusting your search or filters to find classes."
            />
          </div>
        ) : (
          <SchemaPageLayout
            data={filteredData}
            selectedId={selectedId}
            renderDrawerContent={() => null}
          >
            <SchemaTable
              columns={classColumns}
              data={filteredData}
              onRowSelect={setSelectedId}
              selectedId={selectedId}
            />
          </SchemaPageLayout>
        )}
      </div>
    </div>
  );
}

interface RouteParams {
  schemeId: string;
}

function SchemeDetailPage() {
  const { schemeId } = Route.useParams() as RouteParams;

  return <SchemeDetailContent schemeId={schemeId} />;
}

export const Route = createFileRoute("/app/schema/schemes/$schemeId")({
  component: SchemeDetailPage,
});
