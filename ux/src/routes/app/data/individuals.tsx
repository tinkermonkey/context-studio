import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { Button, Modal, FilterBar, PageHeader, RowMenu, Sparkline } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { IndividualEditor } from "@/components/ontology/IndividualEditor";
import { IndividualDrawer } from "@/components/ontology/IndividualDrawer";
import {
  useIndividuals,
  useCreateIndividual,
  useUpdateIndividual,
  useDeleteIndividual,
  useIndividual,
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

  const individualColumns: Column<IndividualResponse>[] = [
    {
      key: "id",
      label: individualsCopy.table.idHeader,
      render: (value) => (
        <code className="font-mono text-xs">{(value as string).slice(0, 8)}</code>
      ),
    },
    {
      key: "title",
      label: individualsCopy.table.nameHeader,
      sortable: true,
      render: (value, row) => (
        <span
          className="text-cyan-400 font-medium cursor-pointer"
          data-testid={`individual-name-${row.id}`}
          onClick={() => onSelectedIdChange(row.id)}
        >
          {value as string}
        </span>
      ),
    },
    {
      key: "class_ids",
      label: individualsCopy.table.classesHeader,
      render: (value) => {
        const classIds = value as string[];
        return (
          <div className="flex gap-1 flex-wrap">
            {classIds.map((classId) => {
              const className = classMap.get(classId) || "Unknown";
              return (
                <span
                  key={classId}
                  className="bg-canvas-bg-2 text-xs font-medium px-2 py-1 rounded"
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
      key: "description",
      label: individualsCopy.table.descriptionHeader,
      render: (value) => {
        const desc = value as string | null | undefined;
        if (!desc) return <span className="opacity-60">—</span>;
        const truncated = desc.length > 50 ? desc.slice(0, 50) + "…" : desc;
        return <span>{truncated}</span>;
      },
    },
    {
      key: "last_modified",
      label: individualsCopy.table.updatedHeader,
      render: (value, row) => {
        const date = value as string | null;
        const barCount = Math.min(row.version, 10);
        const sparkData = Array.from({ length: barCount }, (_, i) =>
          Math.round(30 + ((i + 1) / barCount) * 70),
        );
        const getSparkColor = (lastModified: string | null): string => {
          if (!lastModified) return "neutral";
          const ageInHours = (Date.now() - new Date(lastModified).getTime()) / (1000 * 60 * 60);
          if (ageInHours < 24) return "emerald";
          if (ageInHours < 7 * 24) return "amber";
          return "neutral";
        };
        return (
          <div className="flex flex-col gap-1">
            <Sparkline data={sparkData} color={getSparkColor(date)} height={16} />
            <span className="text-xs opacity-60">
              {date ? new Date(date).toLocaleDateString() : "—"}
            </span>
          </div>
        );
      },
    },
    {
      key: "id",
      label: "",
      width: "40px",
      render: (_, row) => (
        <RowMenu
          data-testid={`individual-row-actions-${row.id}`}
          actions={[
            { id: "edit", label: "Edit", icon: "edit" },
            { type: "separator" },
            { id: "delete", label: "Delete", icon: "trash", danger: true },
          ]}
          onAction={(actionId) => {
            if (actionId === "edit") onEditClick(row.id);
            if (actionId === "delete") onDeleteClick(row.id);
          }}
        />
      ),
    },
  ];

  if (isLoading) {
    return (
      <div className="stack">
        <div className="skeleton" style={{ height: 32, width: 200 }} />
        <div className="skeleton" style={{ height: 40 }} />
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 40 }} />
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
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by title or description…"
        showingCount={filteredData.length}
        totalCount={individuals.length}
      />

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
          renderDrawerContent={(individual) => (
            <IndividualDrawer
              key={individual.id}
              individualId={individual.id}
              onClose={() => onSelectedIdChange(undefined)}
              onSelectIndividual={onSelectedIdChange}
            />
          )}
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

  const {
    data: classesResponse,
    isError: classesError,
    error: classesErrorObj,
    refetch: refetchClasses,
  } = useClasses();
  const classes = classesResponse?.items || [];
  const classMap = new Map(classes.map((c: ClassResponse) => [c.id, c.title]));

  const {
    data: editingIndividual,
    isLoading: isLoadingEditingIndividual,
    isError: editingIndividualError,
    error: editingIndividualErrorObj,
    refetch: refetchEditingIndividual,
  } = useIndividual(editingId || "");

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
      const { class_ids: _, ...updateFields } = data;
      await updateMutation.mutateAsync({
        id: editingId,
        data: updateFields,
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
      <PageHeader
        eyebrow="Data"
        title={individualsCopy.pageTitle}
        idChip="/data/individuals"
        actions={
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="individual-add-button"
          >
            {individualsCopy.create.buttonLabel}
          </Button>
        }
      />

      <div data-testid="schema-page-layout">
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

      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
        }}
        title={individualsCopy.create.modalTitle}
        data-testid="individual-create-modal"
      >
        {classesError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={classesErrorObj || new Error(individualsCopy.errors.failedToLoadClasses)}
              onRetry={() => refetchClasses()}
              message={individualsCopy.errors.failedToLoadClasses}
              daemonLogPath="/local-server/logs/context_studio.log"
            />
          </div>
        )}
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
        isOpen={showEditModal}
        onClose={() => {
          setShowEditModal(false);
          setEditingId(null);
          setEditError(null);
        }}
        title={individualsCopy.edit.modalTitle}
        data-testid="individual-edit-modal"
      >
        {editingIndividualError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={editingIndividualErrorObj || new Error(individualsCopy.errors.failedToLoad)}
              onRetry={() => refetchEditingIndividual()}
              message={individualsCopy.errors.failedToLoad}
              daemonLogPath="/local-server/logs/context_studio.log"
            />
          </div>
        )}
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
        {isLoadingEditingIndividual && (
          <div className="stack-lg">
            <div className="skeleton" style={{ height: 40 }} />
            <div className="skeleton" style={{ height: 40 }} />
            <div className="skeleton" style={{ height: 80 }} />
          </div>
        )}
        {editingId && !isLoadingEditingIndividual && !editingIndividualError && (
          <IndividualEditor
            individualId={editingId}
            initialData={editingIndividual}
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
