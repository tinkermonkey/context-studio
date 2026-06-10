import { useRef, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import {
  Button,
  PageHeader,
  FilterBar,
  TabBar,
  Icon,
} from "@tinkermonkey/heimdall-ui";
import type { Column } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EntitySurface, type EntitySurfaceHandle } from "@/components/crud/EntitySurface";
import { TaxonomyDrawer } from "@/components/ontology/TaxonomyDrawer";
import { useTaxonomies, useDeleteTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { taxonomiesCopy } from "./taxonomies/-copy";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];

const SWATCH_PALETTE = [
  "rgb(var(--status-emerald))",
  "rgb(var(--status-amber))",
  "rgb(var(--status-cyan))",
  "rgb(var(--status-violet))",
  "rgb(var(--status-rose))",
  "rgb(var(--accent-primary))",
];

function swatchColor(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i++) {
    h = (h * 31 + id.charCodeAt(i)) >>> 0;
  }
  return SWATCH_PALETTE[h % SWATCH_PALETTE.length];
}

function toIsoDate(input: string): string {
  const d = new Date(input);
  if (Number.isNaN(d.getTime())) return "—";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const taxonomyColumns: Column<TaxonomyResponse>[] = [
  {
    key: "identifier",
    label: "Identifier",
    width: "180px",
    render: (_, row) => {
      const swatch = row.color || swatchColor(row.id);
      return (
        <span className="taxonomy-id-cell">
          <span
            className="taxonomy-id-cell__swatch"
            style={{ background: swatch }}
            aria-hidden="true"
          />
          <span className="taxonomy-id-cell__text">{row.identifier}</span>
        </span>
      );
    },
  },
  {
    key: "title",
    label: "Title",
    sortable: true,
    render: (value) => <span className="taxonomy-title-cell">{value as string}</span>,
  },
  {
    key: "description",
    label: "Description",
    render: (value) => <span className="taxonomy-desc-cell">{(value as string) || "—"}</span>,
  },
  {
    key: "last_modified",
    label: "Updated",
    width: "120px",
    render: (value) => {
      const date = value as string | null;
      return <span className="taxonomy-date-cell">{date ? toIsoDate(date) : "—"}</span>;
    },
  },
];

export function TaxonomiesPage() {
  const surfaceRef = useRef<EntitySurfaceHandle>(null);
  const navigate = useNavigate();
  const { toast } = useToasts();
  const [searchFilter, setSearchFilter] = useState("");

  const { data: listResponse, isLoading, error, refetch } = useTaxonomies();
  const { data: schemesData } = useSchemes();
  const { data: classesData } = useClasses();
  const { data: propsData } = useProperties();
  const { data: relsData } = useRelationships();

  const deleteMutation = useDeleteTaxonomy();

  const allData = listResponse?.items ?? [];
  const hasFilter = !!searchFilter;
  const filteredData = allData.filter(
    (tax: TaxonomyResponse) =>
      tax.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (tax.description?.toLowerCase().includes(searchFilter.toLowerCase()) ?? false) ||
      tax.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const schemaTabs = [
    { id: "taxonomies", label: "Taxonomies", count: listResponse?.total },
    { id: "schemes", label: "Schemes", count: schemesData?.total },
    { id: "classes", label: "Classes", count: classesData?.total },
    { id: "properties", label: "Properties", count: propsData?.total },
    { id: "relationships", label: "Relationships", count: relsData?.items?.length ?? relsData?.total },
  ];

  function handleTabNavigate(tabId: string) {
    const routes: Record<string, string> = {
      taxonomies: "/app/schema/taxonomies",
      schemes: "/app/schema/schemes",
      classes: "/app/schema/classes",
      properties: "/app/schema/properties",
      relationships: "/app/schema/relationships",
    };
    navigate({ to: routes[tabId] as any });
  }

  async function handleDelete(ids: string[]) {
    const results = await Promise.allSettled(ids.map((id) => deleteMutation.mutateAsync(id)));
    const failed = results.filter((r) => r.status === "rejected").length;
    if (failed === 0) {
      toast("success", taxonomiesCopy.delete.successToast);
    } else {
      const succeeded = ids.length - failed;
      const msg = succeeded > 0
        ? `Deleted ${succeeded}, failed to delete ${failed}`
        : `Failed to delete ${failed} taxonom${failed === 1 ? "y" : "ies"}`;
      toast("error", msg);
      throw new Error(msg);
    }
  }

  function handleRowMenuAction(actionId: string, entity: TaxonomyResponse) {
    if (actionId === "add-scheme") {
      navigate({
        to: "/app/schema/schemes/" as any,
        search: { createForTaxonomy: entity.id } as any,
      });
    }
  }

  const rowMenuActions = [
    { id: "duplicate", label: "Duplicate", icon: "copy" as const },
    { id: "add-scheme", label: "Add concept scheme", icon: "plus" as const },
    { type: "separator" as const },
    { id: "delete", label: "Delete", icon: "trash" as const, danger: true },
  ];

  const bulkActions = [
    { id: "delete", label: "Delete", variant: "danger" as const },
  ];

  const filteredEmpty = hasFilter && allData.length > 0 && filteredData.length === 0;
  const emptyStateTitle = filteredEmpty
    ? taxonomiesCopy.filteredEmpty.title
    : taxonomiesCopy.emptyState.title;
  const emptyStateDescription = filteredEmpty
    ? taxonomiesCopy.filteredEmpty.description
    : taxonomiesCopy.emptyState.description;

  return (
    <div className="stack" data-testid="taxonomies-page">
      <PageHeader
        eyebrow="SCHEMA · node_type · taxonomy"
        title="Taxonomies"
        idChip="/schema/taxonomies"
        subtitle="A taxonomy is the top-level domain. It groups concept schemes — each scheme is a focused area of knowledge."
        actions={
          <>
            <Button variant="ghost" onClick={() => {}} data-testid="taxonomy-export-button">
              <Icon name="download" size={13} /> Export
            </Button>
            <Button
              variant="primary"
              onClick={() => surfaceRef.current?.startCreate()}
              data-testid="taxonomy-add-button"
            >
              <Icon name="plus" size={13} /> New taxonomy
            </Button>
          </>
        }
      />

      <TabBar tabs={schemaTabs} activeTabId="taxonomies" onSelectTab={handleTabNavigate} />

      {error ? (
        <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load taxonomies" />
      ) : (
        <>
          <FilterBar
            data-testid="schema-filter-bar"
            onSearchChange={setSearchFilter}
            searchPlaceholder="Search by title or description…"
            showingCount={filteredData.length}
            totalCount={allData.length}
          />

          <EntitySurface
            ref={surfaceRef}
            entityType="taxonomy"
            data={filteredData}
            isLoading={isLoading}
            columns={taxonomyColumns}
            renderInspector={(entity) => (
              <TaxonomyDrawer key={entity.id} taxonomy={entity} />
            )}
            rowMenuActions={rowMenuActions}
            onRowMenuAction={handleRowMenuAction}
            onDeleteEntity={handleDelete}
            bulkActions={bulkActions}
            emptyStateTitle={emptyStateTitle}
            emptyStateDescription={emptyStateDescription}
            emptyStateShowAction={!filteredEmpty}
            testId="taxonomies-surface"
          />
        </>
      )}
    </div>
  );
}

export const Route = createFileRoute("/app/schema/taxonomies")({
  component: TaxonomiesPage,
});
