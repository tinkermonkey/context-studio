import { useEffect, useRef } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { Button, PageHeader, FilterBar, TabBar, Icon } from "@tinkermonkey/heimdall-ui";
import type { Column } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EntitySurface, type EntitySurfaceHandle } from "@/components/crud/EntitySurface";
import { deleteFailureMessage } from "@/api/mutationErrors";
import { RelationshipDrawer } from "@/components/ontology/RelationshipDrawer";
import { useRelationships, useDeleteRelationship } from "@/api/hooks/ontology/useRelationships";
import { useClassesByIds } from "@/api/hooks/ontology/useClasses";
import { usePropertiesByIds } from "@/api/hooks/ontology/useProperties";
import { useListPaging } from "@/hooks/useListPaging";
import { relationshipsCopy } from "./relationships/-copy";
import { useSchemaTabs } from "./-useSchemaTabs";
import type { components } from "@/api/types";

type RelationshipResponse = components["schemas"]["RelationshipResponse"];

export function RelationshipsPage() {
  const surfaceRef = useRef<EntitySurfaceHandle>(null);
  const { toast } = useToasts();
  const paging = useListPaging();
  const { tabs: schemaTabs, onSelectTab: handleTabNavigate, counts } = useSchemaTabs();

  const {
    data: listResponse,
    isLoading,
    error,
    refetch,
  } = useRelationships(
    // Relationships only sort by created_at (newest first); no column sort is offered.
    { ...paging.params, sort_by: "created_at" },
    { keepPrevious: true },
  );

  const total = listResponse?.total;
  const { clampToTotal } = paging;
  useEffect(() => clampToTotal(total), [total, clampToTotal]);
  const pageData = listResponse?.items ?? [];

  // Resolve source/target/predicate names for this page's rows only.
  const {
    data: classesResponse,
    error: classesError,
    refetch: refetchClasses,
  } = useClassesByIds(pageData.flatMap((r) => [r.source_id, r.target_id]));
  const {
    data: propertiesResponse,
    error: propertiesError,
    refetch: refetchProperties,
  } = usePropertiesByIds(pageData.map((r) => r.property_definition_id));

  const deleteMutation = useDeleteRelationship();

  const classes = classesResponse?.items ?? [];
  const properties = propertiesResponse?.items ?? [];
  const classesById = new Map(classes.map((c) => [c.id, c.title]));
  const propertiesById = new Map(
    properties.map((p) => [p.id, { title: p.title, identifier: p.identifier }]),
  );

  const hasFilter = paging.hasSearch;

  async function handleDelete(ids: string[]) {
    const results = await Promise.allSettled(ids.map((id) => deleteMutation.mutateAsync(id)));
    if (results.every((r) => r.status === "fulfilled")) {
      toast("success", relationshipsCopy.delete.successToast);
      return;
    }
    // Surface the backend's reason if the delete is rejected.
    throw new Error(deleteFailureMessage(results, ids.length));
  }

  const relationshipColumns: Column<RelationshipResponse>[] = [
    {
      key: "id",
      label: "Identifier",
      width: "120px",
      render: (value) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>
          {(value as string).slice(0, 8)}
        </span>
      ),
    },
    {
      key: "source_id",
      label: "Source",
      render: (value) => (
        <span style={{ fontWeight: 500 }}>{classesById.get(value as string) || "—"}</span>
      ),
    },
    {
      key: "property_definition_id",
      label: "Predicate",
      width: "200px",
      render: (value) => {
        const prop = propertiesById.get(value as string);
        return (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11.5,
              color: "rgb(var(--canvas-fg-3))",
            }}
          >
            — {prop?.identifier ?? "?"} →
          </span>
        );
      },
    },
    {
      key: "target_id",
      label: "Target",
      render: (value) => (
        <span style={{ fontWeight: 500 }}>{classesById.get(value as string) || "—"}</span>
      ),
    },
    {
      key: "created_at",
      label: "Created",
      width: "120px",
      render: (value) => {
        const date = value as string | null;
        return (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11.5,
              color: "rgb(var(--canvas-fg-3))",
            }}
          >
            {date ? new Date(date).toLocaleDateString() : "—"}
          </span>
        );
      },
    },
  ];

  const rowMenuActions = [{ id: "delete", label: "Delete", icon: "trash" as const, danger: true }];

  const bulkActions = [{ id: "delete", label: "Delete", variant: "danger" as const }];

  const filteredEmpty = hasFilter && total === 0 && (counts.relationships ?? 0) > 0;
  const emptyStateTitle = filteredEmpty
    ? relationshipsCopy.filteredEmpty.title
    : relationshipsCopy.emptyState.title;
  const emptyStateDescription = filteredEmpty
    ? relationshipsCopy.filteredEmpty.description
    : relationshipsCopy.emptyState.description;

  return (
    <div className="stack" data-testid="relationships-page">
      <PageHeader
        eyebrow="SCHEMA · node_type · relationship"
        title="Relationships"
        idChip="/schema/relationships"
        subtitle="A relationship is a typed triple (s, p, o) between two graph nodes. Source and confidence are tracked separately from the data."
        actions={
          <>
            <Button variant="ghost" onClick={() => {}}>
              <Icon name="download" size={13} /> Export
            </Button>
            <Button
              variant="primary"
              onClick={() => surfaceRef.current?.startCreate()}
              data-testid="relationship-add-button"
            >
              <Icon name="plus" size={13} /> New relationship
            </Button>
          </>
        }
      />

      <TabBar tabs={schemaTabs} activeTabId="relationships" onSelectTab={handleTabNavigate} />

      {error ? (
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message="Failed to load relationships"
        />
      ) : (
        <>
          {classesError && (
            <ErrorBanner
              error={classesError}
              onRetry={() => refetchClasses()}
              message="Failed to load classes"
              compact
            />
          )}
          {propertiesError && (
            <ErrorBanner
              error={propertiesError}
              onRetry={() => refetchProperties()}
              message="Failed to load properties"
              compact
            />
          )}

          <FilterBar
            data-testid="schema-filter-bar"
            onSearchChange={paging.setSearch}
            searchPlaceholder="Search by source, predicate, or target…"
            showingCount={total ?? 0}
            totalCount={counts.relationships ?? total ?? 0}
          />

          <EntitySurface
            ref={surfaceRef}
            entityType="relationship"
            data={pageData}
            isLoading={isLoading}
            columns={relationshipColumns}
            pagination={paging.pagination(total)}
            onCreateSuccess={paging.resetPage}
            renderInspector={(entity) => (
              <RelationshipDrawer
                key={entity.id}
                relationship={entity}
                sourceName={classesById.get(entity.source_id) || "—"}
                targetName={classesById.get(entity.target_id) || "—"}
                propertyName={propertiesById.get(entity.property_definition_id)?.title || "—"}
              />
            )}
            rowMenuActions={rowMenuActions}
            onDeleteEntity={handleDelete}
            bulkActions={bulkActions}
            emptyStateTitle={emptyStateTitle}
            emptyStateDescription={emptyStateDescription}
            emptyStateShowAction={!filteredEmpty}
            testId="relationships-surface"
          />
        </>
      )}
    </div>
  );
}

export const Route = createFileRoute("/app/schema/relationships")({
  component: RelationshipsPage,
});
