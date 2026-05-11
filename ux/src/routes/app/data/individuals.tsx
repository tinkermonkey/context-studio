import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { Edit2, Trash2 } from "lucide-react";
import { useToasts } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { Sparkline } from "@/components/ui/Sparkline";
import { FilterBar } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { IndividualEditor } from "@/components/ontology/IndividualEditor";
import { IndividualDrawer } from "@/components/ontology/IndividualDrawer";
import {
  useIndividuals,
  useCreateIndividual,
  useUpdateIndividual,
  useDeleteIndividual,
} from "@/api/hooks/ontology/useIndividuals";
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
  classesError: boolean;
  classesErrorObj: Error | null;
  onRetryClasses: () => void;
  onEditClick: (id: string) => void;
  onDeleteClick: (id: string) => void;
}

function IndividualsPageContent({
  onCreateClick,
  selectedId,
  onSelectedIdChange,
  classMap,
  classesError,
  classesErrorObj,
  onRetryClasses,
  onEditClick,
  onDeleteClick,
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
      header: individualsCopy.table.idHeader,
      size: 100,
      cell: (info) => (
        <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
          {(info.getValue() as string).slice(0, 8)}
        </span>
      ),
    },
    {
      accessorKey: "title",
      header: individualsCopy.table.nameHeader,
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
      header: individualsCopy.table.classesHeader,
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
      header: individualsCopy.table.descriptionHeader,
      cell: (info) => {
        const desc = info.getValue() as string | null | undefined;
        if (!desc) return <span className="muted-text">—</span>;
        const truncated = desc.length > 50 ? desc.slice(0, 50) + "…" : desc;
        return <span>{truncated}</span>;
      },
    },
    {
      accessorKey: "last_modified",
      header: individualsCopy.table.updatedHeader,
      cell: (info) => {
        const date = info.getValue() as string | null;
        const version = info.row.original.version;
        return (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
            <Sparkline version={version} lastModified={date} maxHeight={16} />
            <span style={{ fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)" }}>
              {date ? new Date(date).toLocaleDateString() : "—"}
            </span>
          </div>
        );
      },
    },
    {
      id: "actions",
      header: "",
      size: 40,
      cell: ({ row }) => (
        <div style={{ display: "flex", gap: "var(--space-1)" }}>
          <button
            type="button"
            onClick={() => onEditClick(row.original.id)}
            className="btn btn-icon"
            data-testid={`individual-row-edit-${row.original.id}`}
          >
            <Edit2 size={16} style={{ color: "var(--canvas-fg-3)" }} />
          </button>
          <button
            type="button"
            onClick={() => onDeleteClick(row.original.id)}
            className="btn btn-icon"
            data-testid={`individual-row-delete-${row.original.id}`}
          >
            <Trash2 size={16} style={{ color: "var(--canvas-fg-3)" }} />
          </button>
        </div>
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
          message={individualsCopy.errors.failedToLoad}
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
      {classesError && (
        <div style={{ marginBottom: "var(--space-3)" }}>
          <ErrorBanner
            error={classesErrorObj || new Error(individualsCopy.errors.failedToLoadClasses)}
            onRetry={onRetryClasses}
            message={individualsCopy.errors.failedToLoadClasses}
          />
        </div>
      )}
      <FilterBar searchValue={searchFilter} onSearchChange={setSearchFilter} />

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState
            title={individualsCopy.filteredEmpty.title}
            description={individualsCopy.filteredEmpty.description}
          />
        </div>
      ) : (
        <SchemaTable
          columns={individualColumns}
          data={filteredData}
          onRowSelect={onSelectedIdChange}
          selectedId={selectedId}
          testIdPrefix="individual"
        />
      )}
    </div>
  );
}

function IndividualsPageWrapper() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/data/individuals" });
  const selectedId = searchParams.selected;
  const createMutation = useCreateIndividual();
  const updateMutation = useUpdateIndividual();
  const deleteMutation = useDeleteIndividual();
  const { toast } = useToasts();

  const { data: classesResponse, isError: classesError, error: classesErrorObj, refetch: refetchClasses } = useClasses();
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
      const result = await createMutation.mutateAsync({
        title: data.title,
        description: data.description,
        class_ids: data.class_ids,
      });
      setShowCreateModal(false);
      handleSelectedIdChange(result.id);
      toast("success", individualsCopy.create.successToast);
    } catch (error) {
      setCreateError(
        error instanceof Error ? error.message : individualsCopy.errors.failedToCreate,
      );
    }
  };

  const handleEditClick = (id: string) => {
    setEditingId(id);
    setShowEditModal(true);
    setEditError(null);
  };

  const handleEditSubmit = async (data: {
    title: string;
    description?: string | null;
    class_ids: string[];
  }) => {
    setEditError(null);
    if (!editingId) return;

    try {
      await updateMutation.mutateAsync({
        id: editingId,
        data: {
          title: data.title,
          description: data.description,
        },
      });
      setShowEditModal(false);
      setEditingId(null);
      toast("success", individualsCopy.edit.successToast);
    } catch (error) {
      setEditError(error instanceof Error ? error.message : individualsCopy.errors.failedToUpdate);
    }
  };

  const handleDeleteClick = (id: string) => {
    if (confirm(individualsCopy.delete.confirmMessage)) {
      deleteMutation
        .mutateAsync(id)
        .then(() => {
          if (selectedId === id) {
            handleSelectedIdChange(undefined);
          }
          toast("success", individualsCopy.delete.successToast);
        })
        .catch((error) => {
          toast(
            "error",
            error instanceof Error ? error.message : individualsCopy.delete.errorToast,
          );
        });
    }
  };

  return (
    <div className="stack" data-testid="individuals-page">
      <div className="flex-between">
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>{individualsCopy.pageTitle}</h1>
        <div className="row">
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="individual-add-button"
          >
            {individualsCopy.create.buttonLabel}
          </Button>
        </div>
      </div>
      <div>
        <IndividualsPageContent
          onCreateClick={() => setShowCreateModal(true)}
          selectedId={selectedId}
          onSelectedIdChange={handleSelectedIdChange}
          classMap={classMap}
          classesError={classesError}
          classesErrorObj={classesErrorObj || null}
          onRetryClasses={() => refetchClasses()}
          onEditClick={handleEditClick}
          onDeleteClick={handleDeleteClick}
        />
      </div>

      <IndividualDrawer
        individualId={selectedId || null}
        onClose={() => handleSelectedIdChange(undefined)}
        onSelectIndividual={handleSelectedIdChange}
      />

      <Modal
        open={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title={individualsCopy.create.modalTitle}
        size="md"
        data-testid="individual-create-modal"
      >
        {createError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={new Error(createError)}
              onRetry={() => setCreateError(null)}
              message={individualsCopy.errors.failedToCreate}
              daemonLogPath="/local-server/logs/context_studio.log"
            />
          </div>
        )}
        <IndividualEditor onSubmit={handleCreateSubmit} isLoading={createMutation.isPending} />
      </Modal>

      <Modal
        open={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditingId(null);
          setEditError(null);
        }}
        title={individualsCopy.edit.modalTitle}
        size="md"
        data-testid="individual-edit-modal"
      >
        {editError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={new Error(editError)}
              onRetry={() => setEditError(null)}
              message={individualsCopy.errors.failedToUpdate}
              daemonLogPath="/local-server/logs/context_studio.log"
            />
          </div>
        )}
        {editingId && (
          <IndividualEditor
            individualId={editingId}
            onSubmit={handleEditSubmit}
            isLoading={updateMutation.isPending}
          />
        )}
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
