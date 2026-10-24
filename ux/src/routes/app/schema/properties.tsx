import { useEffect, useRef } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import {
  Button,
  PageHeader,
  Chip,
  FilterBar,
  TabBar,
  Icon,
  VersionPill,
} from "@tinkermonkey/heimdall-ui";
import type { Column } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EntitySurface, type EntitySurfaceHandle } from "@/components/crud/EntitySurface";
import { deleteFailureMessage } from "@/api/mutationErrors";
import { PropertyDrawer } from "@/components/ontology/PropertyDrawer";
import {
  useProperties,
  useDeleteProperty,
  useSetPropertyRelevance,
} from "@/api/hooks/ontology/useProperties";
import { useListPaging } from "@/hooks/useListPaging";
import { propertiesCopy } from "./properties/-copy";
import { useSchemaTabs } from "./-useSchemaTabs";
import type { components } from "@/api/types";

type PropertyDefinitionResponse = components["schemas"]["PropertyDefinitionResponse"];

function relevanceChip(isRelevant: boolean | null | undefined) {
  if (isRelevant === true) return <Chip variant="emerald">relevant</Chip>;
  if (isRelevant === false) return <Chip variant="rose">irrelevant</Chip>;
  return <Chip variant="neutral">unevaluated</Chip>;
}

export function PropertiesPage() {
  const surfaceRef = useRef<EntitySurfaceHandle>(null);
  const { toast } = useToasts();
  const paging = useListPaging();
  const { tabs: schemaTabs, onSelectTab: handleTabNavigate, counts } = useSchemaTabs();

  const {
    data: listResponse,
    isLoading,
    error,
    refetch,
  } = useProperties(undefined, paging.params, { keepPrevious: true });

  const deleteMutation = useDeleteProperty();
  const relevanceMutation = useSetPropertyRelevance();

  const total = listResponse?.total;
  const { clampToTotal } = paging;
  useEffect(() => clampToTotal(total), [total, clampToTotal]);
  const pageData = listResponse?.items ?? [];
  const hasFilter = paging.hasSearch;

  async function handleDelete(ids: string[]) {
    const results = await Promise.allSettled(ids.map((id) => deleteMutation.mutateAsync(id)));
    if (results.every((r) => r.status === "fulfilled")) {
      toast("success", propertiesCopy.delete.successToast);
      return;
    }
    // Surface the backend's reason if the delete is rejected.
    throw new Error(deleteFailureMessage(results, ids.length));
  }

  const propertyColumns: Column<PropertyDefinitionResponse>[] = [
    {
      key: "identifier",
      label: "Identifier",
      width: "180px",
      render: (value) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5, fontWeight: 500 }}>
          {value as string}
        </span>
      ),
    },
    {
      key: "title",
      label: "Title",
      sortable: true,
      render: (value) => <span style={{ fontWeight: 500 }}>{value as string}</span>,
    },
    {
      key: "description",
      label: "Description",
      render: (value) => (
        <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12.5 }}>
          {(value as string) || "—"}
        </span>
      ),
    },
    {
      key: "is_relevant",
      label: "Relevance",
      width: "140px",
      render: (value) => relevanceChip(value as boolean | null | undefined),
    },
    {
      key: "version",
      label: "Ver",
      width: "60px",
      render: (value) => <VersionPill>{value as number}</VersionPill>,
    },
  ];

  const rowMenuActions = [
    { id: "duplicate", label: "Duplicate", icon: "copy" as const },
    { type: "separator" as const },
    { id: "delete", label: "Delete", icon: "trash" as const, danger: true },
  ];

  const relevanceOptions = [
    { value: "true", label: "Relevant" },
    { value: "false", label: "Irrelevant" },
    { value: "null", label: "Unevaluated" },
  ];

  const bulkActions = [
    { id: "delete", label: "Delete", variant: "danger" as const },
    {
      id: "set-relevance",
      label: "Set relevance",
      variant: "neutral" as const,
      fieldLabel: "Relevance",
      options: relevanceOptions,
      onBulkConfirm: async (ids: string[], value: string) => {
        const isRelevant = value === "true" ? true : value === "false" ? false : null;
        const results = await Promise.allSettled(
          ids.map((id) => relevanceMutation.mutateAsync({ id, isRelevant })),
        );
        const failed = results.filter((r) => r.status === "rejected").length;
        if (failed === 0) {
          toast(
            "success",
            `Updated relevance for ${ids.length} propert${ids.length === 1 ? "y" : "ies"}`,
          );
        } else {
          const succeeded = ids.length - failed;
          const msg =
            succeeded > 0
              ? `Updated ${succeeded}, failed to update ${failed}`
              : `Failed to update ${failed} propert${failed === 1 ? "y" : "ies"}`;
          toast("error", msg);
          throw new Error(msg);
        }
      },
    },
  ];

  const filteredEmpty = hasFilter && total === 0 && (counts.properties ?? 0) > 0;
  const emptyStateTitle = filteredEmpty
    ? propertiesCopy.filteredEmpty.title
    : propertiesCopy.emptyState.title;
  const emptyStateDescription = filteredEmpty
    ? propertiesCopy.filteredEmpty.description
    : propertiesCopy.emptyState.description;

  return (
    <div className="stack" data-testid="properties-page">
      <PageHeader
        eyebrow="SCHEMA · node_type · property_definition"
        title="Properties"
        idChip="/schema/properties"
        subtitle="Property definitions are the named predicates used by relationships. A tri-state relevance flag drives which appear in the inferred graph."
        actions={
          <>
            <Button variant="ghost" onClick={() => {}}>
              <Icon name="filter" size={13} /> Filter
            </Button>
            <Button
              variant="primary"
              onClick={() => surfaceRef.current?.startCreate()}
              data-testid="property-add-button"
            >
              <Icon name="plus" size={13} /> New property
            </Button>
          </>
        }
      />

      <TabBar tabs={schemaTabs} activeTabId="properties" onSelectTab={handleTabNavigate} />

      {error ? (
        <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load properties" />
      ) : (
        <>
          <FilterBar
            data-testid="schema-filter-bar"
            onSearchChange={paging.setSearch}
            searchPlaceholder="Search by identifier or title…"
            showingCount={total ?? 0}
            totalCount={counts.properties ?? total ?? 0}
          />

          <EntitySurface
            ref={surfaceRef}
            entityType="property"
            data={pageData}
            isLoading={isLoading}
            columns={propertyColumns}
            pagination={paging.pagination(total)}
            onSort={paging.onSort}
            onCreateSuccess={paging.resetPage}
            renderInspector={(entity) => <PropertyDrawer key={entity.id} property={entity} />}
            rowMenuActions={rowMenuActions}
            onDeleteEntity={handleDelete}
            bulkActions={bulkActions}
            emptyStateTitle={emptyStateTitle}
            emptyStateDescription={emptyStateDescription}
            emptyStateShowAction={!filteredEmpty}
            emptyStateActionLabel={propertiesCopy.emptyState.actionLabel}
            testId="properties-surface"
          />
        </>
      )}
    </div>
  );
}

export const Route = createFileRoute("/app/schema/properties")({
  component: PropertiesPage,
});
