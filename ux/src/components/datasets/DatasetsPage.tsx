import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Button,
  Chip,
  FilterBar,
  Icon,
  PageHeader,
  Panel,
  Select,
  Table,
  type Column,
} from "@tinkermonkey/heimdall-ui";
import { ApiError } from "@/api/client/interceptors";
import { SMALL_SET_LIMIT } from "@/api/config";
import { useDatasets, useDeleteDataset } from "@/api/hooks/ontology/useDatasets";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useToasts } from "@/components/ui/Toast";
import { formatDate } from "@/components/entity/EntityPageParts";
import { datasetsPerTaxonomy, useDatasetScope } from "@/hooks/useDatasetScope";
import { CreateDatasetModal } from "./CreateDatasetModal";
import { DeleteDatasetDialog } from "./DeleteDatasetDialog";
import { datasetsCopy } from "./copy";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

const ALL_TAXONOMIES = "all";
const copy = datasetsCopy;

interface DatasetsPageProps {
  /** Show only this taxonomy's datasets (the `taxonomy` URL parameter). */
  taxonomyId?: string;
  onTaxonomyChange: (taxonomyId: string | undefined) => void;
}

/**
 * Data → Datasets: every taxonomy's datasets with their sizes, filterable by
 * taxonomy. Create one, open one's individuals, or delete one with its data.
 */
