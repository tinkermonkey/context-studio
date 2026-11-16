import { useState } from "react";
import {
  Button,
  Field,
  FormCallout,
  PageHeader,
  Panel,
  SegmentedControl,
  TextInput,
} from "@tinkermonkey/heimdall-ui";
import { ApiError } from "@/api/client/interceptors";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import { useTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useSource } from "@/api/hooks/sources/useSource";
import { canExtractSource, useExtractSource } from "@/api/hooks/sources/useExtractSource";
import {
  isRunActive,
  useCancelExtractionRun,
  useExtractionRun,
} from "@/api/hooks/sources/useExtractionRun";
import type { ExtractionRunRef, Source } from "@/api/services/sources";
import { formatAge } from "@/components/proposals/proposalModel";
import { ImplementationConfigPicker } from "@/components/pipeline/ImplementationConfigPicker";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useToasts } from "@/components/ui/Toast";
import {
  selectionRequestFields,
  usePipelineSelection,
  type PipelineSelection,
} from "@/hooks/usePipelineSelection";
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

/** The extract request's fields for the schema run's selection; a part not selected is left out. */
function schemaRunFields(selection: PipelineSelection) {
  const { implementation_id, configuration_ref } = selectionRequestFields(selection);
  return {
    ...(implementation_id ? { schema_implementation_id: implementation_id } : {}),
    ...(configuration_ref ? { schema_configuration_ref: configuration_ref } : {}),
  };
}

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
  /**
   * The taxonomy mirrors a client's spec: only that client proposes schema
   * changes to it (over MCP), so schema suggestions aren't offered here.
   * Undefined until the taxonomy loads (or when it fails to): the option
   * stays off until it is known.
   */
  mirrored: boolean | undefined;
  onRunsStarted: (runs: ExtractionRunRef[]) => void;
  onBack: () => void;
  onPagesChange: (pages: number[]) => void;
}

/** Dataset, implementation, configuration, page range and schema option, with a rough estimate. */
function ConfigureForm({
  source,
  datasets,
  mirrored,
  onRunsStarted,
  onBack,
  onPagesChange,
}: ConfigureFormProps) {
  const extract = useExtractSource();
  // The server refuses an implementation that cannot extract a source, so none is offered.
  const selection = usePipelineSelection("individual_extraction", { offers: canExtractSource });
  // The schema run, when one is asked for, is selected on its own.
  const schemaSelection = usePipelineSelection("schema_extraction", { offers: canExtractSource });
  const [dataset, setDataset] = useState(source.dataset_id);
  const [schema, setSchema] = useState(false);
  const [skipBoilerplate, setSkipBoilerplate] = useState(true);
  const [pages, setPages] = useState("");
  const [pagesError, setPagesError] = useState<string>();
  const [startError, setStartError] = useState<string>();
  // A mirrored taxonomy's schema is its client's to change; offer it only once known not to be.
  const schemaOffered = mirrored === false;
  const suggestSchema = schema && schemaOffered;

  const parsed = parsePages(pages, source.pages);
  const chars = "pages" in parsed ? charsInPages(source, parsed.pages) : source.chars;
  const chunks = chunkRange(chars);
  // Each run costs what its own configuration's model does; without a price for
  // every run there is no total to show.
  const prices = [
    configurationPrice(selection.configuration),
    ...(suggestSchema ? [configurationPrice(schemaSelection.configuration)] : []),
  ];
  const total = (chunkCount: number) =>
    prices.reduce((sum, price) => sum + (price ? estimateCost(chars, chunkCount, 1, price) : 0), 0);
  const cost = prices.every(Boolean)
    ? formatRange(formatUsd(total(chunks.min)), formatUsd(total(chunks.max)))
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
          ...selectionRequestFields(selection),
          ...(suggestSchema ? schemaRunFields(schemaSelection) : {}),
          ...(spec ? { pages: spec } : {}),
          schema: suggestSchema,
          skip_boilerplate: skipBoilerplate,
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
            onChange={(v) => {
              setDataset(String(v));
              setStartError(undefined);
            }}
            options={datasets.map((d) => ({ value: d.id, label: d.identifier }))}
            aria-label={copy.datasetLabel}
            data-testid="extract-dataset"
          />
        </Field>

        <ImplementationConfigPicker
          selection={selection}
          idPrefix="extract"
          legend={copy.individualRunLegend}
          disabled={extract.isPending}
          onChange={() => setStartError(undefined)}
        />

        <label
          className={schemaOffered ? "extract-check" : "extract-check extract-check--disabled"}
          htmlFor="extract-schema"
        >
          <input
            id="extract-schema"
            type="checkbox"
            checked={suggestSchema}
            disabled={!schemaOffered}
            onChange={(e) => {
              setSchema(e.target.checked);
              setStartError(undefined);
            }}
            aria-labelledby="extract-schema-label"
            aria-describedby="extract-schema-hint"
            data-testid="extract-schema-toggle"
          />
          <span className="extract-check__text">
            <span id="extract-schema-label" className="extract-check__label">
              {copy.schemaLabel}
            </span>
            <span
              id="extract-schema-hint"
              className="sources-note"
              data-testid="extract-schema-hint"
            >
              {mirrored ? copy.schemaMirroredHint : copy.schemaHint}
            </span>
          </span>
        </label>

        {suggestSchema && (
          <ImplementationConfigPicker
            selection={schemaSelection}
            idPrefix="extract-schema"
            legend={copy.schemaRunLegend}
            disabled={extract.isPending}
            onChange={() => setStartError(undefined)}
          />
        )}

        <label className="extract-check" htmlFor="extract-skip-boilerplate">
          <input
            id="extract-skip-boilerplate"
            type="checkbox"
            checked={skipBoilerplate}
            onChange={(e) => {
              setSkipBoilerplate(e.target.checked);
              setStartError(undefined);
            }}
            aria-labelledby="extract-skip-boilerplate-label"
            aria-describedby="extract-skip-boilerplate-hint"
            data-testid="extract-skip-boilerplate-toggle"
          />
          <span className="extract-check__text">
            <span id="extract-skip-boilerplate-label" className="extract-check__label">
              {copy.skipBoilerplateLabel}
            </span>
            <span id="extract-skip-boilerplate-hint" className="sources-note">
              {copy.skipBoilerplateHint}
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
                setStartError(undefined);
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
          {copy.estimate(formatRange(chunks.min, chunks.max), suggestSchema, datasetLabel, cost)}
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
              mirrored={taxonomy?.mirrored}
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
