import { useRef, useState, useEffect } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
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
import { SchemeDrawer } from "@/components/ontology/SchemeDrawer";
import { useSchemes, useDeleteScheme, useMoveScheme } from "@/api/hooks/ontology/useSchemes";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useRelationships } from "@/api/hooks/ontology/useRelationships";
import { schemesCopy } from "./schemes/-copy";
import type { components } from "@/api/types";

type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];

interface SchemesSearchParams {
  createForTaxonomy?: string;
}

export function SchemesIndexPage() {
  const surfaceRef = useRef<EntitySurfaceHandle>(null);
  const navigate = useNavigate();
  const { toast } = useToasts();
  const [searchFilter, setSearchFilter] = useState("");

  const searchParams = useSearch({ from: "/app/schema/schemes/" });
  const createForTaxonomy = searchParams.createForTaxonomy;

  const {
    data: taxonomiesResponse,
    error: taxonomiesError,
    refetch: refetchTaxonomies,
  } = useTaxonomies();
  const taxonomies = taxonomiesResponse?.items ?? [];
  const taxonomiesById = new Map(taxonomies.map((t) => [t.id, t.title]));

  const { data: listResponse, isLoading, error, refetch } = useSchemes();
  const { data: classesData } = useClasses();
  const { data: propsData } = useProperties();
  const { data: relsData } = useRelationships();

  const deleteMutation = useDeleteScheme();
  const moveMutation = useMoveScheme();

  // Cross-page create: open CreateDrawer with pre-filled taxonomy if directed from taxonomies page
  useEffect(() => {
    if (createForTaxonomy && surfaceRef.current) {
      surfaceRef.current.startCreate({ taxonomyId: createForTaxonomy }, false);
      // Clear the param so navigating back doesn't re-open
      navigate({ to: "/app/schema/schemes/" as any, search: {} as any, replace: true });
    }
  }, [createForTaxonomy, navigate]);

  const allData = listResponse?.items ?? [];
  const hasFilter = !!searchFilter;
  const filteredData = allData.filter(
    (scheme: ConceptSchemeResponse) =>
      scheme.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (scheme.description?.toLowerCase().includes(searchFilter.toLowerCase()) ?? false) ||
      scheme.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const schemaTabs = [
    { id: "taxonomies", label: "Taxonomies", count: taxonomiesResponse?.total },
    { id: "schemes", label: "Schemes", count: listResponse?.total },
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
    try {
      for (const id of ids) {
        await deleteMutation.mutateAsync(id);
      }
      toast("success", schemesCopy.delete.successToast);
    } catch (error) {
      toast("error", error instanceof Error ? error.message : "Failed to delete scheme");
      throw error;
    }
  }

  function handleRowMenuAction(actionId: string, entity: ConceptSchemeResponse) {
    if (actionId === "add-class") {
      navigate({
        to: "/app/schema/classes" as any,
        search: { createForScheme: entity.id } as any,
      });
    }
  }

  const schemeColumns: Column<ConceptSchemeResponse>[] = [
    {
      key: "id",
      label: "Identifier",
      width: "160px",
      render: (value) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>
          {(value as string).slice(0, 8)}
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
      key: "taxonomy_id",
      label: "Taxonomy",
      width: "160px",
      render: (value) => {
        const taxName = taxonomiesById.get(value as string) || "—";
        return <Chip variant="neutral">{taxName}</Chip>;
      },
    },
    {
      key: "last_modified",
      label: "Updated",
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
    {
      key: "version",
      label: "Ver",
      width: "60px",
      render: (value) => <VersionPill>{value as number}</VersionPill>,
    },
  ];

  const rowMenuActions = [
    { id: "duplicate", label: "Duplicate", icon: "copy" as const },
    { id: "add-class", label: "Add class", icon: "plus" as const },
    { type: "separator" as const },
    { id: "delete", label: "Delete", icon: "trash" as const, danger: true },
  ];

  const bulkActions = [
    { id: "delete", label: "Delete", variant: "danger" as const },
    {
      id: "move-to-taxonomy",
      label: "Move to taxonomy",
      variant: "neutral" as const,
      fieldLabel: "Target taxonomy",
      options: taxonomies.map((t) => ({ value: t.id, label: t.title })),
      onBulkConfirm: async (ids: string[], taxonomyId: string) => {
        for (const id of ids) {
          await moveMutation.mutateAsync({ id, data: { target_taxonomy_id: taxonomyId } });
        }
        toast("success", `Moved ${ids.length} scheme${ids.length === 1 ? "" : "s"} to new taxonomy`);
      },
    },
  ];

  const filteredEmpty = hasFilter && allData.length > 0 && filteredData.length === 0;
  const emptyStateTitle = filteredEmpty
    ? schemesCopy.filteredEmpty.title
    : schemesCopy.emptyState.title;
  const emptyStateDescription = filteredEmpty
    ? schemesCopy.filteredEmpty.description
    : schemesCopy.emptyState.description;

  return (
    <div className="stack" data-testid="schemes-page">
      <PageHeader
        eyebrow="SCHEMA · node_type · concept_scheme"
        title="Concept Schemes"
        idChip="/schema/schemes"
        subtitle="A concept scheme is a focused vocabulary inside a taxonomy. Classes belong to exactly one scheme."
        actions={
          <>
            <Button variant="ghost" onClick={() => {}} data-testid="scheme-export-button">
              <Icon name="download" size={13} /> Export
            </Button>
            <Button
              variant="primary"
              onClick={() => surfaceRef.current?.startCreate()}
              data-testid="scheme-add-button"
            >
              <Icon name="plus" size={13} /> New scheme
            </Button>
          </>
        }
      />

      <TabBar tabs={schemaTabs} activeTabId="schemes" onSelectTab={handleTabNavigate} />

      {error ? (
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message="Failed to load concept schemes"
        />
      ) : (
        <>
          {taxonomiesError && (
            <ErrorBanner
              error={taxonomiesError}
              onRetry={() => refetchTaxonomies()}
              message="Failed to load parent taxonomies"
              compact
            />
          )}

          <FilterBar
            data-testid="schema-filter-bar"
            onSearchChange={setSearchFilter}
            searchPlaceholder="Search by title or description…"
            showingCount={filteredData.length}
            totalCount={allData.length}
          />

          <EntitySurface
            ref={surfaceRef}
            entityType="scheme"
            data={filteredData}
            isLoading={isLoading}
            columns={schemeColumns}
            renderInspector={(entity) => (
              <SchemeDrawer
                key={entity.id}
                scheme={entity}
                taxonomyName={taxonomiesById.get(entity.taxonomy_id) || "—"}
              />
            )}
            rowMenuActions={rowMenuActions}
            onRowMenuAction={handleRowMenuAction}
            onDeleteEntity={handleDelete}
            bulkActions={bulkActions}
            emptyStateTitle={emptyStateTitle}
            emptyStateDescription={emptyStateDescription}
            emptyStateShowAction={!filteredEmpty}
            testId="schemes-surface"
          />
        </>
      )}
    </div>
  );
}

export const Route = createFileRoute("/app/schema/schemes/")({
  component: SchemesIndexPage,
  validateSearch: (search: Record<string, unknown>): SchemesSearchParams => ({
    createForTaxonomy: typeof search.createForTaxonomy === "string" ? search.createForTaxonomy : undefined,
  }),
});
