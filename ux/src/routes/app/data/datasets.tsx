import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { Button, Modal, FilterBar, PageHeader, RowMenu } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SchemaTable, type Column } from "@/components/schema/SchemaTable";
import { useDatasets, useCreateDataset, useDeleteDataset, useActivateDataset } from "@/api/hooks/admin/useDatasets";
import { datasetsCopy } from "./datasets/-copy";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

interface DatasetsSearchParams {
  selected?: string;
}

interface DatasetsPageContentProps {
  onCreateClick: () => void;
  selectedId?: string;
  onSelectedIdChange: (id?: string) => void;
  onDeleteClick: (id: string) => void;
}


function DatasetsPageContent({
  onCreateClick,
  selectedId,
  onSelectedIdChange,
  onDeleteClick,
}: DatasetsPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");

  const { data: listResponse, isLoading, error, refetch } = useDatasets();
  const activateDataset = useActivateDataset();
  const datasets = listResponse || [];

  const filteredData = datasets.filter(
    (dataset: DatasetResponse) =>
      dataset.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      dataset.description?.toLowerCase().includes(searchFilter.toLowerCase()) ||
      dataset.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const datasetColumns: Column<DatasetResponse>[] = [
    {
      key: "id",
      label: "ID",
      render: (value) => (
        <code className="font-mono text-xs">{(value as string).slice(0, 8)}</code>
      ),
    },
    {
      key: "title",
      label: "Name",
      sortable: true,
      render: (value, row) => (
        <span
          className="text-cyan-400 font-medium cursor-pointer"
          data-testid={`dataset-name-${row.id}`}
          onClick={() => onSelectedIdChange(row.id)}
        >
          {value as string}
        </span>
      ),
    },
    {
      key: "filename",
      label: "Filename",
      render: (value) => <span>{value as string}</span>,
    },
    {
      key: "description",
      label: "Description",
      render: (value) => {
        const desc = value as string | null | undefined;
        if (!desc) return <span className="opacity-60">—</span>;
        const truncated = desc.length > 50 ? desc.slice(0, 50) + "…" : desc;
        return <span>{truncated}</span>;
      },
    },
    {
      key: "is_active",
      label: "Status",
      render: (value) => {
        const isActive = value as boolean;
        return isActive ? (
          <span className="text-emerald-400">Active</span>
        ) : (
          <span className="opacity-60">Inactive</span>
        );
      },
    },
    {
      key: "id",
      label: "",
      width: "40px",
      render: (_, row) => (
        <RowMenu
          data-testid={`dataset-row-actions-${row.id}`}
          actions={[
            { id: "activate", label: row.is_active ? "Active (current)" : "Activate" },
            { type: "separator" },
            { id: "delete", label: "Delete", icon: "trash", danger: true },
          ]}
          onAction={(actionId) => {
            if (actionId === "activate" && !row.is_active) {
              activateDataset.mutate(row.id);
            }
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
          message={datasetsCopy.errors.failedToLoad}
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  }

  if (datasets.length === 0) {
    return (
      <EmptyState
        title={datasetsCopy.emptyState.title}
        description={datasetsCopy.emptyState.description}
        action={{ label: "New Dataset", onClick: onCreateClick }}
      />
    );
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = datasets.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div>
      <FilterBar
        data-testid="schema-filter-bar"
        onSearchChange={setSearchFilter}
        searchPlaceholder="Search by title or description…"
        showingCount={filteredData.length}
        totalCount={datasets.length}
      />

      {showFilteredEmpty ? (
        <div style={{ marginTop: "var(--space-6)" }}>
          <EmptyState title="No datasets found" description="Try adjusting your search filter" />
        </div>
      ) : (
        <SchemaTable
          columns={datasetColumns}
          data={filteredData}
          onRowSelect={onSelectedIdChange}
          selectedId={selectedId}
          testIdPrefix="dataset"
        />
      )}
    </div>
  );
}

function DatasetsPageWrapper() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [createFilename, setCreateFilename] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const navigate = useNavigate();
  const searchParams = useSearch({ from: "/app/data/datasets" });
  const selectedId = searchParams.selected;
  const createMutation = useCreateDataset();
  const deleteMutation = useDeleteDataset();
  const { toast } = useToasts();

  const handleSelectedIdChange = (id?: string) => {
    navigate({
      to: "/app/data/datasets",
      search: id ? { selected: id } : {},
      replace: true,
    });
  };

  const handleCreateSubmit = async () => {
    setCreateError(null);
    if (!createTitle.trim()) {
      setCreateError("Title is required");
      return;
    }
    if (!createFilename.trim()) {
      setCreateError("Filename is required");
      return;
    }

    try {
      const result = await createMutation.mutateAsync({
        title: createTitle,
        filename: createFilename,
        description: createDescription || undefined,
      });
      setShowCreateModal(false);
      setCreateTitle("");
      setCreateFilename("");
      setCreateDescription("");
      handleSelectedIdChange(result.id);
      toast("success", datasetsCopy.create.successToast);
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : datasetsCopy.errors.failedToCreate);
    }
  };

  const handleDeleteClick = (id: string) => {
    if (confirm(datasetsCopy.delete.confirmMessage)) {
      deleteMutation
        .mutateAsync(id)
        .then(() => {
          if (selectedId === id) {
            handleSelectedIdChange(undefined);
          }
          toast("success", datasetsCopy.delete.successToast);
        })
        .catch((error) => {
          toast(
            "error",
            error instanceof Error ? error.message : datasetsCopy.errors.failedToDelete,
          );
        });
    }
  };

  return (
    <div className="stack" data-testid="datasets-page">
      <PageHeader
        eyebrow="Data"
        title={datasetsCopy.pageTitle}
        idChip="/data/datasets"
        actions={
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="dataset-add-button"
          >
            New Dataset
          </Button>
        }
      />
      <DatasetsPageContent
        onCreateClick={() => setShowCreateModal(true)}
        selectedId={selectedId}
        onSelectedIdChange={handleSelectedIdChange}
        onDeleteClick={handleDeleteClick}
      />

      <Modal isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
          setCreateTitle("");
          setCreateFilename("");
          setCreateDescription("");
        }}
        title={datasetsCopy.create.modalTitle}
        data-testid="dataset-create-modal"
      >
        {createError && (
          <div style={{ marginBottom: "var(--space-3)" }}>
            <ErrorBanner
              error={new Error(createError)}
              onRetry={() => setCreateError(null)}
              message="Error"
              daemonLogPath="/local-server/logs/context_studio.log"
            />
          </div>
        )}
        <div className="stack">
          <div>
            <label htmlFor="title" style={{ display: "block", marginBottom: "var(--space-1)" }}>
              {datasetsCopy.form.nameLabel}
            </label>
            <input
              id="title"
              type="text"
              placeholder={datasetsCopy.form.namePlaceholder}
              value={createTitle}
              onChange={(e) => {
                setCreateTitle(e.target.value);
                if (createError) setCreateError(null);
              }}
              data-testid="dataset-title-input"
              className="input"
            />
          </div>
          <div>
            <label htmlFor="filename" style={{ display: "block", marginBottom: "var(--space-1)" }}>
              {datasetsCopy.form.sourceLabel}
            </label>
            <input
              id="filename"
              type="text"
              placeholder={datasetsCopy.form.sourcePlaceholder}
              value={createFilename}
              onChange={(e) => {
                setCreateFilename(e.target.value);
                if (createError) setCreateError(null);
              }}
              data-testid="dataset-filename-input"
              className="input"
            />
          </div>
          <div>
            <label
              htmlFor="description"
              style={{ display: "block", marginBottom: "var(--space-1)" }}
            >
              {datasetsCopy.form.descriptionLabel}
            </label>
            <textarea
              id="description"
              placeholder={datasetsCopy.form.descriptionPlaceholder}
              value={createDescription}
              onChange={(e) => {
                setCreateDescription(e.target.value);
                if (createError) setCreateError(null);
              }}
              data-testid="dataset-description-input"
              className="input"
              rows={3}
            />
          </div>
          <div className="row" style={{ gap: "var(--space-2)", justifyContent: "flex-end" }}>
            <Button
              variant="ghost"
              onClick={() => {
                setShowCreateModal(false);
                setCreateError(null);
                setCreateTitle("");
                setCreateFilename("");
                setCreateDescription("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleCreateSubmit}
              disabled={createMutation.isPending}
              data-testid="dataset-submit-button"
            >
              {createMutation.isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

export function DatasetsPage() {
  return <DatasetsPageWrapper />;
}

export const Route = createFileRoute("/app/data/datasets")({
  component: DatasetsPage,
  validateSearch: (search: Record<string, unknown>): DatasetsSearchParams => ({
    selected: typeof search.selected === "string" ? search.selected : undefined,
  }),
});
