import { useState } from "react";
import {
  Button,
  Field,
  FormCallout,
  PageHeader,
  Panel,
  SegmentedControl,
  Select,
  TextInput,
} from "@tinkermonkey/heimdall-ui";
import { ApiError } from "@/api/client/interceptors";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import { useTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useSource } from "@/api/hooks/sources/useSource";
import {
  useExtractionConfigurations,
  useExtractSource,
} from "@/api/hooks/sources/useExtractSource";
import {
  isRunActive,
  useCancelExtractionRun,
  useExtractionRun,
} from "@/api/hooks/sources/useExtractionRun";
import type { ExtractionRunRef, Source } from "@/api/services/sources";
import { formatAge } from "@/components/proposals/proposalModel";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useToasts } from "@/components/ui/Toast";
import { ChunkList } from "./ChunkList";
import { ExtractRunPanel } from "./ExtractRunPanel";
import { sourcesCopy } from "./copy";
import {
  charsInPages,
  chunkRange,
  configurationPrice,
  estimateCost,
  formatRange,
  formatUsd,
  pagesSpec,
  parsePages,
  sourceDetail,
} from "./sourceModel";
import "./sources.css";
import type { components } from "@/api/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];

const copy = sourcesCopy.extract;
const SERVER_DEFAULT = "";

export interface ExtractSourcePageProps {
  sourceId: string;
  /** The individual extraction run to follow (the `run` URL parameter). */
  runId?: string;
  /** The schema extraction run started with it, if any. */
  schemaRunId?: string;
  onRunsStarted: (runs: ExtractionRunRef[]) => void;
  /** Leave the run and configure a new extraction. */
  onReset: () => void;
  onBack: () => void;
  onReview: (proposalId: string) => void;
}

interface ConfigureFormProps {
  source: Source;
  datasets: DatasetResponse[];
  onRunsStarted: (runs: ExtractionRunRef[]) => void;
  onBack: () => void;
  onPagesChange: (pages: number[]) => void;
}

/** Dataset, configuration, page range and schema option, with a rough estimate. */
function ConfigureForm({
  source,
  datasets,
  onRunsStarted,
  onBack,
  onPagesChange,
}: ConfigureFormProps) {
  const extract = useExtractSource();
  const { configurations } = useExtractionConfigurations();
  const [dataset, setDataset] = useState(source.dataset_id);
  const [configChoice, setConfigChoice] = useState<string | undefined>(undefined);
  const [schema, setSchema] = useState(false);
  const [pages, setPages] = useState("");
  const [pagesError, setPagesError] = useState<string>();
  const [startError, setStartError] = useState<string>();

  const configRef = configChoice ?? configurations[0]?.config_ref ?? SERVER_DEFAULT;
  const config = configurations.find((c) => c.config_ref === configRef);
  const parsed = parsePages(pages, source.pages);
  const chars = "pages" in parsed ? charsInPages(source, parsed.pages) : source.chars;
  const chunks = chunkRange(chars);
  const price = configurationPrice(config);
  const runs = schema ? 2 : 1;
  const cost = price
    ? formatRange(
        formatUsd(estimateCost(chars, chunks.min, runs, price)),
        formatUsd(estimateCost(chars, chunks.max, runs, price)),
      )
    : undefined;
  const datasetLabel = datasets.find((d) => d.id === dataset)?.identifier ?? dataset;

  const start = () => {
    if ("error" in parsed) {
      setPagesError(parsed.error);
      return;
    }
    setStartError(undefined);
    // The server takes digits, "-" and commas only; every page is no spec at all.
    const spec = pagesSpec(parsed.pages, source.pages);
    extract.mutate(
      {
        sourceId: source.id,
        body: {
          dataset,
          ...(configRef ? { configuration_ref: configRef } : {}),
          ...(spec ? { pages: spec } : {}),
          schema,
        },
      },
      {
        onSuccess: (response) => onRunsStarted(response.runs),
        onError: (err) =>
          setStartError(err instanceof ApiError && err.detail ? err.detail : copy.startFailed),
      },
    );
  };

  return (
    <Panel
      title={copy.configureTitle}
      subtitle={copy.configureSubtitle}
      data-testid="extract-configure-panel"
    >
      <div className="extract-form">
        <Field label={copy.datasetLabel} hint={copy.datasetHint}>
          <SegmentedControl
            value={dataset}
            onChange={(v) => setDataset(String(v))}
            options={datasets.map((d) => ({ value: d.id, label: d.identifier }))}
            aria-label={copy.datasetLabel}
            data-testid="extract-dataset"
          />
        </Field>

        <Field label={copy.configLabel} htmlFor="extract-config" hint={copy.configHint}>
          <Select
            id="extract-config"
            value={configRef}
            onChange={setConfigChoice}
            placeholder={copy.configPlaceholder}
            ariaLabel={copy.configLabel}
            data-testid="extract-config"
          >
            {configurations.map((c) => (
              <Select.Item key={c.id} value={c.config_ref} description={c.model ?? undefined}>
                {c.config_ref}
              </Select.Item>
            ))}
          </Select>
        </Field>

        <label className="extract-check" htmlFor="extract-schema">
          <input
            id="extract-schema"
            type="checkbox"
            checked={schema}
            onChange={(e) => setSchema(e.target.checked)}
            aria-describedby="extract-schema-hint"
            data-testid="extract-schema-toggle"
          />
          <span className="extract-check__text">
            <span className="extract-check__label">{copy.schemaLabel}</span>
            <span id="extract-schema-hint" className="sources-note">
              {copy.schemaHint}
            </span>
          </span>
        </label>

        {source.pages > 1 && (
          <Field
            label={copy.pagesLabel}
            htmlFor="extract-pages"
            hint={copy.pagesHint}
            error={pagesError}
            errorId="extract-pages-error"
            className="extract-form__pages"
          >
            <TextInput
              id="extract-pages"
              mono
              placeholder={copy.pagesPlaceholder}
              value={pages}
              onChange={(e) => {
                const next = e.target.value;
                setPages(next);
                setPagesError(undefined);
                // Like the estimate, a range that doesn't parse counts every page.
                const result = parsePages(next, source.pages);
                onPagesChange("pages" in result ? result.pages : []);
              }}
              error={!!pagesError}
              aria-invalid={!!pagesError}
              aria-describedby={pagesError ? "extract-pages-error" : undefined}
              data-testid="extract-pages"
            />
          </Field>
        )}

        <FormCallout variant="info" icon="zap" data-testid="extract-estimate">
          {copy.estimate(formatRange(chunks.min, chunks.max), schema, datasetLabel, cost)}
        </FormCallout>

        {startError && (
          <FormCallout variant="error" icon="alert" data-testid="extract-start-error">
            {startError}
          </FormCallout>
        )}

        <div className="extract-actions">
          <Button variant="ghost" size="sm" onClick={onBack} data-testid="extract-cancel">
            {copy.cancel}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={start}
            disabled={extract.isPending}
            data-testid="extract-start"
          >
            {copy.start}
          </Button>
        </div>
      </div>
    </Panel>
  );
}

