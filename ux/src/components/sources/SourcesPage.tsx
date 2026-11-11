import { useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import {
  Button,
  Chip,
  ConfirmDialog,
  Icon,
  PageHeader,
  Panel,
  SegmentedControl,
  Select,
  Table,
  type Column,
} from "@tinkermonkey/heimdall-ui";
import { ApiError } from "@/api/client/interceptors";
import { SMALL_SET_LIMIT } from "@/api/config";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import { useSources } from "@/api/hooks/sources/useSources";
import { useRemoveSource } from "@/api/hooks/sources/useRemoveSource";
import type { Source } from "@/api/services/sources";
import { formatAge } from "@/components/proposals/proposalModel";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useToasts } from "@/components/ui/Toast";
import { useDatasetScope } from "@/hooks/useDatasetScope";
import type { DatasetSearch } from "@/lib/datasetSearch";
import { AddSourcePanel } from "./AddSourcePanel";
import { LastExtractionCell } from "./LastExtractionCell";
import { sourcesCopy } from "./copy";
import { STATUS_TONE, sourceDetail, statusNote, type ExtractionRunIds } from "./sourceModel";
import "./sources.css";

const copy = sourcesCopy;
const ALL_DATASETS = "all";

interface SourcesPageProps {
  /** The taxonomy whose sources show (the `taxonomy` URL parameter); a default one without. */
  taxonomyId?: string;
  onTaxonomyChange: (taxonomyId: string) => void;
}

/**
 * Data → Sources: a taxonomy's files, web pages and pasted text, filtered by
 * dataset. Add one, extract one into a proposal, or remove one.
 */
