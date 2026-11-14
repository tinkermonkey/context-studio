import { useEffect, useRef, useState } from "react";
import {
  Button,
  Field,
  FormCallout,
  Icon,
  PageHeader,
  Panel,
  Select,
  TabBar,
  TextArea,
} from "@tinkermonkey/heimdall-ui";
import { useTaxonomies } from "@/api/hooks/ontology/useTaxonomies";
import {
  useIndividualExtractionCandidates,
  useSchemaExtractionCandidates,
} from "@/api/hooks/pipeline/useExtractionCandidates";
import {
  reviewKindOf,
  useExtractionReviewRuns,
  type ReviewKind,
} from "@/api/hooks/pipeline/useExtractionReviewRuns";
import { usePipelineRun } from "@/api/hooks/pipeline/usePipelineRuns";
import { useExtractionExamples } from "@/api/hooks/pipeline/useExtractionExamples";
import { selectionRequestFields, usePipelineSelection } from "@/hooks/usePipelineSelection";
import { useRunDataset } from "@/hooks/useRunDataset";
import { ImplementationConfigPicker } from "../ImplementationConfigPicker";
import { DATASET_REQUIRED, RunDatasetField } from "../RunDatasetField";
import { ExampleRuns } from "./ExampleRuns";
import { SchemaCandidateReview } from "./SchemaCandidateReview";
import { IndividualCandidateReview } from "./IndividualCandidateReview";
import "./ExtractionReview.css";

const REVIEW_TABS: Array<{ id: ReviewKind; label: string }> = [
  { id: "schema", label: "Schema extraction" },
  { id: "individual", label: "Individual extraction" },
];
const tabId = (kind: ReviewKind) => `extraction-review-tab-${kind}`;
const tabPanelId = (kind: ReviewKind) => `extraction-review-tabpanel-${kind}`;

/** Taxonomy a run was started with; review and apply compare against it, so it is fixed per run. */
export interface ReviewScope {
  taxonomyId: string;
  taxonomyLabel: string;
}

interface FormErrors {
  text?: string;
  taxonomy?: string;
  dataset?: string;
}

const TEXT_REQUIRED = "Paste a paragraph to extract from";

export interface ExtractionReviewPageProps {
  onOpenRunHistory?: () => void;
  /** Open an earlier run for review (from the example's run list). */
  onOpenRun?: (runId: string) => void;
  /** An existing schema/individual extraction run to open for review. */
  initialRunId?: string;
}