/**
 * Extract a source into a proposal: configure the run, follow it chunk by
 * chunk, and hand off to the review queue.
 */
export function ExtractSourcePage({
  sourceId,
  runId,
  schemaRunId,
  onRunsStarted,
  onReset,
  onBack,
  onReview,
}: ExtractSourcePageProps) {
  const { toast } = useToasts();
  const { data: source, error, refetch } = useSource(sourceId);
  const { data: taxonomy } = useTaxonomy(source?.taxonomy_id ?? "");
  const { data: datasets } = useDatasets(source?.taxonomy_id);
  const { data: run, error: runError } = useExtractionRun(runId);
  const { data: schemaRun } = useExtractionRun(schemaRunId);
  const cancelRun = useCancelExtractionRun();
  const [selectedPages, setSelectedPages] = useState<number[]>([]);

  if (error) {
    return (
      <div className="stack" data-testid="extract-source-page">
        <ErrorBanner error={error} onRetry={() => refetch()} message={copy.loadError} />
      </div>
    );
  }
  if (!source) {
    return (
      <div className="stack" data-testid="extract-source-page" aria-busy="true">
        <div className="skeleton entity-page__skeleton" />
      </div>
    );
  }

  const taxonomyDatasets = datasets ?? [];
  const datasetName = (id: string) => taxonomyDatasets.find((d) => d.id === id)?.identifier ?? id;
  const estimate = chunkRange(charsInPages(source, selectedPages));
  // The dataset this run extracts into, from the source's last extraction when it is this one.
  const lastExtraction = source.last_extraction;
  const runDatasetId = lastExtraction?.runs.some((r) => r.run_id === runId)
    ? (lastExtraction.dataset_id ?? undefined)
    : undefined;

  const cancel = () => {
    for (const r of [run, schemaRun]) {
      if (!r || !isRunActive(r.status)) continue;
      cancelRun.mutate(r.id, {
        onError: (err) =>
          toast(
            "error",
            copy.cancelFailed,
            err instanceof ApiError && err.detail ? err.detail : undefined,
          ),
      });
    }
  };

  return (
    <div className="stack sources-page" data-testid="extract-source-page">
      <PageHeader
        eyebrow={copy.eyebrow(source.kind, taxonomy?.identifier ?? "…")}
        title={source.title}
        idChip={source.id.slice(0, 8)}
        subtitle={copy.subtitle(
          sourceDetail(source),
          formatAge(source.created_at),
          datasetName(source.dataset_id),
        )}
      />
      <div className="extract-layout">
        <div className="extract-layout__main">
          {runId ? (
            <ExtractRunPanel
              run={run}
              runError={runError}
              schemaRun={schemaRun}
              sourceTitle={source.title}
              datasetId={runDatasetId}
              datasetName={datasetName}
              onCancel={cancel}
              cancelling={cancelRun.isPending}
              onReview={onReview}
              onBack={onBack}
              onRetry={onReset}
            />
          ) : source.status !== "ready" ? (
            <FormCallout variant="warn" icon="alert" data-testid="extract-not-ready">
              {copy.notReady}
            </FormCallout>
          ) : (
            <ConfigureForm
              source={source}
              datasets={taxonomyDatasets}
              onRunsStarted={onRunsStarted}
              onBack={onBack}
              onPagesChange={setSelectedPages}
            />
          )}
        </div>
        <ChunkList
          run={runId ? run : undefined}
          estimatedChunks={formatRange(estimate.min, estimate.max)}
          pages={source.pages}
        />
      </div>
    </div>
  );
}