export function SourcesPage({ taxonomyId: taxonomyParam, onTaxonomyChange }: SourcesPageProps) {
  const navigate = useNavigate();
  const { toast } = useToasts();
  const { dataset: datasetParam } = useSearch({ strict: false }) as DatasetSearch;
  const { data: taxonomiesResponse, isLoading: taxonomiesLoading } = useTaxonomies({
    limit: SMALL_SET_LIMIT,
  });
  const { data: allDatasets } = useDatasets();
  const taxonomies = taxonomiesResponse?.items ?? [];

  // The URL's taxonomy, else the chosen dataset's, else the first one.
  const taxonomyId =
    taxonomyParam ??
    allDatasets?.find((d) => d.id === datasetParam)?.taxonomy_id ??
    taxonomies[0]?.id;
  const taxonomy = taxonomies.find((t) => t.id === taxonomyId);

  const { datasets, selectedDataset, selectedDatasetId, showSelector, setDataset } =
    useDatasetScope(taxonomyId);
  // A taxonomy's only dataset is implied: new sources go there.
  const addDatasetId = selectedDatasetId ?? (datasets.length === 1 ? datasets[0].id : undefined);

  const {
    data: sourcesResponse,
    isLoading,
    error,
    refetch,
  } = useSources({ taxonomy_id: taxonomyId, dataset: selectedDatasetId });
  const sources = sourcesResponse?.items ?? [];
  const removeSource = useRemoveSource();
  const [removing, setRemoving] = useState<Source | null>(null);

  // A run to follow opens with both run ids, so the schema run shows too.
  const openExtract = (source: Source, runs: ExtractionRunIds = {}) =>
    navigate({
      to: "/app/data/sources/$sourceId/extract",
      params: { sourceId: source.id },
      search: (prev) => ({ ...prev, run: runs.run, schemaRun: runs.schemaRun }),
    });
  const openProposal = (proposalId: string) =>
    navigate({ to: "/app/proposals/$proposalId", params: { proposalId } });

  const handleRemove = (source: Source) => {
    setRemoving(null);
    removeSource.mutate(source.id, {
      onSuccess: () => toast("success", copy.remove.removed(source.title)),
      onError: (err) =>
        toast(
          "error",
          copy.remove.failed,
          err instanceof ApiError && err.detail ? err.detail : undefined,
        ),
    });
  };

  const columns: Column<Source>[] = [
    {
      key: "title",
      label: copy.table.source,
      render: (_, row) => (
        <span className="sources-cell-stack" data-testid={`source-row-${row.id}`}>
          <span className="sources-title">{row.title}</span>
          <span className="sources-mono-muted">{sourceDetail(row)}</span>
        </span>
      ),
    },
    {
      key: "kind",
      label: copy.table.kind,
      width: "90px",
      render: (value) => <Chip form="id-tag">{value as string}</Chip>,
    },
    {
      key: "status",
      label: copy.table.status,
      width: "170px",
      render: (_, row) => (
        <span
          className="sources-cell-stack"
          title={row.failure_detail ?? undefined}
          data-testid={`source-status-${row.id}`}
        >
          <Chip variant={STATUS_TONE[row.status]}>{row.status}</Chip>
          {statusNote(row) && <span className="sources-note">{statusNote(row)}</span>}
        </span>
      ),
    },
    {
      key: "dataset_id",
      label: copy.table.lastExtraction,
      width: "280px",
      render: (_, row) => (
        <LastExtractionCell
          sourceId={row.id}
          extraction={row.last_extraction}
          onOpenProposal={openProposal}
          onFollowRun={(runs) => openExtract(row, runs)}
        />
      ),
    },
    {
      key: "created_at",
      label: copy.table.added,
      width: "80px",
      render: (value) => <span className="sources-mono-muted">{formatAge(value as string)}</span>,
    },
    {
      key: "id",
      label: copy.table.actions,
      width: "170px",
      render: (_, row) => (
        <span className="sources-actions">
          {row.status === "ready" && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => openExtract(row)}
              aria-label={copy.table.extractLabel(row.title)}
              data-testid={`source-extract-${row.id}`}
            >
              {row.last_extraction ? copy.table.extractAgain : copy.table.extract}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            icon
            aria-label={copy.table.removeLabel(row.title)}
            title={copy.table.removeLabel(row.title)}
            onClick={() => setRemoving(row)}
            data-testid={`source-remove-${row.id}`}
          >
            <Icon name="trash" size={13} />
          </Button>
        </span>
      ),
    },
  ];

  if (!taxonomiesLoading && taxonomies.length === 0) {
    return (
      <div className="stack" data-testid="sources-page">
        <PageHeader eyebrow="DATA · sources" title={copy.page.title} idChip="/app/data/sources" />
        <EmptyState title={copy.empty.title} description={copy.page.noTaxonomy} />
      </div>
    );
  }

  return (
    <div className="stack sources-page" data-testid="sources-page">
      <PageHeader
        eyebrow={copy.page.eyebrow(taxonomy?.identifier ?? "…", selectedDataset?.identifier)}
        title={copy.page.title}
        idChip="/app/data/sources"
        subtitle={copy.page.subtitle}
      />

      <div className="sources-filters">
        <div className="sources-filters__controls">
          {taxonomies.length > 1 && (
            <Select
              value={taxonomyId ?? ""}
              onChange={onTaxonomyChange}
              ariaLabel={copy.page.taxonomyLabel}
              data-testid="sources-taxonomy-select"
            >
              {taxonomies.map((t) => (
                <Select.Item key={t.id} value={t.id}>
                  {t.title} · {t.identifier}
                </Select.Item>
              ))}
            </Select>
          )}
          {showSelector && (
            <SegmentedControl
              value={selectedDatasetId ?? ALL_DATASETS}
              onChange={(v) => setDataset(v === ALL_DATASETS ? undefined : String(v))}
              options={[
                ...datasets.map((d) => ({ value: d.id, label: d.identifier })),
                { value: ALL_DATASETS, label: copy.page.allDatasets },
              ]}
              aria-label={copy.page.datasetLabel}
              data-testid="sources-dataset-filter"
            />
          )}
        </div>
        <span className="sources-mono-muted" data-testid="sources-count">
          {copy.page.count(sourcesResponse?.total ?? sources.length)}
        </span>
      </div>

      {taxonomyId && (
        <AddSourcePanel
          key={taxonomyId}
          taxonomyId={taxonomyId}
          datasetId={addDatasetId}
          datasets={datasets}
        />
      )}

      {error ? (
        <ErrorBanner error={error} onRetry={() => refetch()} message={copy.page.loadError} />
      ) : (
        <Panel noPadding>
          <div data-testid="sources-table" aria-busy={isLoading}>
            {isLoading ? (
              <div className="skeleton entity-page__skeleton" />
            ) : (
              <Table
                columns={columns}
                data={sources}
                rowKey="id"
                emptyState={
                  <EmptyState
                    title={copy.empty.title}
                    description={copy.empty.description}
                    variant="compact"
                  />
                }
              />
            )}
          </div>
        </Panel>
      )}

      <p className="sources-footnote">{copy.page.footnote}</p>

      <ConfirmDialog
        isOpen={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && handleRemove(removing)}
        title={copy.remove.title}
        message={removing ? copy.remove.message(removing.title) : ""}
        confirmLabel={copy.remove.confirm}
      />
    </div>
  );
}
