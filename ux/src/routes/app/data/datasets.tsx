import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import {
  Button,
  Modal,
  FilterBar,
  PageHeader,
  InspectorPanel,
  KVGrid,
  TextInput as Input,
} from "@tinkermonkey/heimdall-ui";
import type { Column } from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { EmptyState } from "@/components/ui/EmptyState";
import { SelectableTable } from "@/components/crud/SelectableTable";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import {
  useDatasets,
  useCreateDataset,
  useDeleteDataset,
  useActivateDataset,
} from "@/api/hooks/admin/useDatasets";
import { datasetsCopy } from "./datasets/-copy";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

function toIsoDate(input: string | null | undefined): string {
  if (!input) return "—";
  const d = new Date(input);
  if (Number.isNaN(d.getTime())) return "—";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function StatusDot({ active }: { active: boolean }) {
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: active ? "rgb(var(--status-emerald))" : "transparent",
          border: `1.5px solid ${active ? "rgb(var(--status-emerald))" : "rgb(var(--canvas-border))"}`,
          display: "inline-block",
          flexShrink: 0,
        }}
        aria-hidden="true"
      />
      <span>{active ? "Active" : "Inactive"}</span>
    </span>
  );
}

function ActiveDatasetBanner({ dataset }: { dataset: DatasetResponse }) {
  return (
    <div
      data-testid="active-dataset-banner"
      style={{
        background: "rgb(var(--canvas-bg-2))",
        border: "1px solid rgb(var(--status-emerald))",
        borderRadius: "var(--radius-md, 6px)",
        padding: "12px 16px",
        marginBottom: 16,
        display: "flex",
        alignItems: "center",
        gap: 24,
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "rgb(var(--status-emerald))",
            display: "inline-block",
          }}
          aria-hidden="true"
        />
        <span style={{ fontSize: 11, fontWeight: 600, color: "rgb(var(--status-emerald))", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Active Dataset
        </span>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{ fontWeight: 600, color: "rgb(var(--canvas-fg-1))", marginRight: 8 }}>
          {dataset.title}
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>
          {dataset.filename}
        </span>
      </div>
      <div
        style={{
          display: "flex",
          gap: 16,
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          color: "rgb(var(--canvas-fg-3))",
        }}
      >
        <span>{dataset.metrics.layers_count} layers</span>
        <span>{dataset.metrics.domains_count} domains</span>
        <span>{dataset.metrics.terms_count} terms</span>
        <span>{dataset.metrics.relationships_count} relationships</span>
        <span>{dataset.metrics.individuals_count} individuals</span>
      </div>
    </div>
  );
}

interface DatasetInspectorProps {
  dataset: DatasetResponse;
  onActivate: () => void;
  isActivating: boolean;
}

function DatasetInspector({ dataset, onActivate, isActivating }: DatasetInspectorProps) {
  const inspectorActions = dataset.is_active ? null : (
    <Button
      variant="primary"
      size="sm"
      onClick={onActivate}
      disabled={isActivating}
      data-testid="dataset-inspector-activate-button"
    >
      {isActivating ? "Activating…" : "Activate"}
    </Button>
  );

  return (
    <InspectorPanel
      eyebrow="dataset"
      title={dataset.title}
      id={dataset.id}
      actions={inspectorActions}
      data-testid="dataset-inspector"
    >
      <InspectorPanel.Section title="Identity">
        <div className="stack">
          <div>
            <label className="form-group-label">Title</label>
            <Input type="text" value={dataset.title} disabled data-testid="dataset-inspector-title" />
          </div>
          <div>
            <label className="form-group-label">Description</label>
            <Input
              type="text"
              value={dataset.description ?? ""}
              disabled
              data-testid="dataset-inspector-description"
            />
          </div>
          <div>
            <label className="form-group-label">Filename</label>
            <Input
              type="text"
              value={dataset.filename}
              disabled
              mono
              data-testid="dataset-inspector-filename"
            />
          </div>
          <div>
            <label className="form-group-label">Schema version</label>
            <Input
              type="text"
              value={dataset.schema_version}
              disabled
              mono
              data-testid="dataset-inspector-schema-version"
            />
          </div>
        </div>
      </InspectorPanel.Section>

      <InspectorPanel.Section title="Metrics">
        <KVGrid
          rows={[
            { key: "Layers", value: String(dataset.metrics.layers_count) },
            { key: "Domains", value: String(dataset.metrics.domains_count) },
            { key: "Terms", value: String(dataset.metrics.terms_count) },
            { key: "Relationships", value: String(dataset.metrics.relationships_count) },
            { key: "Individuals", value: String(dataset.metrics.individuals_count) },
          ]}
        />
      </InspectorPanel.Section>
    </InspectorPanel>
  );
}

export function DatasetsPage() {
  const [searchFilter, setSearchFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [createFilename, setCreateFilename] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const { data: datasets, isLoading, error, refetch } = useDatasets();
  const activateMutation = useActivateDataset();
  const deleteMutation = useDeleteDataset();
  const createMutation = useCreateDataset();
  const { toast } = useToasts();

  const allDatasets: DatasetResponse[] = datasets || [];
  const activeDataset = allDatasets.find((d) => d.is_active);

  const filteredData = allDatasets.filter(
    (dataset) =>
      dataset.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
      (dataset.description?.toLowerCase().includes(searchFilter.toLowerCase()) ?? false) ||
      dataset.id.toLowerCase().includes(searchFilter.toLowerCase()),
  );

  const datasetColumns: Column<DatasetResponse>[] = [
    {
      key: "is_active",
      label: "Status",
      width: "110px",
      render: (value) => <StatusDot active={value as boolean} />,
    },
    {
      key: "title",
      label: "Title",
      sortable: true,
      render: (value, row) => (
        <span
          className="cursor-pointer font-medium"
          style={{ color: "rgb(var(--accent-cyan, var(--status-cyan)))" }}
          data-testid={`dataset-name-${row.id}`}
          onClick={() => setSelectedId(row.id)}
        >
          {value as string}
        </span>
      ),
    },
    {
      key: "filename",
      label: "Filename",
      render: (value) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{value as string}</span>
      ),
    },
    {
      key: "schema_version",
      label: "Schema",
      width: "100px",
      render: (value) => (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{value as string}</span>
      ),
    },
    {
      key: "created_at",
      label: "Imported",
      width: "120px",
      render: (value) => (
        <span style={{ fontSize: 12, color: "rgb(var(--canvas-fg-3))" }}>
          {toIsoDate(value as string | null)}
        </span>
      ),
    },
  ];

  const rowMenuActions = [
    { id: "activate", label: "Activate" },
    { type: "separator" as const },
    { id: "delete", label: "Delete", icon: "trash" as const, danger: true },
  ];

  function handleRowMenuAction(actionId: string, dataset: DatasetResponse) {
    if (actionId === "activate" && !dataset.is_active) {
      activateMutation.mutate(dataset.id, {
        onError: (err) => toast("error", err instanceof Error ? err.message : "Failed to activate"),
      });
    }
    if (actionId === "delete") {
      if (confirm(datasetsCopy.delete.confirmMessage)) {
        deleteMutation.mutateAsync(dataset.id).then(() => {
          if (selectedId === dataset.id) setSelectedId(undefined);
          toast("success", datasetsCopy.delete.successToast);
        }).catch((err) => {
          toast("error", err instanceof Error ? err.message : datasetsCopy.errors.failedToDelete);
        });
      }
    }
  }

  async function handleCreateSubmit() {
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
      setSelectedId(result.id);
      toast("success", datasetsCopy.create.successToast);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : datasetsCopy.errors.failedToCreate);
    }
  }

  function closeCreateModal() {
    setShowCreateModal(false);
    setCreateError(null);
    setCreateTitle("");
    setCreateFilename("");
    setCreateDescription("");
  }

  if (isLoading) {
    return (
      <div className="stack" data-testid="datasets-page">
        <PageHeader
          eyebrow="Data"
          title={datasetsCopy.pageTitle}
          idChip="/data/datasets"
          actions={
            <Button variant="primary" data-testid="dataset-add-button" onClick={() => setShowCreateModal(true)}>
              New Dataset
            </Button>
          }
        />
        <div className="stack">
          <div className="skeleton" style={{ height: 32, width: 200 }} />
          <div className="skeleton" style={{ height: 40 }} />
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 40 }} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="stack" data-testid="datasets-page">
        <PageHeader
          eyebrow="Data"
          title={datasetsCopy.pageTitle}
          idChip="/data/datasets"
          actions={
            <Button variant="primary" data-testid="dataset-add-button" onClick={() => setShowCreateModal(true)}>
              New Dataset
            </Button>
          }
        />
        <ErrorBanner
          error={error}
          onRetry={() => refetch()}
          message={datasetsCopy.errors.failedToLoad}
          daemonLogPath="/local-server/logs/context_studio.log"
        />
      </div>
    );
  }

  const hasFilter = !!searchFilter;
  const showFilteredEmpty = allDatasets.length > 0 && filteredData.length === 0 && hasFilter;

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

      {activeDataset && <ActiveDatasetBanner dataset={activeDataset} />}

      {allDatasets.length === 0 ? (
        <EmptyState
          title={datasetsCopy.emptyState.title}
          description={datasetsCopy.emptyState.description}
          action={{ label: "New Dataset", onClick: () => setShowCreateModal(true) }}
        />
      ) : (
        <>
          <FilterBar
            data-testid="schema-filter-bar"
            onSearchChange={setSearchFilter}
            searchPlaceholder="Search by title or description…"
            showingCount={filteredData.length}
            totalCount={allDatasets.length}
          />

          {showFilteredEmpty ? (
            <div style={{ marginTop: "var(--space-6)" }}>
              <EmptyState title="No datasets found" description="Try adjusting your search filter" />
            </div>
          ) : (
            <SchemaPageLayout
              data={filteredData}
              selectedId={selectedId}
              renderInspectorContent={(dataset) => (
                <DatasetInspector
                  key={dataset.id}
                  dataset={dataset}
                  onActivate={() =>
                    activateMutation.mutate(dataset.id, {
                      onError: (err) =>
                        toast("error", err instanceof Error ? err.message : "Failed to activate"),
                    })
                  }
                  isActivating={activateMutation.isPending}
                />
              )}
            >
              <SelectableTable
                columns={datasetColumns}
                data={filteredData}
                onRowClick={(row) => setSelectedId(row.id === selectedId ? undefined : row.id)}
                rowMenuActions={rowMenuActions}
                onRowMenuAction={handleRowMenuAction}
                rowMenuTestIdPrefix="dataset-row-actions"
                testId="datasets-table"
              />
            </SchemaPageLayout>
          )}
        </>
      )}

      <Modal
        isOpen={showCreateModal}
        onClose={closeCreateModal}
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
            <label htmlFor="description" style={{ display: "block", marginBottom: "var(--space-1)" }}>
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
            <Button variant="ghost" onClick={closeCreateModal}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={() => void handleCreateSubmit()}
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

export const Route = createFileRoute("/app/data/datasets")({
  component: DatasetsPage,
});
