import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { MoreVertical } from "lucide-react";
import { useToasts } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { IndividualEditor } from "@/components/ontology/IndividualEditor";
import { useIndividuals, useCreateIndividual } from "@/api/hooks/ontology/useIndividuals";
import { useClasses } from "@/api/hooks/ontology/useClasses";
import { individualsCopy } from "./individuals/-copy";
import type { components } from "@/api/types";

type IndividualResponse = components["schemas"]["IndividualResponse"];
type ClassResponse = components["schemas"]["ClassResponse"];

interface IndividualsSearchParams {
  selected?: string;
}

interface IndividualsPageContentProps {
  onCreateClick: () => void;
  selectedId?: string;
  onSelectedIdChange: (id?: string) => void;
  classMap: Map<string, string>;
}

function IndividualsPageContent({
  onCreateClick,
  selectedId,
  onSelectedIdChange,
  classMap,
}: IndividualsPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");

  const { data: listResponse, isLoading, error, refetch } = useIndividuals();
  const individuals = listResponse?.items || [];

  const filteredData = individuals.filter(
    (individual: IndividualResponse) =>
      individual.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      individual.description?.toLowerCase().includes(searchFilter.toLowerCase()) ||
      individual.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const individualColumns: ColumnDef<IndividualResponse>[] = [
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
      accessorKey: "title",
      header: "Name",
      cell: (info) => {
        const individualId = info.row.original.id;
        return (
          <span
            style={{
              color: "var(--cyan-600, #0891b2)",
              fontWeight: 500,
              cursor: "pointer",
            }}
            data-testid={`individual-name-${individualId}`}
            onClick={() => onSelectedIdChange(individualId)}
          >
            {info.getValue() as string}
          </span>
        );
      },
    },
    {
      accessorKey: "class_ids",
      header: "Classes",
      cell: (info) => {
        const classIds = info.getValue() as string[];
        return (
          <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
            {classIds.map((classId) => {
              const className = classMap.get(classId) || "Unknown";
              return (
                <span
                  key={classId}
                  style={{
                    backgroundColor: "var(--canvas-bg-2)",
                    color: "var(--canvas-fg)",
                    padding: "4px 8px",
                    borderRadius: "4px",
                    fontSize: "var(--text-xs)",
                    fontWeight: 500,
                  }}
                  data-testid={`individual-class-chip-${classId}`}
                >
                  {className}
                </span>
              );
            })}
          </div>
        );
      },
    },
    {
      accessorKey: "description",
      header: "Description",
      cell: (info) => {
        const desc = info.getValue() as string | null | undefined;
        if (!desc) return <span className="muted-text">—</span>;
        const truncated = desc.length > 50 ? desc.slice(0, 50) + "…" : desc;
        return <span>{truncated}</span>;
      },
    },
    {
      accessorKey: "last_modified",
      header: "Updated",
      cell: (info) => {
        const date = info.getValue() as string | null;
        if (!date) return "—";
        return new Date(date).toLocaleDateString();
      },
    },
    {
      id: "actions",
      header: "",
      size: 40,
      cell: ({ row }) => (
        <button data-testid={`individual-row-actions-${row.original.id}`} className="btn btn-icon">
          <MoreVertical size={16} style={{ color: "var(--canvas-fg-3)" }} />
        </button>
      ),
    },
  ];

  if (isLoading) {
    return (
      <div className="stack">
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
      <div className="stack">
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message="Failed to load individuals"
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  }

  if (individuals.length === 0) {
    return (
      <EmptyState
        title={individualsCopy.emptyState.title}
        description={individualsCopy.emptyState.description}
        action={{
          label: individualsCopy.emptyState.actionLabel,
          onClick: onCreateClick,
        }}
      />
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = individuals.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div>
      <FilterBar searchValue={searchFilter} onSearchChange={setSearchFilter} />

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title={individualsCopy.filteredEmpty.title}
            description={individualsCopy.filteredEmpty.description}
          />
        </div>
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderDrawerContent={() => {
            return (
              <div style={{ padding: "var(--space-4)", color: "var(--canvas-fg-3)" }}>
                Individual details drawer coming soon
              </div>
            );
          }}
        >
          <SchemaTable
            columns={individualColumns}
            data={filteredData}
            onRowSelect={onSelectedIdChange}
            selectedId={selectedId}
            testIdPrefix="individual"
          />
        </SchemaPageLayout>
      )}
    </div>
  );
}

function IndividualsPageWrapper() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/data/individuals" });
  const selectedId = searchParams.selected;
  const createMutation = useCreateIndividual();
  const { toast } = useToasts();

  const { data: classesResponse } = useClasses();
  const classes = classesResponse?.items || [];
  const classMap = new Map(classes.map((c: ClassResponse) => [c.id, c.title]));

  const handleSelectedIdChange = (id?: string) => {
    navigate({
      to: "/app/data/individuals",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  const handleCreateSubmit = async (data: {
    title: string;
    description?: string | null;
    class_ids: string[];
  }) => {
    setCreateError(null);
    try {
      await createMutation.mutateAsync({
        title: data.title,
        description: data.description,
        class_ids: data.class_ids,
      });
      setShowCreateModal(false);
      toast("success", individualsCopy.create.successToast);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Failed to create individual");
    }
  };

  return (
    <div className="stack" data-testid="individuals-page">
      <div className="flex-between">
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>Individuals</h1>
        <div className="row">
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="individual-add-button"
          >
            + New individual
          </Button>
        </div>
      </div>
      <div>
        <IndividualsPageContent
          onCreateClick={() => setShowCreateModal(true)}
          selectedId={selectedId}
          onSelectedIdChange={handleSelectedIdChange}
          classMap={classMap}
        />
      </div>

      <Modal
        open={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title="Create Individual"
        size="md"
        data-testid="individual-create-modal"
      >
        {createError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={new Error(createError)}
              onRetry={() => setCreateError(null)}
              message="Failed to create individual"
              daemonLogPath="/local-server/logs/context_studio.log"
            />
          </div>
        )}
        <IndividualEditor onSubmit={handleCreateSubmit} isLoading={createMutation.isPending} />
      </Modal>
    </div>
  );
}

export function IndividualsPage() {
  return <IndividualsPageWrapper />;
}

export const Route = createFileRoute("/app/data/individuals")({
  component: IndividualsPage,
  validateSearch: (search: Record<string, unknown>): IndividualsSearchParams => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});
