import { Button, Modal, PageHeader, FilterBar } from "@tinkermonkey/heimdall-ui";
import { useState, useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { useFlavors, useCreateFlavor, useDeleteFlavor } from "@/api/hooks/flavor";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";

import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { FlavorForm } from "@/components/pipeline/FlavorForm";
import { FlavorDrawer } from "@/components/pipeline/FlavorDrawer";
import { COPY } from "./-copy";
import type { components } from "@/api/types";

type PipelineFlavorResponse = components["schemas"]["PipelineFlavorResponse"];

function FlavorsContent() {
  const { data: flavors = [], isLoading, error, refetch } = useFlavors();
  const createFlavor = useCreateFlavor();
  const deleteFlavor = useDeleteFlavor();

  const [searchFilter, setSearchFilter] = useState("");
  const [selectedFlavorId, setSelectedFlavorId] = useState<string | undefined>(undefined);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const filteredFlavors = useMemo(() => {
    if (!searchFilter) return flavors;
    const query = searchFilter.toLowerCase();
    return flavors.filter(
      (f) => f.name.toLowerCase().includes(query) || f.description.toLowerCase().includes(query),
    );
  }, [flavors, searchFilter]);

  const selectedFlavor = flavors.find((f) => f.id === selectedFlavorId);

  const flavorColumns: Column<PipelineFlavorResponse>[] = [
    {
      key: "name",
      label: "Name",
      sortable: true,
      render: (value, row) => (
        <span
          data-testid={`flavor-name-${row.id}`}
          className="cursor-pointer hover:underline"
          onClick={() => setSelectedFlavorId(row.id)}
          role="button"
        >
          {value as string}
        </span>
      ),
    },
    {
      key: "step_count",
      label: "Steps",
      width: "80px",
      render: (value, row) => (
        <span data-testid={`flavor-steps-${row.id}`}>{value as number}</span>
      ),
    },
    {
      key: "id",
      label: "",
      width: "50px",
      render: (_, row) => (
        <button
          data-testid={`flavor-row-actions-${row.id}`}
          onClick={() => setSelectedFlavorId(row.id)}
          className="text-sm text-blue-500 hover:underline"
        >
          View
        </button>
      ),
    },
  ];

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = flavors.length > 0 && filteredFlavors.length === 0 && hasFilters;

  return (
    <div data-testid="flavors-page">
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create New Flavor"
      >
        <FlavorForm
          onSubmit={async (data) => {
            await createFlavor.mutateAsync(data);
            setShowCreateModal(false);
          }}
          onCancel={() => setShowCreateModal(false)}
          isLoading={createFlavor.isPending}
        />
      </Modal>

      <SchemaPageLayout
        data={filteredFlavors}
        selectedId={selectedFlavorId}
        renderDrawerContent={(flavor) =>
          flavor &&
          selectedFlavor && (
            <FlavorDrawer
              flavor={selectedFlavor}
              onClose={() => setSelectedFlavorId(undefined)}
              onDelete={async (id) => {
                await deleteFlavor.mutateAsync(id);
                setSelectedFlavorId(undefined);
              }}
              isDeleting={deleteFlavor.isPending}
            />
          )
        }
      >
        <div data-testid="flavors-content" className="stack">
          <PageHeader
            eyebrow="Pipelines"
            title={COPY.FLAVORS_PAGE_TITLE}
            idChip="/pipelines/flavors"
            actions={
              <Button
                variant="primary"
                onClick={() => setShowCreateModal(true)}
                data-testid="flavor-add-button"
              >
                <Plus size={16} style={{ marginRight: "4px" }} />
                {COPY.NEW_FLAVOR_BUTTON}
              </Button>
            }
          />

          {isLoading ? (
            <>
              <Skeleton height={40} />
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} height={40} />
              ))}
            </>
          ) : error ? (
            <ErrorBanner
              error={error}
              onRetry={() => refetch()}
              message={COPY.FLAVORS_LOAD_ERROR}
              daemonLogPath="/local-server/logs/context_studio.log"
            />
          ) : (
            <>
              <FilterBar
                searchPlaceholder={COPY.SEARCH_FLAVORS_PLACEHOLDER}
                onSearchChange={setSearchFilter}
                showingCount={filteredFlavors.length}
                totalCount={flavors.length}
                data-testid="flavors-filter-bar"
              />

              {showFilteredEmpty ? (
                <EmptyState
                  title={COPY.NO_FLAVORS_FILTERED_TITLE}
                  description={COPY.NO_FLAVORS_FILTERED_DESCRIPTION}
                />
              ) : flavors.length === 0 ? (
                <EmptyState
                  title={COPY.NO_FLAVORS_TITLE}
                  description={COPY.NO_FLAVORS_DESCRIPTION}
                  action={{
                    label: COPY.CREATE_FLAVOR_CTA,
                    onClick: () => setShowCreateModal(true),
                  }}
                />
              ) : (
                <SchemaTable columns={flavorColumns} data={filteredFlavors} testIdPrefix="flavor-row" />
              )}
            </>
          )}
        </div>
      </SchemaPageLayout>
    </div>
  );
}

export const Route = createFileRoute("/app/pipelines/flavors")({
  component: FlavorsContent,
});