export function DatasetsPage({ taxonomyId, onTaxonomyChange }: DatasetsPageProps) {
  const navigate = useNavigate();
  const { toast } = useToasts();
  const { data: datasets, isLoading, error, refetch } = useDatasets(taxonomyId);
  const { data: taxonomiesResponse } = useTaxonomies({ limit: SMALL_SET_LIMIT });
  const deleteDataset = useDeleteDataset();
  const { selectedDatasetId, setDataset } = useDatasetScope();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleting, setDeleting] = useState<DatasetResponse | null>(null);
  const [search, setSearch] = useState("");

  const taxonomies = taxonomiesResponse?.items ?? [];
  const taxonomyTitle = new Map(taxonomies.map((t) => [t.id, t.title]));
  const allRows = datasets ?? [];
  const q = search.trim().toLowerCase();
  const rows = q
    ? allRows.filter(
        (d) => d.title.toLowerCase().includes(q) || d.identifier.toLowerCase().includes(q),
      )
    : allRows;

  const perTaxonomy = datasetsPerTaxonomy(allRows);
  // A taxonomy's only dataset is implied: no parameter, so nothing stays scoped.
  const openIndividuals = (dataset: DatasetResponse) =>
    navigate({
      to: "/app/data/individuals",
      search: {
        dataset: (perTaxonomy.get(dataset.taxonomy_id) ?? 0) >= 2 ? dataset.id : undefined,
      },
    });

  const handleDelete = (dataset: DatasetResponse) => {
    setDeleting(null);
    deleteDataset.mutate(dataset.id, {
      onSuccess: (result) => {
        if (selectedDatasetId === dataset.id) setDataset(undefined);
        toast(
          "success",
          copy.delete.successToast(result.individual_count, result.relationship_count),
        );
      },
      onError: (err) =>
        toast("error", err instanceof ApiError && err.detail ? err.detail : copy.delete.failed),
    });
  };

  const columns: Column<DatasetResponse>[] = [
    {
      key: "title",
      label: copy.table.title,
      render: (_, row) => (
        <span className="dataset-title-cell" data-testid={`dataset-row-${row.id}`}>
          <span className="dataset-title-cell__title">{row.title}</span>
          <span className="entity-muted-cell mono">{row.identifier}</span>
          {row.yields_to_schema && <Chip variant="neutral">{copy.page.yieldsToSchema}</Chip>}
        </span>
      ),
    },
    {
      key: "taxonomy_id",
      label: copy.table.taxonomy,
      width: "220px",
      render: (value) => (
        <Chip variant="neutral">{taxonomyTitle.get(value as string) ?? (value as string)}</Chip>
      ),
    },
    {
      key: "individual_count",
      label: copy.table.individuals,
      width: "110px",
      render: (value) => <span className="entity-count-cell">{value as number}</span>,
    },
    {
      key: "relationship_count",
      label: copy.table.relationships,
      width: "120px",
      render: (value) => <span className="entity-count-cell">{value as number}</span>,
    },
    {
      key: "last_modified",
      label: copy.table.lastModified,
      width: "130px",
      render: (value) => <span className="entity-muted-cell">{formatDate(value as string)}</span>,
    },
    {
      key: "id",
      label: "",
      width: "56px",
      render: (_, row) => (
        <Button
          variant="ghost"
          size="sm"
          icon
          aria-label={copy.table.deleteLabel(row.title)}
          title={copy.table.deleteLabel(row.title)}
          onClick={(e) => {
            e.stopPropagation();
            setDeleting(row);
          }}
          data-testid={`dataset-row-delete-${row.id}`}
        >
          <Icon name="trash" size={13} />
        </Button>
      ),
    },
  ];

  return (
    <div className="stack" data-testid="datasets-page">
      <PageHeader
        eyebrow={copy.page.eyebrow}
        title={copy.page.title}
        idChip="/data/datasets"
        subtitle={copy.page.subtitle}
        actions={
          <Button
            variant="primary"
            onClick={() => setCreateOpen(true)}
            disabled={taxonomies.length === 0}
            data-testid="dataset-add-button"
          >
            <Icon name="plus" size={13} /> {copy.page.addButton}
          </Button>
        }
      />

      {error ? (
        <ErrorBanner error={error} onRetry={() => refetch()} message={copy.page.loadError} />
      ) : (
        <>
          <FilterBar
            onSearchChange={setSearch}
            searchPlaceholder={copy.page.searchPlaceholder}
            showingCount={rows.length}
            totalCount={allRows.length}
            data-testid="datasets-filter-bar"
          >
            {taxonomies.length > 1 && (
              <Select
                value={taxonomyId ?? ALL_TAXONOMIES}
                onChange={(value) => onTaxonomyChange(value === ALL_TAXONOMIES ? undefined : value)}
                ariaLabel={copy.page.taxonomyFilterLabel}
                data-testid="dataset-taxonomy-filter"
              >
                <Select.Item value={ALL_TAXONOMIES}>{copy.page.allTaxonomies}</Select.Item>
                {taxonomies.map((t) => (
                  <Select.Item key={t.id} value={t.id}>
                    {t.title} · {t.identifier}
                  </Select.Item>
                ))}
              </Select>
            )}
          </FilterBar>
          <Panel noPadding>
            <div data-testid="datasets-table" aria-busy={isLoading}>
              {isLoading ? (
                <div className="skeleton entity-page__skeleton" />
              ) : (
                <Table
                  columns={columns}
                  data={rows}
                  rowKey="id"
                  onRowClick={openIndividuals}
                  emptyState={
                    <EmptyState
                      title={copy.empty.title}
                      description={copy.empty.description}
                      action={
                        taxonomies.length > 0
                          ? { label: copy.empty.action, onClick: () => setCreateOpen(true) }
                          : undefined
                      }
                      variant="compact"
                    />
                  }
                />
              )}
            </div>
          </Panel>
        </>
      )}

      <CreateDatasetModal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        taxonomies={taxonomies}
        initialTaxonomyId={taxonomyId}
        onCreated={(dataset) => {
          setCreateOpen(false);
          toast("success", copy.create.successToast(dataset.title));
        }}
      />
      <DeleteDatasetDialog
        dataset={deleting}
        taxonomyTitle={deleting ? taxonomyTitle.get(deleting.taxonomy_id) : undefined}
        onClose={() => setDeleting(null)}
        onConfirm={handleDelete}
      />
    </div>
  );
}
