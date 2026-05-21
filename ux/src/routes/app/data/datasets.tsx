import { useState } from "react";
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { ColumnDef } from "@tanstack/react-table";
import { Trash2 } from "lucide-react";
import { useToasts } from "@/components/ui/Toast";
import { Button } from "@tinkermonkey/heimdall-ui";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar } from "@/components/schema/FilterBar";
import { SchemaTable } from "@/components/schema/SchemaTable";
import { useDatasets, useCreateDataset, useDeleteDataset } from "@/api/hooks/admin/useDatasets";
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

function DatasetsEmptyState({ onCreateClick }: { onCreateClick: () => void }) {
  return (
    <div className="empty-state" data-testid="empty-state">
      <div className="empty-state-content">
        <div className="empty-state-title">{datasetsCopy.emptyState.title}</div>
        <div className="empty-state-description">{datasetsCopy.emptyState.description}</div>
      </div>
      <div
        style={{
          display: "flex",
          gap: "var(--space-2)",
          justifyContent: "center",
          flexWrap: "wrap",
        }}
      >
        <Button
          variant="primary"
          size="sm"
          onClick={onCreateClick}
          data-testid="empty-state-new-dataset"
        >
          Create Dataset
        </Button>
      </div>
    </div>
  );
}

function DatasetsPageContent({
  onCreateClick,
  selectedId,
  onSelectedIdChange,
  onDeleteClick,
}: DatasetsPageContentProps) {
  const [searchFilter, setSearchFilter] = useState("");

  const { data: listResponse, isLoading, error, refetch } = useDatasets();
  const datasets = listResponse || [];

  const filteredData = datasets.filter(
    (dataset: DatasetResponse) =>
      dataset.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      dataset.description?.toLowerCase().includes(searchFilter.toLowerCase()) ||
      dataset.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const datasetColumns: ColumnDef<DatasetResponse>[] = [
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
        const datasetId = info.row.original.id;
        return (
          <span
            style={{
              color: "var(--cyan-600, #0891b2)",
              fontWeight: 500,
              cursor: "pointer",
            }}
            data-testid={`dataset-name-${datasetId}`}
            onClick={() => onSelectedIdChange(datasetId)}
          >
            {info.getValue() as string}
          </span>
        );
      },
    },
    {
      accessorKey: "filename",
      header: "Filename",
      cell: (info) => {
        const filename = info.getValue() as string;
        return <span>{filename}</span>;
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
      accessorKey: "is_active",
      header: "Status",
      cell: (info) => {
        const isActive = info.getValue() as boolean;
        return isActive ? (
          <span style={{ color: "var(--emerald-600)" }}>Active</span>
        ) : (
          <span className="muted-text">Inactive</span>
        );
      },
    },
  ];

  const renderRowActions = (row: DatasetResponse) => (
    <div style={{ display: "flex", gap: "var(--space-1)" }}>
      <button
        type="button"
        onClick={() => onDeleteClick(row.id)}
        className="btn btn-icon"
        data-testid={`dataset-row-delete-${row.id}`}
        disabled={row.is_active}
        title={row.is_active ? "Cannot delete active dataset" : "Delete dataset"}
      >
        <Trash2 size={16} style={{ color: "var(--canvas-fg-3)" }} />
      </button>
    </div>
  );

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
          message={datasetsCopy.errors.failedToLoad}
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  }

  if (datasets.length === 0) {
    return <DatasetsEmptyState onCreateClick={onCreateClick} />;
  }

  const hasFilters = !!searchFilter;
  const showFilteredEmpty = datasets.length > 0 && filteredData.length === 0 && hasFilters;

  return (
    <div>
      <FilterBar searchValue={searchFilter} onSearchChange={setSearchFilter} />

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
          renderRowActions={renderRowActions}
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
      <div className="flex-between">
        <h1 style={{ margin: 0, fontSize: "var(--text-xl)" }}>{datasetsCopy.pageTitle}</h1>
        <div className="row">
          <Button
            variant="primary"
            onClick={() => setShowCreateModal(true)}
            data-testid="dataset-add-button"
          >
            New Dataset
          </Button>
        </div>
      </div>
      <DatasetsPageContent
        onCreateClick={() => setShowCreateModal(true)}
        selectedId={selectedId}
        onSelectedIdChange={handleSelectedIdChange}
        onDeleteClick={handleDeleteClick}
      />

      <Modal
        open={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          setCreateError(null);
          setCreateTitle("");
          setCreateFilename("");
          setCreateDescription("");
        }}
        title={datasetsCopy.create.modalTitle}
        size="md"
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
