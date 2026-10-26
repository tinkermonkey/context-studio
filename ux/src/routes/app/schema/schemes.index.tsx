import { useRef, useEffect } from "react";
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
import { deleteFailureMessage } from "@/api/mutationErrors";
import { SchemeDrawer } from "@/components/ontology/SchemeDrawer";
import { useSchemes, useDeleteScheme, useMoveScheme } from "@/api/hooks/ontology/useSchemes";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useListPaging } from "@/hooks/useListPaging";
import { schemesCopy } from "./schemes/-copy";
import { useSchemaTabs } from "./-useSchemaTabs";
import type { components } from "@/api/types";
import { SMALL_SET_LIMIT } from "@/api/config";
import { EntityNavigator, SCHEMA_LIST_MODE_LINKS } from "@/components/entity/EntityNavigator";
import { EntityPageLayout } from "@/components/entity/EntityPageParts";

type ConceptSchemeResponse = components["schemas"]["ConceptSchemeResponse"];

interface SchemesSearchParams {
  createForTaxonomy?: string;
}

export function SchemesIndexPage() {
  const surfaceRef = useRef<EntitySurfaceHandle>(null);
  const navigate = useNavigate();
  const { toast } = useToasts();
  const paging = useListPaging();
  const { tabs: schemaTabs, onSelectTab: handleTabNavigate, counts } = useSchemaTabs();

  const searchParams = useSearch({ from: "/app/schema/schemes/" });
  const createForTaxonomy = searchParams.createForTaxonomy;

  const {
    data: taxonomiesResponse,
    error: taxonomiesError,
    refetch: refetchTaxonomies,
  } = useTaxonomies({ limit: SMALL_SET_LIMIT });
  const taxonomies = taxonomiesResponse?.items ?? [];
  const taxonomiesById = new Map(taxonomies.map((t) => [t.id, t.title]));

  const {
    data: listResponse,
    isLoading,
    error,
    refetch,
  } = useSchemes(undefined, paging.params, { keepPrevious: true });

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

  const total = listResponse?.total;
  const { clampToTotal } = paging;
  useEffect(() => clampToTotal(total), [total, clampToTotal]);
  const pageData = listResponse?.items ?? [];
  const hasFilter = paging.hasSearch;

  async function handleDelete(ids: string[]) {
    const results = await Promise.allSettled(ids.map((id) => deleteMutation.mutateAsync(id)));
    if (results.every((r) => r.status === "fulfilled")) {
      toast("success", schemesCopy.delete.successToast);
      return;
    }
    // Surface the backend's reason (e.g. "Cannot delete: it has N class(es)").
    throw new Error(deleteFailureMessage(results, ids.length));
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
        const results = await Promise.allSettled(
          ids.map((id) =>
            moveMutation.mutateAsync({ id, data: { target_taxonomy_id: taxonomyId } }),
          ),
        );
        const failed = results.filter((r) => r.status === "rejected").length;
        if (failed === 0) {
          toast(
            "success",
            `Moved ${ids.length} scheme${ids.length === 1 ? "" : "s"} to new taxonomy`,
          );
        } else {
          const succeeded = ids.length - failed;
          const msg =
            succeeded > 0
              ? `Moved ${succeeded}, failed to move ${failed}`
              : `Failed to move ${failed} scheme${failed === 1 ? "" : "s"}`;
          toast("error", msg);
          throw new Error(msg);
        }
      },
    },
  ];

  const filteredEmpty = hasFilter && total === 0 && (counts.schemes ?? 0) > 0;
  const emptyStateTitle = filteredEmpty
    ? schemesCopy.filteredEmpty.title
    : schemesCopy.emptyState.title;
  const emptyStateDescription = filteredEmpty
    ? schemesCopy.filteredEmpty.description
    : schemesCopy.emptyState.description;

  return (
    <EntityPageLayout
      navigator={<EntityNavigator defaultMode="schema" modeLinks={SCHEMA_LIST_MODE_LINKS} />}
      data-testid="schema-navigator-layout"
    >
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
              onSearchChange={paging.setSearch}
              searchPlaceholder="Search by title or identifier…"
              showingCount={total ?? 0}
              totalCount={counts.schemes ?? total ?? 0}
            />

            <EntitySurface
              ref={surfaceRef}
              entityType="scheme"
              data={pageData}
              isLoading={isLoading}
              columns={schemeColumns}
              pagination={paging.pagination(total)}
              onSort={paging.onSort}
              onCreateSuccess={paging.resetPage}
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
    </EntityPageLayout>
  );
}

export const Route = createFileRoute("/app/schema/schemes/")({
  component: SchemesIndexPage,
  validateSearch: (search: Record<string, unknown>): SchemesSearchParams => ({
    createForTaxonomy:
      typeof search.createForTaxonomy === "string" ? search.createForTaxonomy : undefined,
  }),
});
