import { useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { Button, PageHeader, FilterBar, Icon, Chip, VersionPill } from "@tinkermonkey/heimdall-ui";
import type { Column } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EntitySurface, type EntitySurfaceHandle } from "@/components/crud/EntitySurface";
import { deleteFailureMessage } from "@/api/mutationErrors";
import { IndividualDrawer } from "@/components/ontology/IndividualDrawer";
import { useIndividuals, useDeleteIndividual } from "@/api/hooks/ontology/useIndividuals";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { individualsCopy } from "./individuals/-copy";
import type { components } from "@/api/types";

type IndividualResponse = components["schemas"]["IndividualResponse"];

export function IndividualsPage() {
  const surfaceRef = useRef<EntitySurfaceHandle>(null);
  const { toast } = useToasts();
  const [searchFilter, setSearchFilter] = useState("");

  const { data: listResponse, isLoading, error, refetch } = useIndividuals();
  const { data: classesResponse, error: classesError, refetch: refetchClasses } = useClasses();

  const deleteMutation = useDeleteIndividual();

  const classes = classesResponse?.items ?? [];
  const classMap = new Map(classes.map((c) => [c.id, c.title]));

  const allData = listResponse?.items ?? [];
  const hasFilter = !!searchFilter;
  const filteredData = allData.filter(
    (individual: IndividualResponse) =>
      individual.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (individual.description?.toLowerCase().includes(searchFilter.toLowerCase()) ?? false) ||
      individual.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  async function handleDelete(ids: string[]) {
    const results = await Promise.allSettled(ids.map((id) => deleteMutation.mutateAsync(id)));
    if (results.every((r) => r.status === "fulfilled")) {
      toast("success", individualsCopy.delete.successToast);
      return;
    }
    // Surface the backend's reason if the delete is rejected.
    throw new Error(deleteFailureMessage(results, ids.length));
  }

  const individualColumns: Column<IndividualResponse>[] = [
    {
      key: "id",
      label: individualsCopy.table.idHeader,
      width: "120px",
      render: (value) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12.5 }}>
          {(value as string).slice(0, 8)}
        </span>
      ),
    },
    {
      key: "title",
      label: individualsCopy.table.nameHeader,
      sortable: true,
      render: (value, row) => (
        <span
          className="cursor-pointer"
          style={{ fontWeight: 500 }}
          data-testid={`individual-name-${row.id}`}
        >
          {value as string}
        </span>
      ),
    },
    {
      key: "description",
      label: individualsCopy.table.descriptionHeader,
      render: (value) => (
        <span style={{ color: "rgb(var(--canvas-fg-3))", fontSize: 12.5 }}>
          {(value as string) || "—"}
        </span>
      ),
    },
    {
      key: "class_ids",
      label: individualsCopy.table.classesHeader,
      width: "200px",
      render: (value) => {
        const classIds = value as string[];
        return (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {classIds.map((classId) => (
              <Chip
                key={classId}
                variant="neutral"
                data-testid={`individual-class-chip-${classId}`}
              >
                {classMap.get(classId) || individualsCopy.drawer.classNameFallback}
              </Chip>
            ))}
          </div>
        );
      },
    },
    {
      key: "version",
      label: individualsCopy.table.versionHeader,
      width: "60px",
      render: (value) => <VersionPill>{value as number}</VersionPill>,
    },
  ];

  const rowMenuActions = [{ id: "delete", label: "Delete", icon: "trash" as const, danger: true }];

  const bulkActions = [{ id: "delete", label: "Delete", variant: "danger" as const }];

  const filteredEmpty = hasFilter && allData.length > 0 && filteredData.length === 0;
  const emptyStateTitle = filteredEmpty
    ? individualsCopy.filteredEmpty.title
    : individualsCopy.emptyState.title;
  const emptyStateDescription = filteredEmpty
    ? individualsCopy.filteredEmpty.description
    : individualsCopy.emptyState.description;

  return (
    <div className="stack" data-testid="individuals-page">
      <PageHeader
        eyebrow="DATA · node_type · individual"
        title={individualsCopy.pageTitle}
        idChip="/data/individuals"
        subtitle={individualsCopy.subtitle}
        actions={
          <Button
            variant="primary"
            onClick={() => surfaceRef.current?.startCreate()}
            data-testid="individual-add-button"
          >
            <Icon name="plus" size={13} /> {individualsCopy.create.buttonLabel}
          </Button>
        }
      />

      {error ? (
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message={individualsCopy.errors.failedToLoad}
        />
      ) : (
        <>
          {classesError && (
            <ErrorBanner
              error={classesError}
              onRetry={() => refetchClasses()}
              message={individualsCopy.errors.failedToLoadClasses}
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
            entityType="individual"
            data={filteredData}
            isLoading={isLoading}
            columns={individualColumns}
            renderInspector={(entity, { selectEntity }) => (
              <IndividualDrawer
                key={entity.id}
                individualId={entity.id}
                onSelectIndividual={selectEntity}
              />
            )}
            rowMenuActions={rowMenuActions}
            onDeleteEntity={handleDelete}
            bulkActions={bulkActions}
            emptyStateTitle={emptyStateTitle}
            emptyStateDescription={emptyStateDescription}
            emptyStateShowAction={!filteredEmpty}
            emptyStateActionLabel={individualsCopy.emptyState.actionLabel}
            testId="individuals-surface"
          />
        </>
      )}
    </div>
  );
}

export const Route = createFileRoute("/app/data/individuals")({
  component: IndividualsPage,
});
