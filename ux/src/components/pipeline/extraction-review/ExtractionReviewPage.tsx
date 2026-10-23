import { useState } from "react";
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
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";
import {
  useIndividualExtractionCandidates,
  useSchemaExtractionCandidates,
} from "@/api/hooks/pipeline/useExtractionCandidates";
import {
  useExtractionReviewRuns,
  type ReviewKind,
} from "@/api/hooks/pipeline/useExtractionReviewRuns";
import { SchemaCandidateReview } from "./SchemaCandidateReview";
import { IndividualCandidateReview } from "./IndividualCandidateReview";
import "./ExtractionReview.css";

/** Scope a run was started with; apply reads it, so it is fixed per run. */
export interface ReviewScope {
  taxonomyId: string;
  taxonomyLabel: string;
  conceptSchemeId: string;
  conceptSchemeLabel: string;
}

interface FormErrors {
  text?: string;
  taxonomy?: string;
  scheme?: string;
  config?: string;
}

const TEXT_REQUIRED = "Paste a paragraph to extract from";

type ConfigLike = {
  config_ref: string;
  version: number;
  enabled?: boolean;
  provider?: string | null;
  model?: string | null;
};
const firstEnabled = (configs?: ConfigLike[]) =>
  configs?.find((c) => c.enabled !== false) ?? configs?.[0];
/** Prefer the individual config that uses the same provider + model as the schema config. */
const pairedConfig = (configs: ConfigLike[] | undefined, partner?: ConfigLike) =>
  configs?.find(
    (c) =>
      c.enabled !== false &&
      partner?.model &&
      c.provider === partner.provider &&
      c.model === partner.model,
  ) ?? firstEnabled(configs);

export interface ExtractionReviewPageProps {
  onOpenRunHistory?: () => void;
}

