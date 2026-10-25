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
  SegmentedControl,
  Select,
} from "@tinkermonkey/heimdall-ui";
import type { Column } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EntitySurface, type EntitySurfaceHandle } from "@/components/crud/EntitySurface";
import { deleteFailureMessage } from "@/api/mutationErrors";
import { ClassDrawer } from "@/components/ontology/ClassDrawer";
import {
  useClasses,
  useClassesByIds,
  useDeleteClass,
  useMoveClass,
} from "@/api/hooks/ontology/useClasses";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useListPaging } from "@/hooks/useListPaging";
import { classesCopy } from "./classes/-copy";
import { useSchemaTabs } from "./-useSchemaTabs";
import type { components } from "@/api/types";
import { SMALL_SET_LIMIT } from "@/api/config";
import { EntityNavigator } from "@/components/entity/EntityNavigator";
import { EntityPageLayout } from "@/components/entity/EntityPageParts";

type ClassResponse = components["schemas"]["ClassResponse"];

/** Most concept schemes the domain filter shows as a segmented control. */
const MAX_SEGMENTED_DOMAINS = 4;

interface ClassesSearchParams {
  createForScheme?: string;
}

export function ClassesPage() {
  const surfaceRef = useRef<EntitySurfaceHandle>(null);
  const navigate = useNavigate();
  const { toast } = useToasts();
  const [domainFilter, setDomainFilter] = useState<string>("all");
  const paging = useListPaging(domainFilter);
  const { tabs: schemaTabs, onSelectTab: handleTabNavigate, counts } = useSchemaTabs();

  const searchParams = useSearch({ from: "/app/schema/classes" });
  const createForScheme = searchParams.createForScheme;

  const {
    data: listResponse,
    isLoading,
    error,
    refetch,
  } = useClasses(
    {
      ...paging.params,
      concept_scheme_id: domainFilter === "all" ? undefined : domainFilter,
    },
    { keepPrevious: true },
  );
  // Concept schemes are a small set: the domain filter, scheme chips and the
  // bulk "move to scheme" targets all need every one of them.
  const {
    data: schemesResponse,
    error: schemesError,
    refetch: refetchSchemes,
  } = useSchemes(undefined, { limit: SMALL_SET_LIMIT });

  const deleteMutation = useDeleteClass();
  const moveMutation = useMoveClass();

  const total = listResponse?.total;
  const { clampToTotal } = paging;
  useEffect(() => clampToTotal(total), [total, clampToTotal]);

  const pageData = listResponse?.items ?? [];
  const schemes = schemesResponse?.items ?? [];
  const schemeMap = new Map(schemes.map((s) => [s.id, s.title]));
  // Parent titles for this page only: parents are often on another page.
  const { data: parentsResponse } = useClassesByIds(pageData.map((c) => c.parent_class_id));
  const classMap = new Map(
    [...pageData, ...(parentsResponse?.items ?? [])].map((c) => [c.id, c.title]),
  );

  // Cross-page create: open CreateDrawer with pre-filled scheme if directed from schemes page
  useEffect(() => {
    if (createForScheme && surfaceRef.current) {
      surfaceRef.current.startCreate({ schemeId: createForScheme }, false);
      navigate({ to: "/app/schema/classes" as any, search: {} as any, replace: true });
    }
  }, [createForScheme, navigate]);

  const domainOptions = [
    { value: "all", label: "All domains" },
    ...schemes.map((s) => ({ value: s.id, label: s.title })),
  ];

  const hasFilter = paging.hasSearch || domainFilter !== "all";

  async function handleDelete(ids: string[]) {
    const results = await Promise.allSettled(ids.map((id) => deleteMutation.mutateAsync(id)));
    if (results.every((r) => r.status === "fulfilled")) {
      toast("success", classesCopy.delete.successToast);
      return;
    }
    // Surface the backend's reason (e.g. "Cannot delete: it has N subclass(es)").
    throw new Error(deleteFailureMessage(results, ids.length));
  }

  function handleRowMenuAction(actionId: string, entity: ClassResponse) {
    if (actionId === "add-child-class") {
      surfaceRef.current?.startCreate(
        { schemeId: entity.concept_scheme_id, parentClassId: entity.id },
        false,
      );
    }
  }

  const classColumns: Column<ClassResponse>[] = [
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
      key: "concept_scheme_id",
      label: "Scheme",
      width: "140px",
      render: (value, row) => {
        const schemeName = schemeMap.get(value as string) || "—";
        return (
          <Chip variant="neutral" data-testid={`class-domain-${row.id}`}>
            {schemeName}
          </Chip>
        );
      },
    },
    {
      key: "parent_class_id",
      label: "Parent",
      width: "120px",
      render: (value) => {
        const parentId = value as string | null | undefined;
        if (!parentId)
          return <em style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12 }}>— root —</em>;
        const parentName = classMap.get(parentId);
        return (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11.5,
              color: "rgb(var(--canvas-fg-2))",
            }}
          >
            {parentName || parentId.slice(0, 8)}
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
    { id: "add-child-class", label: "Add child class", icon: "plus" as const },
    { type: "separator" as const },
    { id: "delete", label: "Delete", icon: "trash" as const, danger: true },
  ];

  const bulkActions = [
    { id: "delete", label: "Delete", variant: "danger" as const },
    {
      id: "move-to-scheme",
      label: "Move to scheme",
      variant: "neutral" as const,
      fieldLabel: "Target concept scheme",
      options: schemes.map((s) => ({ value: s.id, label: s.title })),
      onBulkConfirm: async (ids: string[], schemeId: string) => {
        const results = await Promise.allSettled(
          ids.map((id) => moveMutation.mutateAsync({ id, data: { target_scheme_id: schemeId } })),
        );
        const failed = results.filter((r) => r.status === "rejected").length;
        if (failed === 0) {
          toast(
            "success",
            `Moved ${ids.length} class${ids.length === 1 ? "" : "es"} to new scheme`,
          );
        } else {
          const succeeded = ids.length - failed;
          const msg =
            succeeded > 0
              ? `Moved ${succeeded}, failed to move ${failed}`
              : `Failed to move ${failed} class${failed === 1 ? "" : "es"}`;
          toast("error", msg);
          throw new Error(msg);
        }
      },
    },
  ];

  const filteredEmpty = hasFilter && total === 0 && (counts.classes ?? 0) > 0;
  const emptyStateTitle = filteredEmpty
    ? classesCopy.filteredEmpty.title
    : classesCopy.emptyState.title;
  const emptyStateDescription = filteredEmpty
    ? classesCopy.filteredEmpty.description
    : classesCopy.emptyState.description;

  return (
    <EntityPageLayout navigator={<EntityNavigator />} data-testid="schema-navigator-layout">
      <div className="stack" data-testid="classes-page">
        <PageHeader
          eyebrow="SCHEMA · node_type · class"
          title="Classes"
          idChip="/schema/classes"
          subtitle="Classes are the structural nodes of the graph. Each belongs to a concept scheme, inherits from a parent class, and carries data-property definitions populated by pipelines or curators."
          actions={
            <>
              <Button variant="ghost" onClick={() => {}}>
                <Icon name="download" size={13} /> Export
              </Button>
              <Button
                variant="primary"
                onClick={() => surfaceRef.current?.startCreate()}
                data-testid="class-add-button"
              >
                <Icon name="plus" size={13} /> New class
              </Button>
            </>
          }
        />

        <TabBar tabs={schemaTabs} activeTabId="classes" onSelectTab={handleTabNavigate} />

        {error ? (
          <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load classes" />
        ) : (
          <>
            {schemesError && (
              <ErrorBanner
                error={schemesError as Error}
                onRetry={() => refetchSchemes()}
                message="Failed to load domains"
                compact
              />
            )}

            <FilterBar
              data-testid="schema-filter-bar"
              onSearchChange={paging.setSearch}
              searchPlaceholder="Search classes by title or identifier…"
              showingCount={total ?? 0}
              totalCount={counts.classes ?? total ?? 0}
            >
              {/* A segmented control only fits a few schemes; past that it crowds out
                the search input, so the domain filter becomes a dropdown. */}
              {schemes.length > 0 && schemes.length <= MAX_SEGMENTED_DOMAINS && (
                <SegmentedControl
                  value={domainFilter}
                  onChange={(v) => setDomainFilter(v as string)}
                  options={domainOptions}
                />
              )}
              {schemes.length > MAX_SEGMENTED_DOMAINS && (
                <Select
                  value={domainFilter}
                  onChange={setDomainFilter}
                  ariaLabel="Filter by domain"
                  data-testid="class-domain-filter"
                >
                  {domainOptions.map((o) => (
                    <Select.Item key={o.value} value={o.value}>
                      {o.label}
                    </Select.Item>
                  ))}
                </Select>
              )}
            </FilterBar>

            <EntitySurface
              ref={surfaceRef}
              entityType="class"
              data={pageData}
              isLoading={isLoading}
              columns={classColumns}
              pagination={paging.pagination(total)}
              onSort={paging.onSort}
              onCreateSuccess={paging.resetPage}
              renderInspector={(entity) => <ClassDrawer key={entity.id} classData={entity} />}
              rowMenuActions={rowMenuActions}
              onRowMenuAction={handleRowMenuAction}
              onDeleteEntity={handleDelete}
              bulkActions={bulkActions}
              emptyStateTitle={emptyStateTitle}
              emptyStateDescription={emptyStateDescription}
              emptyStateShowAction={!filteredEmpty}
              testId="classes-surface"
            />
          </>
        )}
      </div>
    </EntityPageLayout>
  );
}

export const Route = createFileRoute("/app/schema/classes")({
  component: ClassesPage,
  validateSearch: (search: Record<string, unknown>): ClassesSearchParams => ({
    createForScheme:
      typeof search.createForScheme === "string" ? search.createForScheme : undefined,
  }),
});
