import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { MoreVertical } from "lucide-react";
import {
  usePipelineFlavors,
  useCreatePipelineFlavor,
} from "@/api/hooks/pipeline";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { FlavorDrawer } from "@/components/pipeline/FlavorDrawer";
import { FlavorForm } from "@/components/pipeline/FlavorForm";
import { useToasts } from "@/components/ui/Toast";
import { COPY } from "./-copy";
import type { PipelineFlavorResponse } from "@/api/services/pipeline";

interface FlavorsSearchParams {
  selected?: string;
}

interface FlavorsPageContentProps {
  onCreateClick: () => void;
  selectedId?: string;
  onSelectedIdChange: (id: string | undefined) => void;
}

function FlavorsPageContent({
  onCreateClick,
  selectedId,
  onSelectedIdChange,
}: FlavorsPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");

  const { data: flavorsResponse, isLoading, error, refetch } = usePipelineFlavors();
  const flavors = flavorsResponse || [];

  const filteredData = flavors.filter(
    (flavor: PipelineFlavorResponse) =>
      flavor.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (flavor.description?.toLowerCase().includes(searchFilter.toLowerCase()) ?? false) ||
      flavor.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const flavorColumns: ColumnDef<PipelineFlavorResponse>[] = [
    {
      accessorKey: "id",
      header: COPY.FLAVOR_ID_HEADER,
      size: 100,
      cell: (info) => (
        <span className="mono">
          {(info.getValue() as string).slice(0, 8)}
        </span>
      ),
    },
    {
      accessorKey: "name",
      header: COPY.FLAVOR_NAME_HEADER,
      cell: (info) => {
        const flavorId = info.row.original.id;
        return (
          <span
            className="row-link"
            onClick={() => onSelectedIdChange(flavorId)}
            data-testid={`flavor-name-${flavorId}`}
            role="button"
          >
            {info.getValue() as string}
          </span>
        );
      },
    },
    {
      accessorKey: "description",
      header: COPY.FLAVOR_DESCRIPTION_HEADER,
      cell: (info) => {
        const desc = (info.getValue() as string) || "—";
        const truncated = desc.length > 50 ? `${desc.slice(0, 50)}…` : desc;
        return (
          <span className="muted-text" title={desc}>
            {truncated}
          </span>
        );
      },
    },
    {
      id: "steps",
      header: COPY.FLAVOR_STEPS_HEADER,
      cell: ({ row }) => (
        <span className="mono" data-testid={`flavor-steps-${row.original.id}`}>
          {row.original.step_count}
        </span>
      ),
    },
    {
      accessorKey: "last_updated",
      header: COPY.FLAVOR_UPDATED_HEADER,
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
          data-testid={`flavor-row-actions-${row.original.id}`}
          className="btn btn-icon"
          onClick={() => onSelectedIdChange(row.original.id)}
          aria-label="View flavor details"
        >
          <MoreVertical size={16} style={{ color: "var(--canvas-fg-3)" }} />
        </button>
      ),
    },
  ];

  if (isLoading) {
    return (
      <div data-testid="flavors-page" className="stack">
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
      <div data-testid="flavors-page" className="stack">
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message={COPY.FLAVORS_LOAD_ERROR}
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  }

  if (flavors.length === 0) {
    return (
      <div data-testid="flavors-page">
        <EmptyState
          title={COPY.NO_FLAVORS_TITLE}
          description={COPY.NO_FLAVORS_DESCRIPTION}
          action={{
            label: COPY.CREATE_A_FLAVOR_CTA,
            onClick: onCreateClick,
          }}
        />
      </div>
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = flavors.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div data-testid="flavors-page">
      <FilterBar searchValue={searchFilter} onSearchChange={setSearchFilter} />

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title={COPY.NO_FLAVORS_FILTERED_TITLE}
            description={COPY.NO_FLAVORS_FILTERED_DESCRIPTION}
          />
        </div>
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderDrawerContent={(flavor) => (
            <FlavorDrawer
              key={flavor.id}
              flavor={flavor}
              onClose={() => onSelectedIdChange(undefined)}
            />
          )}
        >
          <SchemaTable
            columns={flavorColumns}
            data={filteredData}
            onRowSelect={onSelectedIdChange}
            selectedId={selectedId}
            testIdPrefix="flavor"
          />
        </SchemaPageLayout>
      )}
    </div>
  );
}

function FlavorsPageWrapper() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/pipelines/flavors" });
  const selectedId = searchParams.selected;
  const createMutation = useCreatePipelineFlavor();
  const { toast } = useToasts();

  const handleSelectedIdChange = (id: string | undefined) => {
    navigate({
      to: "/app/pipelines/flavors",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  const handleCreateSubmit = async (data: {
    name: string;
    description?: string;
    steps: Array<Record<string, unknown>>;
  }) => {
    setCreateError(null);
    try {
      const result = await createMutation.mutateAsync(data);
      setShowCreateModal(false);
      handleSelectedIdChange(result.id);
      toast("success", COPY.FLAVOR_CREATED(result.name));
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : COPY.FLAVOR_CREATE_ERROR);
    }
  };

  return (
    <div className="stack">
      <div className="page-head">
        <h1>{COPY.FLAVORS_PAGE_TITLE}</h1>
        <Button
          variant="primary"
          onClick={() => setShowCreateModal(true)}
          data-testid="flavor-add-button"
          aria-label="Create new pipeline flavor"
        >
          {COPY.NEW_FLAVOR_BUTTON}
        </Button>
      </div>
      <div data-testid="flavors-content">
        <FlavorsPageContent
          onCreateClick={() => setShowCreateModal(true)}
          selectedId={selectedId}
          onSelectedIdChange={handleSelectedIdChange}
        />
      </div>

      <Modal
        open={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title={COPY.CREATE_FLAVOR_MODAL_TITLE}
        size="lg"
        data-testid="flavor-create-modal"
      >
        {createError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={new Error(createError)}
              onRetry={() => setCreateError(null)}
              message={COPY.FLAVOR_CREATE_ERROR}
            />
          </div>
        )}
        <FlavorForm onSubmit={handleCreateSubmit} isLoading={createMutation.isPending} />
      </Modal>
    </div>
  );
}

export function FlavorsPage() {
  return <FlavorsPageWrapper />;
}

export const Route = createFileRoute("/app/pipelines/flavors")({
  component: FlavorsPage,
  validateSearch: (search: Record<string, unknown>): FlavorsSearchParams => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});
