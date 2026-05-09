import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { MoreVertical, ChevronDown } from "lucide-react";
import { ToastViewport, useToasts } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { FilterBar, type FilterChip } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { RelationshipDrawer } from "@/components/ontology/RelationshipDrawer";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { relationshipsCopy } from "./relationships/-copy";
import type { components } from "@/api/types";

type RelationshipResponse = components["schemas"]["RelationshipResponse"];

interface RelationshipsPageContentProps {
  classesById: Map<string, string>;
  propertiesById: Map<string, string>;
}

function RelationshipsPageContent({
  classesById,
  propertiesById,
}: RelationshipsPageContentProps) {
  const [selectedId, setSelectedId] = useState<string>();
  const [searchFilter, setSearchFilter] = useState("");
  const [sourceClassFilter, setSourceClassFilter] = useState<string>();
  const [targetClassFilter, setTargetClassFilter] = useState<string>();

  const { data: listResponse, isLoading, error, refetch } = useRelationships();
  const relationships = listResponse?.items || [];

  const filteredData = relationships.filter((rel: RelationshipResponse) => {
    const sourceClassName = classesById.get(rel.source_id)?.toLowerCase() ?? "";
    const targetClassName = classesById.get(rel.target_id)?.toLowerCase() ?? "";
    const propertyName = propertiesById.get(rel.property_definition_id)?.toLowerCase() ?? "";
    const search = searchFilter.toLowerCase();

    const matchesSearch =
      sourceClassName.includes(search) || targetClassName.includes(search) || propertyName.includes(search);

    const matchesSourceFilter = !sourceClassFilter || rel.source_id === sourceClassFilter;
    const matchesTargetFilter = !targetClassFilter || rel.target_id === targetClassFilter;

    return matchesSearch && matchesSourceFilter && matchesTargetFilter;
  });

  const filterChips: FilterChip[] = [
    ...(sourceClassFilter
      ? [
          {
            label: `Source: ${classesById.get(sourceClassFilter) || sourceClassFilter}`,
            value: sourceClassFilter,
            onRemove: () => setSourceClassFilter(undefined),
          },
        ]
      : []),
    ...(targetClassFilter
      ? [
          {
            label: `Target: ${classesById.get(targetClassFilter) || targetClassFilter}`,
            value: targetClassFilter,
            onRemove: () => setTargetClassFilter(undefined),
          },
        ]
      : []),
  ];

  const relationshipColumns: ColumnDef<RelationshipResponse>[] = [
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
      accessorKey: "property_definition_id",
      header: "Name",
      cell: (info) => (
        <span
          style={{
            color: "var(--cyan-600, #0891b2)",
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          {propertiesById.get(info.getValue() as string) || "—"}
        </span>
      ),
    },
    {
      accessorKey: "source_id",
      header: "Source Class",
      cell: (info) => (
        <span style={{ color: "var(--canvas-fg-2)" }}>
          {classesById.get(info.getValue() as string) || "—"}
        </span>
      ),
    },
    {
      accessorKey: "target_id",
      header: "Target Class",
      cell: (info) => (
        <span style={{ color: "var(--canvas-fg-2)" }}>
          {classesById.get(info.getValue() as string) || "—"}
        </span>
      ),
    },
    {
      id: "actions",
      header: "",
      size: 40,
      cell: ({ row }) => (
        <button
          data-testid={`relationship-row-actions-${row.original.id}`}
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
          onRetry={() => refetch()}
          message="Failed to load relationships"
        />
      </div>
    );
  }

  if (relationships.length === 0) {
    return (
      <EmptyState
        title={relationshipsCopy.emptyState.title}
        description={relationshipsCopy.emptyState.description}
        action={{
          label: relationshipsCopy.emptyState.actionLabel,
          onClick: () => {
            // TODO: Open create relationship dialog
          },
        }}
      />
    );
  }

  const hasFilters = !!searchFilter || !!sourceClassFilter || !!targetClassFilter;
  const showFilteredEmpty = relationships.length > 0 && filteredData.length === 0 && hasFilters;

  if (showFilteredEmpty) {
    return (
      <div data-testid="relationships-page">
        <FilterBar
          searchValue={searchFilter}
          onSearchChange={setSearchFilter}
          filterChips={filterChips}
        />
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title={relationshipsCopy.filteredEmpty.title}
            description={relationshipsCopy.filteredEmpty.description}
          />
        </div>
      </div>
    );
  }

  return (
    <div data-testid="relationships-page">
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ position: "relative" }}>
            <select
              value={sourceClassFilter || ""}
              onChange={(e) => setSourceClassFilter(e.target.value || undefined)}
              data-testid="relationship-source-class-filter"
              style={{
                padding: "6px 8px",
                borderRadius: "4px",
                border: "1px solid var(--canvas-fg-4, #e5e7eb)",
                backgroundColor: "var(--canvas-bg, #ffffff)",
                cursor: "pointer",
                fontSize: "var(--text-sm)",
                appearance: "none",
                paddingRight: "24px",
              }}
            >
              <option value="">Source Class</option>
              {Array.from(classesById.entries()).map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
            <ChevronDown
              size={14}
              style={{
                position: "absolute",
                right: "8px",
                top: "50%",
                transform: "translateY(-50%)",
                pointerEvents: "none",
                color: "var(--canvas-fg-3)",
              }}
            />
          </div>

          <div style={{ position: "relative" }}>
            <select
              value={targetClassFilter || ""}
              onChange={(e) => setTargetClassFilter(e.target.value || undefined)}
              data-testid="relationship-target-class-filter"
              style={{
                padding: "6px 8px",
                borderRadius: "4px",
                border: "1px solid var(--canvas-fg-4, #e5e7eb)",
                backgroundColor: "var(--canvas-bg, #ffffff)",
                cursor: "pointer",
                fontSize: "var(--text-sm)",
                appearance: "none",
                paddingRight: "24px",
              }}
            >
              <option value="">Target Class</option>
              {Array.from(classesById.entries()).map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
            <ChevronDown
              size={14}
              style={{
                position: "absolute",
                right: "8px",
                top: "50%",
                transform: "translateY(-50%)",
                pointerEvents: "none",
                color: "var(--canvas-fg-3)",
              }}
            />
          </div>
        </div>

        <FilterBar
          searchValue={searchFilter}
          onSearchChange={setSearchFilter}
          filterChips={filterChips}
        />
      </div>

      <SchemaPageLayout
        data={filteredData}
        selectedId={selectedId}
        renderDrawerContent={(rel) => (
          <RelationshipDrawer
            key={rel.id}
            relationship={rel}
            sourceName={classesById.get(rel.source_id) || "—"}
            targetName={classesById.get(rel.target_id) || "—"}
            propertyName={propertiesById.get(rel.property_definition_id) || "—"}
            onClose={() => setSelectedId(undefined)}
          />
        )}
      >
        <SchemaTable
          columns={relationshipColumns}
          data={filteredData}
          onRowSelect={setSelectedId}
          selectedId={selectedId}
        />
      </SchemaPageLayout>
    </div>
  );
}

function RelationshipsPageWrapper() {
  const { data: classesResponse } = useClasses();
  const { data: propertiesResponse } = useProperties();
  const { toasts, dismiss } = useToasts();

  const classes = classesResponse?.items || [];
  const properties = propertiesResponse?.items || [];

  const classesById = new Map(classes.map((c) => [c.id, c.title]));
  const propertiesById = new Map(properties.map((p) => [p.id, p.title]));

  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>Relationships</h1>
          <Button
            variant="primary"
            onClick={() => {
              // TODO: Open create relationship dialog
            }}
            data-testid="relationship-add-button"
          >
            + Add relationship
          </Button>
        </div>
        <div data-testid="relationships-content">
          <RelationshipsPageContent classesById={classesById} propertiesById={propertiesById} />
        </div>
      </div>
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </>
  );
}

function RelationshipsPage() {
  return <RelationshipsPageWrapper />;
}

export const Route = createFileRoute("/app/schema/relationships")({
  component: RelationshipsPage,
});
