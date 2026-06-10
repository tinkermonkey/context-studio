import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import {
  Button,
  Modal,
  FilterBar,
  PageHeader,
  RowMenu,
  Chip,
  VersionPill,
  Icon,
} from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { IndividualEditor } from "@/components/ontology/IndividualEditor";
import { IndividualDrawer } from "@/components/ontology/IndividualDrawer";
import { CreateDrawer } from "@/components/crud/CreateDrawer";
import {
  useIndividuals,
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
          onClick={() => onSelectedIdChange(row.id)}
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
    <div className="stack">
      {classesError && (
        <ErrorBanner
          error={classesErrorObj || new Error(individualsCopy.errors.failedToLoadClasses)}
          onRetry={onRetryClasses}
          message={individualsCopy.errors.failedToLoadClasses}
        />
      )}
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by title or description…"
        showingCount={filteredData.length}
        totalCount={individuals.length}
      />

      {showFilteredEmpty ? (
        <EmptyState
          title={individualsCopy.filteredEmpty.title}
          description={individualsCopy.filteredEmpty.description}
        />
      ) : (
        <SchemaPageLayout
          data={filteredData}
          selectedId={selectedId}
          renderInspectorContent={(individual) => (
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
  const [showCreateDrawer, setShowCreateDrawer] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/data/individuals" });
  const selectedId = searchParams.selected;
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

  const handleCreateSuccess = (entity: { id: string; title?: string }) => {
    handleSelectedIdChange(entity.id);
    toast("success", individualsCopy.create.successToast);
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
        eyebrow="DATA · node_type · individual"
        title={individualsCopy.pageTitle}
        idChip="/data/individuals"
        subtitle={individualsCopy.subtitle}
        actions={
          <Button
            variant="primary"
            onClick={() => setShowCreateDrawer(true)}
            data-testid="individual-add-button"
          >
            <Icon name="plus" size={13} /> {individualsCopy.create.buttonLabel}
          </Button>
        }
      />

      <div data-testid="individuals-content">
        <IndividualsPageContent
          onCreateClick={() => setShowCreateDrawer(true)}
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

      <CreateDrawer
        entityType="individual"
        isOpen={showCreateDrawer}
        onClose={() => setShowCreateDrawer(false)}
        onSuccess={handleCreateSuccess}
        data-testid="individual-create-drawer"
      />

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