export function ExtractionReviewPage({
  onOpenRunHistory,
  onOpenRun,
  initialRunId,
}: ExtractionReviewPageProps) {
  const [text, setText] = useState("");
  const [taxonomyChoice, setTaxonomyChoice] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  // After the first run attempt, an emptied paragraph re-shows its error on blur.
  const [attempted, setAttempted] = useState(false);
  const [tab, setTab] = useState<ReviewKind>("schema");
  const tabBarRef = useRef<HTMLDivElement>(null);
  // Heimdall's TabBar renders no ids on its tab buttons, so wire the
  // tab ↔ tabpanel association (id / aria-controls) onto them here.
  useEffect(() => {
    tabBarRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]').forEach((btn, i) => {
      const kind = REVIEW_TABS[i]?.id;
      if (!kind) return;
      btn.id = tabId(kind);
      btn.setAttribute("aria-controls", tabPanelId(kind));
    });
  });
  const [scope, setScope] = useState<ReviewScope | null>(null);

  const { data: taxonomyList } = useTaxonomies();
  const taxonomies = taxonomyList?.items ?? [];
  const taxonomyId =
    taxonomyChoice ||
    taxonomies.find((t) => t.identifier === "dr_spec")?.id ||
    taxonomies[0]?.id ||
    "";
  const taxonomy = taxonomies.find((t) => t.id === taxonomyId);
  // The individual run extracts into one dataset; a taxonomy with several needs it named.
  const dataset = useRunDataset(taxonomyId || undefined);

  // Each run is selected on its own: the two types share no implementation list.
  const schemaSelection = usePipelineSelection("schema_extraction");
  const individualSelection = usePipelineSelection("individual_extraction");

  const runs = useExtractionReviewRuns();

  // The example library: picking one fills the paragraph. A run records the
  // example only while the paragraph is still the example's text.
  const { data: examples } = useExtractionExamples();
  const [exampleChoice, setExampleChoice] = useState("");
  const example = examples?.find((e) => e.id === exampleChoice);
  const exampleEdited = !!example && text !== example.text;
  const pickExample = (id: string) => {
    const picked = examples?.find((e) => e.id === id);
    if (!picked) return;
    setExampleChoice(id);
    setText(picked.text);
    setErrors((prev) => ({ ...prev, text: undefined }));
    const hinted = taxonomies.find((t) => t.identifier === picked.taxonomy_hint);
    if (hinted) setTaxonomyChoice(hinted.id);
  };

  // Open a run passed by id (from run history) once it loads.
  const { data: initialRun } = usePipelineRun(initialRunId ?? "");
  const [openedRunId, setOpenedRunId] = useState<string | null>(null);
  const { open: openRun } = runs;
  useEffect(() => {
    if (!initialRun || openedRunId === initialRun.id) return;
    const kind = reviewKindOf(initialRun.pipeline_type);
    if (!kind) return;
    const input = (initialRun.input_summary ?? {}) as Record<string, unknown>;
    const asText = (v: unknown) => (typeof v === "string" ? v : "");
    setOpenedRunId(initialRun.id);
    setTab(kind);
    // Show the paragraph the run read; its highlights index into it.
    setText(initialRun.source_text ?? "");
    setExampleChoice(asText(input.example_id));
    // Point the scope pickers at the run's scope so its labels resolve.
    setTaxonomyChoice(asText(input.taxonomy_id));
    setScope({
      taxonomyId: asText(input.taxonomy_id),
      taxonomyLabel: asText(input.taxonomy_name) || asText(input.taxonomy_id) || "—",
    });
    openRun(initialRun);
  }, [initialRun, openedRunId, openRun]);
  const showingOpenedRun =
    !!openedRunId &&
    !runs.lastRequest &&
    (runs.schema.run?.id === openedRunId || runs.individual.run?.id === openedRunId);
  // Highlights index into the text that was run: the live request, or the opened run's stored text.
  const openedRunText = showingOpenedRun ? (initialRun?.source_text ?? "") : "";
  const runText = runs.lastRequest?.text ?? openedRunText;
  const anyRunning = runs.schema.status === "running" || runs.individual.status === "running";

  const schemaCount = useSchemaExtractionCandidates(
    runs.schema.run?.id ?? "",
    runs.schema.status === "completed",
  ).data?.length;
  const individualCount = useIndividualExtractionCandidates(
    runs.individual.run?.id ?? "",
    runs.individual.status === "completed",
  ).data?.length;

  const run = () => {
    const next: FormErrors = {};
    if (!text.trim()) next.text = TEXT_REQUIRED;
    if (!taxonomy) next.taxonomy = "Select a taxonomy";
    if (dataset.missing) next.dataset = DATASET_REQUIRED;
    setErrors(next);
    setAttempted(true);
    if (Object.keys(next).length > 0 || !taxonomy) return;

    setScope({
      taxonomyId: taxonomy.id,
      taxonomyLabel: `${taxonomy.title} · ${taxonomy.identifier}`,
    });
    void runs.start({
      text,
      taxonomy: { id: taxonomy.id, label: taxonomy.title },
      exampleId: example && !exampleEdited ? example.id : undefined,
      datasetId: dataset.dataset?.id,
      schema: selectionRequestFields(schemaSelection),
      individual: selectionRequestFields(individualSelection),
    });
  };

  const reviewScope: ReviewScope = { ...(scope ?? { taxonomyId: "", taxonomyLabel: "—" }) };
  // An opened run only carries its taxonomy id; use the picker label once it loads.
  if (showingOpenedRun && taxonomy?.id === reviewScope.taxonomyId) {
    reviewScope.taxonomyLabel = `${taxonomy.title} · ${taxonomy.identifier}`;
  }

  return (
    <div data-testid="extraction-review-page">
      <PageHeader
        eyebrow="PIPELINES · extraction · review"
        title="Extraction review"
        idChip="/pipelines/review"
        subtitle="Paste a paragraph and run schema and individual extraction against a taxonomy. Review each result set, then apply what you accept. Nothing is written until you apply."
        actions={
          onOpenRunHistory ? (
            <Button
              variant="ghost"
              onClick={onOpenRunHistory}
              data-testid="extraction-review-run-history"
            >
              <Icon name="clock" size={13} /> Run history
            </Button>
          ) : undefined
        }
      />
      <div className="xr-gap" />

      <Panel
        title="Source paragraph"
        subtitle="Both runs read the same paragraph. Each result set is reviewed and applied separately."
        data-testid="extraction-review-input"
        footer={
          <div className="xr-between">
            <span className="xr-mono-muted">starts schema_extraction + individual_extraction</span>
            <Button
              variant="primary"
              onClick={run}
              disabled={anyRunning}
              aria-busy={anyRunning}
              data-testid="extraction-review-run"
            >
              <Icon name="zap" size={13} /> {anyRunning ? "Running…" : "Run extraction"}
            </Button>
          </div>
        }
      >
        <div className="xr-input-grid">
          <Field
            label="Paragraph"
            htmlFor="extraction-review-text"
            required
            error={errors.text}
            errorId="extraction-review-text-error"
          >
            <TextArea
              id="extraction-review-text"
              rows={5}
              value={text}
              placeholder="Paste a paragraph to extract schema and individuals from…"
              error={!!errors.text}
              aria-invalid={!!errors.text}
              aria-describedby={errors.text ? "extraction-review-text-error" : undefined}
              onChange={(e) => {
                setText(e.target.value);
                setErrors((prev) => ({ ...prev, text: undefined }));
              }}
              onBlur={() => {
                if (attempted && !text.trim()) {
                  setErrors((prev) => ({ ...prev, text: TEXT_REQUIRED }));
                }
              }}
              data-testid="extraction-review-text"
            />
          </Field>
          <div className="xr-stack-sm">
            <Field label="Example" hint="optional">
              <Select
                value={example ? example.id : ""}
                onChange={pickExample}
                placeholder="Pick an example paragraph"
                ariaLabel="Example paragraph"
                data-testid="extraction-review-example"
              >
                {(examples ?? []).map((e) => (
                  <Select.Item key={e.id} value={e.id}>
                    {e.title}
                  </Select.Item>
                ))}
              </Select>
            </Field>
            {example && (
              <span className="xr-example-desc" data-testid="extraction-review-example-description">
                {example.description}
                {exampleEdited && " Edited: runs of this text are not linked to the example."}
              </span>
            )}
            <Field label="Taxonomy" required error={errors.taxonomy}>
              <Select
                value={taxonomyId}
                onChange={(v) => {
                  setTaxonomyChoice(v);
                  setErrors((prev) => ({ ...prev, taxonomy: undefined }));
                }}
                placeholder="Select a taxonomy"
                ariaLabel="Taxonomy"
                error={!!errors.taxonomy}
                data-testid="extraction-review-taxonomy"
              >
                {taxonomies.map((t) => (
                  <Select.Item key={t.id} value={t.id}>
                    {`${t.title} · ${t.identifier}`}
                  </Select.Item>
                ))}
              </Select>
            </Field>
            <RunDatasetField
              run={dataset}
              id="extraction-review-dataset"
              error={errors.dataset}
              disabled={anyRunning}
              onChange={() => setErrors((prev) => ({ ...prev, dataset: undefined }))}
            />
          </div>
        </div>
        <div className="xr-pickers" data-testid="extraction-review-pickers">
          <ImplementationConfigPicker
            selection={schemaSelection}
            idPrefix="extraction-review-schema"
            legend="Schema extraction"
            disabled={anyRunning}
            placement="top-start"
          />
          <ImplementationConfigPicker
            selection={individualSelection}
            idPrefix="extraction-review-individual"
            legend="Individual extraction"
            disabled={anyRunning}
            placement="top-start"
          />
        </div>
        {runText && text !== runText && (
          <>
            <div className="xr-gap-sm" />
            <FormCallout variant="warn" icon="alert" data-testid="extraction-review-stale">
              The paragraph changed since the last run. Highlights show the text that was run.
              Re-run to review the new text.
            </FormCallout>
          </>
        )}
      </Panel>

      {example && !exampleEdited && (
        <>
          <div className="xr-gap-sm" />
          <ExampleRuns exampleId={example.id} exampleTitle={example.title} onOpenRun={onOpenRun} />
        </>
      )}

      {showingOpenedRun && (
        <>
          <div className="xr-gap-sm" />
          <FormCallout variant="info" icon="info" data-testid="extraction-review-opened-run">
            Reviewing run <code>{openedRunId}</code> from run history.
            {openedRunText
              ? " Highlights show the paragraph the run read."
              : " This run has no stored source paragraph, so provenance highlights are unavailable."}
          </FormCallout>
        </>
      )}

      <div className="xr-gap" />
      <TabBar
        ref={tabBarRef}
        tabs={REVIEW_TABS.map((t) => ({
          ...t,
          count: t.id === "schema" ? schemaCount : individualCount,
        }))}
        activeTabId={tab}
        onSelectTab={(id) => setTab(id as ReviewKind)}
        data-testid="extraction-review-tabs"
      />
      <div className="xr-gap-sm" />
      {/* Both tabs stay mounted so review decisions survive switching tabs. */}
      <div
        role="tabpanel"
        id={tabPanelId("schema")}
        aria-labelledby={tabId("schema")}
        hidden={tab !== "schema"}
      >
        <SchemaCandidateReview
          slot={runs.schema}
          text={runText}
          scope={reviewScope}
          onRetry={() => void runs.rerun("schema", selectionRequestFields(schemaSelection))}
        />
      </div>
      <div
        role="tabpanel"
        id={tabPanelId("individual")}
        aria-labelledby={tabId("individual")}
        hidden={tab !== "individual"}
      >
        <IndividualCandidateReview
          slot={runs.individual}
          text={runText}
          scope={reviewScope}
          onRetry={() => void runs.rerun("individual", selectionRequestFields(individualSelection))}
        />
      </div>
    </div>
  );
}