export function ExtractionReviewPage({ onOpenRunHistory }: ExtractionReviewPageProps) {
  const [text, setText] = useState("");
  const [taxonomyChoice, setTaxonomyChoice] = useState("");
  const [schemeChoice, setSchemeChoice] = useState("");
  const [implChoice, setImplChoice] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  // After the first run attempt, an emptied paragraph re-shows its error on blur.
  const [attempted, setAttempted] = useState(false);
  const [tab, setTab] = useState<ReviewKind>("schema");
  const [scope, setScope] = useState<ReviewScope | null>(null);

  const { data: taxonomyList } = useTaxonomies();
  const taxonomies = taxonomyList?.items ?? [];
  const taxonomyId =
    taxonomyChoice ||
    taxonomies.find((t) => t.identifier === "dr_spec")?.id ||
    taxonomies[0]?.id ||
    "";
  const taxonomy = taxonomies.find((t) => t.id === taxonomyId);

  const { data: schemeList } = useSchemes(taxonomyId || undefined);
  const schemes = taxonomyId ? (schemeList?.items ?? []) : [];
  const schemeId =
    (schemes.some((s) => s.id === schemeChoice) ? schemeChoice : "") || schemes[0]?.id || "";
  const scheme = schemes.find((s) => s.id === schemeId);

  const { data: schemaImpls } = usePipelineImplementations("schema_extraction");
  const { data: individualImpls } = usePipelineImplementations("individual_extraction");
  const sharedImpls = (schemaImpls ?? []).filter((i) =>
    (individualImpls ?? []).some((j) => j.id === i.id),
  );
  const implId =
    implChoice || sharedImpls.find((i) => i.id === "default")?.id || sharedImpls[0]?.id || "";
  const { data: schemaConfigs } = usePipelineConfigurations("schema_extraction", implId);
  const { data: individualConfigs } = usePipelineConfigurations("individual_extraction", implId);
  const schemaConfig = firstEnabled(schemaConfigs);
  const individualConfig = pairedConfig(individualConfigs, schemaConfig);

  const runs = useExtractionReviewRuns();
  const runText = runs.lastRequest?.text ?? "";
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
    if (!scheme) next.scheme = "Select a concept scheme";
    if (!schemaConfig || !individualConfig) next.config = "Select a configuration";
    setErrors(next);
    setAttempted(true);
    if (Object.keys(next).length > 0 || !taxonomy || !scheme) return;

    const taxonomyLabel = `${taxonomy.title} · ${taxonomy.identifier}`;
    const schemeLabel = `${scheme.title} · ${scheme.identifier}`;
    setScope({
      taxonomyId: taxonomy.id,
      taxonomyLabel,
      conceptSchemeId: scheme.id,
      conceptSchemeLabel: schemeLabel,
    });
    void runs.start({
      text,
      taxonomy: { id: taxonomy.id, label: taxonomy.title },
      conceptScheme: { id: scheme.id, label: scheme.title },
      implementationId: implId,
      schemaConfigRef: schemaConfig!.config_ref,
      individualConfigRef: individualConfig!.config_ref,
      schemaModel: schemaConfig!.model,
      individualModel: individualConfig!.model,
    });
  };

  const reviewScope: ReviewScope = scope ?? {
    taxonomyId: "",
    taxonomyLabel: "—",
    conceptSchemeId: "",
    conceptSchemeLabel: "—",
  };

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
            <Field label="Taxonomy" required error={errors.taxonomy}>
              <Select
                value={taxonomyId}
                onChange={(v) => {
                  setTaxonomyChoice(v);
                  setSchemeChoice("");
                  setErrors((prev) => ({ ...prev, taxonomy: undefined, scheme: undefined }));
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
            <Field label="Concept scheme" required hint="schema target" error={errors.scheme}>
              <Select
                value={schemeId}
                onChange={(v) => {
                  setSchemeChoice(v);
                  setErrors((prev) => ({ ...prev, scheme: undefined }));
                }}
                placeholder="Select a concept scheme"
                ariaLabel="Concept scheme"
                error={!!errors.scheme}
                data-testid="extraction-review-scheme"
              >
                {schemes.map((s) => (
                  <Select.Item key={s.id} value={s.id}>
                    {`${s.title} · ${s.identifier}`}
                  </Select.Item>
                ))}
              </Select>
            </Field>
            <Field label="Configuration" error={errors.config}>
              <Select
                value={implId}
                onChange={(v) => {
                  setImplChoice(v);
                  setErrors((prev) => ({ ...prev, config: undefined }));
                }}
                placeholder="Select a configuration"
                ariaLabel="Configuration"
                error={!!errors.config}
                data-testid="extraction-review-config"
              >
                {sharedImpls.map((i) => (
                  <Select.Item key={i.id} value={i.id}>
                    {i.id}
                  </Select.Item>
                ))}
              </Select>
            </Field>
            {schemaConfig && individualConfig && (
              <span className="xr-mono-muted" data-testid="extraction-review-config-refs">
                {`${schemaConfig.config_ref} v${schemaConfig.version} · ${individualConfig.config_ref} v${individualConfig.version}`}
              </span>
            )}
          </div>
        </div>
        {runs.lastRequest && text !== runText && (
          <>
            <div className="xr-gap-sm" />
            <FormCallout variant="warn" icon="alert" data-testid="extraction-review-stale">
              The paragraph changed since the last run. Highlights show the text that was run.
              Re-run to review the new text.
            </FormCallout>
          </>
        )}
      </Panel>

      <div className="xr-gap" />
      <TabBar
        tabs={[
          { id: "schema", label: "Schema extraction", count: schemaCount },
          { id: "individual", label: "Individual extraction", count: individualCount },
        ]}
        activeTabId={tab}
        onSelectTab={(id) => setTab(id as ReviewKind)}
        data-testid="extraction-review-tabs"
      />
      <div className="xr-gap-sm" />
      {/* Both tabs stay mounted so review decisions survive switching tabs. */}
      <div role="tabpanel" aria-label="Schema extraction" hidden={tab !== "schema"}>
        <SchemaCandidateReview
          slot={runs.schema}
          text={runText}
          scope={reviewScope}
          onRetry={() => void runs.rerun("schema")}
        />
      </div>
      <div role="tabpanel" aria-label="Individual extraction" hidden={tab !== "individual"}>
        <IndividualCandidateReview
          slot={runs.individual}
          text={runText}
          scope={reviewScope}
          onRetry={() => void runs.rerun("individual")}
        />
      </div>
    </div>
  );
}
