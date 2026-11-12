import { useMemo, useState } from "react";
import {
  Chip,
  ConfirmDialog,
  FormCallout,
  InspectorPanel,
  KVGrid,
  Panel,
  SegmentedControl,
  Select,
  StatGrid,
  StatTile,
  Table,
} from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import {
  useRecognitionPreview,
  useSchemaExtractionCandidates,
  type SchemaExtractionCandidate,
  type SchemaRecognitionHit,
} from "@/api/hooks/pipeline/useExtractionCandidates";
import type { ReviewRunSlot } from "@/api/hooks/pipeline/useExtractionReviewRuns";
import type { ReviewDecisionValue } from "@/api/hooks/pipeline/useApplyReviewedRun";
import { SourceText } from "./SourceText";
import { ReviewDecision } from "./ReviewDecision";
import {
  ApplyBar,
  MATCH_METHOD_VARIANT,
  ProvenanceList,
  RunMeta,
  RunStateBody,
  applyResultRows,
} from "./ReviewParts";
import { countDecisions, pct } from "./reviewUtils";
import { useReviewApplyFlow } from "./useReviewApplyFlow";
import type { ReviewScope } from "./ExtractionReviewPage";
import "./ExtractionReview.css";

type CandidateType = SchemaExtractionCandidate["candidate_type"];

/** A schema candidate flattened into one row shape, keyed for decisions. */
export interface SchemaRow {
  id: string;
  candidate_type: CandidateType;
  confidence: number;
  label: string;
  proposed_definition?: string | null;
  proposed_domain?: string | null;
  proposed_range?: string | null;
  /** Class candidates: the class it is a kind of (existing or proposed); null when top-level. */
  proposed_parent?: string | null;
  /** Attribute candidates: the class it describes; null when none resolves. */
  of_class?: string | null;
  value_type?: string;
  unit?: string | null;
  subject_ref?: string;
  predicate?: string;
  object_ref?: string;
  provenance: NonNullable<SchemaExtractionCandidate["provenance"]>;
}

function toRow(c: SchemaExtractionCandidate): SchemaRow {
  const base = {
    id: c.candidate_id,
    candidate_type: c.candidate_type,
    confidence: c.confidence,
    provenance: c.provenance ?? [],
  };
  if (c.candidate_type === "schema_connection") {
    return {
      ...base,
      label: `${c.subject_ref} → ${c.predicate} → ${c.object_ref}`,
      subject_ref: c.subject_ref,
      predicate: c.predicate,
      object_ref: c.object_ref,
    };
  }
  const shared = { ...base, label: c.label, proposed_definition: c.proposed_definition ?? null };
  if (c.candidate_type === "schema_property") {
    return { ...shared, proposed_domain: c.proposed_domain, proposed_range: c.proposed_range };
  }
  if (c.candidate_type === "schema_attribute") {
    return {
      ...shared,
      of_class: c.of_class ?? null,
      value_type: c.value_type,
      unit: c.unit ?? null,
    };
  }
  return { ...shared, proposed_parent: c.proposed_parent ?? null };
}

const PIPELINE_TYPE = "schema_extraction";

/**
 * Whether a candidate already exists in the target concept scheme. Exact matches
 * are reused on apply; vector matches (classes only) are a "similar to" hint and
 * the candidate is still created as new if accepted.
 */
function ExistingMatchCell({
  hit,
  loaded,
  "data-testid": testId,
}: {
  hit?: SchemaRecognitionHit;
  loaded: boolean;
  "data-testid"?: string;
}) {
  if (!hit?.match_method) {
    return (
      <span data-testid={testId}>
        {loaded ? <Chip variant="amber">new</Chip> : <span className="xr-mono-muted">—</span>}
      </span>
    );
  }
  const exists = hit.will_match_existing;
  return (
    <div className="xr-node-ref" data-testid={testId}>
      <div className="xr-node-ref__head">
        <span>{hit.existing_entity_title}</span>
        <Chip variant={MATCH_METHOD_VARIANT[hit.match_method] ?? "neutral"}>
          {exists ? "exists" : "similar"}
        </Chip>
      </div>
      <span className="xr-mono-muted">
        {exists ? "reused on apply" : `${pct(hit.match_score)} · created as new`}
      </span>
    </div>
  );
}

const matchSummary = (hits: SchemaRecognitionHit[]) => {
  const exist = hits.filter((h) => h.will_match_existing).length;
  const similar = hits.filter((h) => h.match_method === "vector").length;
  return similar > 0 ? `${exist} exist · ${similar} similar` : `${exist} already exist`;
};

export interface SchemaCandidateReviewProps {
  slot: ReviewRunSlot;
  text: string;
  scope: ReviewScope;
  onRetry: () => void;
}

export function SchemaCandidateReview({ slot, text, scope, onRetry }: SchemaCandidateReviewProps) {
  const runId = slot.run?.id ?? "";
  const completed = slot.status === "completed";
  const { data, isLoading, error, refetch } = useSchemaExtractionCandidates(runId, completed);
  const previewQuery = useRecognitionPreview(
    runId,
    { confidence_threshold: 0, taxonomy_id: scope.taxonomyId },
    completed && !!scope.taxonomyId,
  );

  let body;
  if (slot.status !== "completed") {
    body = (
      <RunStateBody
        state={slot.status}
        kind="schema"
        pipelineType={PIPELINE_TYPE}
        failureReason={slot.error}
        onRetry={onRetry}
      />
    );
  } else if (error) {
    body = (
      <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load candidates" />
    );
  } else if (isLoading || !data) {
    body = <RunStateBody state="running" kind="schema" pipelineType={PIPELINE_TYPE} />;
  } else if (data.length === 0) {
    body = <RunStateBody state="empty" kind="schema" pipelineType={PIPELINE_TYPE} />;
  } else {
    body = (
      <SchemaCandidateReviewBody
        key={runId}
        runId={runId}
        rows={data.map(toRow)}
        recognitionHits={previewQuery.data?.schema_hits}
        recognitionError={previewQuery.error}
        text={text}
        scope={scope}
      />
    );
  }

  return (
    <div data-testid="extraction-review-schema">
      <RunMeta
        slot={slot}
        pipelineType={PIPELINE_TYPE}
        data-testid="extraction-review-schema-run-meta"
      />
      {body}
    </div>
  );
}

const TYPE_LABEL: Record<CandidateType, string> = {
  schema_class: "Classes",
  schema_property: "Properties",
  schema_attribute: "Attributes",
  schema_connection: "Connections",
};

function SchemaCandidateReviewBody({
  runId,
  rows,
  recognitionHits,
  recognitionError,
  text,
  scope,
}: {
  runId: string;
  rows: SchemaRow[];
  recognitionHits?: SchemaRecognitionHit[];
  recognitionError?: Error | null;
  text: string;
  scope: ReviewScope;
}) {
  const hitById = useMemo(
    () => new Map((recognitionHits ?? []).map((h) => [h.candidate_id, h])),
    [recognitionHits],
  );
  const hitsOf = (t: CandidateType) =>
    (recognitionHits ?? []).filter((h) => h.candidate_type === t);
  const countOf = (t: CandidateType) => rows.filter((r) => r.candidate_type === t).length;
  const [kind, setKind] = useState<CandidateType>(
    () => (Object.keys(TYPE_LABEL) as CandidateType[]).find(countOf) ?? "schema_class",
  );
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, ReviewDecisionValue>>({});
  const flow = useReviewApplyFlow({
    applied: "Schema candidates applied",
    reverted: "draft schema removed",
  });

  const visible = rows.filter((r) => r.candidate_type === kind);
  // Keep a selection so the source panel + inspector column never disappears.
  const selected = rows.find((r) => r.id === selectedKey) ?? visible[0] ?? rows[0];
  const counts = countDecisions(
    decisions,
    rows.map((r) => r.id),
  );
  const setDecision = (k: string, v: ReviewDecisionValue) =>
    setDecisions((d) => ({ ...d, [k]: v }));
  const spans = useMemo(
    () => rows.flatMap((r) => r.provenance.map((s) => ({ ...s, key: r.id }))),
    [rows],
  );

  const accepted = rows.filter((r) => decisions[r.id] === "yes");
  // Accepted classes that don't exist yet need a concept scheme to go to;
  // classes that already exist anywhere in the taxonomy are reused.
  const newClassCount = accepted.filter(
    (r) => r.candidate_type === "schema_class" && !hitById.get(r.id)?.will_match_existing,
  ).length;
  const { data: schemeList, error: schemesError } = useSchemes(
    scope.taxonomyId || undefined,
    undefined,
    { enabled: !!scope.taxonomyId },
  );
  const schemes = schemeList?.items ?? [];
  const [targetChoice, setTargetChoice] = useState("");
  const targetScheme =
    schemes.length === 1 ? schemes[0] : schemes.find((s) => s.id === targetChoice);
  const targetMissing = newClassCount > 0 && !targetScheme;
  const targetLabel = targetScheme ? `${targetScheme.title} · ${targetScheme.identifier}` : "";

  const applyInput = {
    runId,
    kind: "schema" as const,
    scope: {
      taxonomy_id: scope.taxonomyId,
      concept_scheme_id: newClassCount > 0 ? targetScheme?.id : undefined,
    },
    decisions,
  };
  // A connection whose endpoint, or an attribute whose class, is a proposed class
  // that is not accepted (and does not already exist) is skipped on apply.
  const unacceptedClassLabels = new Set(
    rows
      .filter(
        (r) =>
          r.candidate_type === "schema_class" &&
          decisions[r.id] !== "yes" &&
          !hitById.get(r.id)?.will_match_existing,
      )
      .map((r) => r.label.toLowerCase()),
  );
  const reusedCount = accepted.filter((r) => hitById.get(r.id)?.will_match_existing).length;
  const classRefsOf = (r: SchemaRow) =>
    r.candidate_type === "schema_connection"
      ? [r.subject_ref, r.object_ref]
      : r.candidate_type === "schema_attribute"
        ? [r.of_class]
        : [];
  const orphaned = accepted.filter((r) =>
    classRefsOf(r).some((ref) => unacceptedClassLabels.has(ref?.toLowerCase() ?? "")),
  );
  const labelFor = (id: string) => rows.find((r) => r.id === id)?.label ?? id;

  const decisionCol = {
    key: "id" as const,
    label: "Decision",
    width: "196px",
    render: (k: unknown) => (
      <ReviewDecision
        value={decisions[String(k)] ?? "pending"}
        onChange={(v) => setDecision(String(k), v)}
        data-testid={`extraction-review-schema-decision-${k}`}
      />
    ),
  };
  // Table keys header and cells by column key, so this column can't reuse "id"
  // (the decision column has it); it reads the id from the row instead.
  const existingCol = {
    key: "candidate_type" as const,
    label: "Existing",
    width: "180px",
    render: (_: unknown, r: SchemaRow) => (
      <ExistingMatchCell
        hit={hitById.get(r.id)}
        loaded={recognitionHits !== undefined}
        data-testid={`extraction-review-schema-existing-${r.id}`}
      />
    ),
  };
  const confCol = {
    key: "confidence" as const,
    label: "Conf",
    width: "64px",
    render: (v: unknown) => <span className="xr-mono">{pct(v as number)}</span>,
  };
  const columns = {
    schema_class: [
      {
        key: "label" as const,
        label: "Proposed class",
        width: "160px",
        render: (v: unknown, r: SchemaRow) => (
          <div className="xr-node-ref">
            <span className="xr-strong">{String(v)}</span>
            {r.proposed_parent && (
              <span
                className="xr-mono-muted"
                data-testid={`extraction-review-schema-parent-${r.id}`}
              >
                under {r.proposed_parent}
              </span>
            )}
          </div>
        ),
      },
      {
        key: "proposed_definition" as const,
        label: "Proposed definition",
        render: (v: unknown) =>
          v ? (
            <span className="xr-muted">{String(v)}</span>
          ) : (
            <span className="xr-mono-muted">no definition</span>
          ),
      },
      existingCol,
      confCol,
      decisionCol,
    ],
    schema_property: [
      {
        key: "label" as const,
        label: "Proposed property",
        width: "150px",
        render: (v: unknown) => <span className="xr-mono">{String(v)}</span>,
      },
      {
        key: "proposed_domain" as const,
        label: "Domain → range",
        render: (v: unknown, r: SchemaRow) => (
          <span className="xr-mono-muted">
            {(v as string) || "?"} → {r.proposed_range || "?"}
          </span>
        ),
      },
      existingCol,
      confCol,
      decisionCol,
    ],
    schema_attribute: [
      {
        key: "label" as const,
        label: "Proposed attribute",
        width: "160px",
        render: (v: unknown) => <span className="xr-strong">{String(v)}</span>,
      },
      {
        key: "of_class" as const,
        label: "Of class",
        render: (v: unknown, r: SchemaRow) =>
          v ? (
            <span className="xr-mono" data-testid={`extraction-review-schema-of-class-${r.id}`}>
              {String(v)}
            </span>
          ) : (
            <span
              className="xr-mono-muted"
              data-testid={`extraction-review-schema-of-class-${r.id}`}
            >
              no class · skipped on apply
            </span>
          ),
      },
      {
        key: "value_type" as const,
        label: "Value type",
        width: "100px",
        render: (v: unknown) => <Chip form="id-tag">{String(v || "string")}</Chip>,
      },
      {
        key: "unit" as const,
        label: "Unit",
        width: "72px",
        render: (v: unknown) =>
          v ? (
            <span className="xr-mono">{String(v)}</span>
          ) : (
            <span className="xr-mono-muted">—</span>
          ),
      },
      confCol,
      decisionCol,
    ],
    schema_connection: [
      {
        key: "subject_ref" as const,
        label: "Subject",
        render: (v: unknown) => <span className="xr-mono">{String(v)}</span>,
      },
      {
        key: "predicate" as const,
        label: "Predicate",
        width: "110px",
        render: (v: unknown) => <Chip form="id-tag">{String(v)}</Chip>,
      },
      {
        key: "object_ref" as const,
        label: "Object",
        render: (v: unknown) => <span className="xr-mono">{String(v)}</span>,
      },
      existingCol,
      confCol,
      decisionCol,
    ],
  };

  const proposalRows = (r: SchemaRow) => [
    { key: "candidate_type", value: <span className="xr-mono">{r.candidate_type}</span> },
    { key: "confidence", value: <span className="xr-mono">{pct(r.confidence)}</span> },
    ...(r.candidate_type !== "schema_connection"
      ? [{ key: "definition", value: r.proposed_definition || "—" }]
      : []),
    ...(r.candidate_type === "schema_class"
      ? [
          {
            key: "parent",
            value: <span className="xr-mono">{r.proposed_parent || "— (top-level)"}</span>,
          },
        ]
      : []),
    ...(r.candidate_type === "schema_attribute"
      ? [
          {
            key: "of_class",
            value: <span className="xr-mono">{r.of_class || "— (skipped on apply)"}</span>,
          },
          { key: "value_type", value: <span className="xr-mono">{r.value_type || "string"}</span> },
          { key: "unit", value: <span className="xr-mono">{r.unit || "—"}</span> },
        ]
      : []),
    ...(r.candidate_type === "schema_property"
      ? [
          { key: "domain", value: <span className="xr-mono">{r.proposed_domain || "—"}</span> },
          { key: "range", value: <span className="xr-mono">{r.proposed_range || "—"}</span> },
        ]
      : []),
    ...(r.candidate_type === "schema_connection"
      ? [
          { key: "subject_ref", value: <span className="xr-mono">{r.subject_ref}</span> },
          { key: "predicate", value: <span className="xr-mono">{r.predicate}</span> },
          { key: "object_ref", value: <span className="xr-mono">{r.object_ref}</span> },
        ]
      : []),
  ];

  const matchRows = (r: SchemaRow) => {
    const h = hitById.get(r.id);
    if (!h) return [{ key: "status", value: recognitionHits ? "—" : "loading preview" }];
    return [
      {
        key: "status",
        value: h.will_match_existing
          ? "exists · reused on apply"
          : h.match_method
            ? "similar existing class · created as new"
            : "created as new",
      },
      ...(h.match_method
        ? [
            { key: "existing_title", value: h.existing_entity_title || "—" },
            {
              key: "existing_id",
              value: <span className="xr-mono-muted">{h.existing_entity_id}</span>,
            },
            {
              key: "method",
              value: (
                <Chip variant={MATCH_METHOD_VARIANT[h.match_method] ?? "neutral"}>
                  {h.match_method}
                </Chip>
              ),
            },
            { key: "score", value: <span className="xr-mono">{pct(h.match_score)}</span> },
          ]
        : []),
    ];
  };

  return (
    <>
      <StatGrid columns={5}>
        <StatTile
          label="CLASSES"
          value={countOf("schema_class")}
          color="violet"
          icon="schema"
          meta={recognitionHits ? matchSummary(hitsOf("schema_class")) : "proposed classes"}
        />
        <StatTile
          label="PROPERTIES"
          value={countOf("schema_property")}
          color="cyan"
          icon="component"
          meta={recognitionHits ? matchSummary(hitsOf("schema_property")) : "proposed properties"}
        />
        <StatTile
          label="ATTRIBUTES"
          value={countOf("schema_attribute")}
          color="neutral"
          icon="tag"
          meta="values describing a class"
        />
        <StatTile
          label="CONNECTIONS"
          value={countOf("schema_connection")}
          color="amber"
          icon="link"
          meta={recognitionHits ? matchSummary(hitsOf("schema_connection")) : "class-to-class"}
        />
        <StatTile
          label="ACCEPTED"
          value={`${counts.yes} / ${rows.length}`}
          color="emerald"
          icon="check"
          meta={`${counts.no} rejected · ${counts.pending} pending`}
        />
      </StatGrid>
      <div className="xr-gap" />
      <SchemaPageLayout
        data={rows}
        selectedId={selected?.id}
        renderInspectorContent={(r) => (
          <div className="xr-stack">
            <Panel
              title="Source text"
              subtitle="Highlights are candidate provenance. Click one to select its candidate."
              data-testid="extraction-review-schema-source-panel"
            >
              <SourceText
                text={text}
                spans={spans}
                activeKey={r.id}
                onSelectKey={(k) => {
                  setSelectedKey(k);
                  const hit = rows.find((c) => c.id === k);
                  if (hit) setKind(hit.candidate_type);
                }}
                data-testid="extraction-review-schema-source"
              />
            </Panel>
            <InspectorPanel
              eyebrow={`${r.candidate_type.replace("_", " ").toUpperCase()} CANDIDATE`}
              title={r.label}
              id={`${runId} · ${r.id}`}
              actions={
                <ReviewDecision
                  value={decisions[r.id] ?? "pending"}
                  onChange={(v) => setDecision(r.id, v)}
                  data-testid="extraction-review-schema-inspector-decision"
                />
              }
              data-testid="extraction-review-schema-inspector"
            >
              <InspectorPanel.Section title="Proposal">
                <KVGrid rows={proposalRows(r)} />
              </InspectorPanel.Section>
              {r.candidate_type !== "schema_attribute" && (
                <InspectorPanel.Section title="Existing match">
                  <div data-testid="extraction-review-schema-inspector-match">
                    <KVGrid rows={matchRows(r)} />
                  </div>
                </InspectorPanel.Section>
              )}
              <InspectorPanel.Section title="Provenance" count={r.provenance.length}>
                <ProvenanceList provenance={r.provenance} />
              </InspectorPanel.Section>
            </InspectorPanel>
          </div>
        )}
      >
        <Panel
          noPadding
          title="Candidates"
          subtitle={`Accept or reject each proposal. Existing: "exists" is reused on apply, "similar" is close to a class already in ${scope.taxonomyLabel}.`}
          headerAction={
            <SegmentedControl
              value={kind}
              onChange={(v) => setKind(v as CandidateType)}
              options={(Object.keys(TYPE_LABEL) as CandidateType[]).map((t) => ({
                value: t,
                label: `${TYPE_LABEL[t]} · ${countOf(t)}`,
              }))}
            />
          }
          data-testid="extraction-review-schema-candidates"
        >
          {recognitionError && (
            <ErrorBanner error={recognitionError} compact message="Existing-match preview failed" />
          )}
          <Table<SchemaRow>
            columns={columns[kind]}
            data={visible}
            rowKey="id"
            selectedRows={selected ? [selected.id] : []}
            onRowClick={(r) => setSelectedKey(r.id)}
            emptyState={<div className="xr-empty">No candidates of this type.</div>}
          />
        </Panel>
      </SchemaPageLayout>
      <div className="xr-gap" />
      <ApplyBar
        kind="schema"
        counts={counts}
        scope={{ taxonomyLabel: scope.taxonomyLabel }}
        target={
          newClassCount > 0 && !flow.applied
            ? {
                key: "new classes go to",
                value: (
                  <TargetSchemePicker
                    schemes={schemes}
                    loaded={schemeList !== undefined}
                    error={schemesError}
                    value={targetChoice}
                    onChange={setTargetChoice}
                    newClassCount={newClassCount}
                  />
                ),
              }
            : undefined
        }
        applyDisabled={targetMissing}
        applied={flow.applied}
        busy={flow.busy}
        onApply={flow.openConfirm}
        onRevert={() => flow.revertRun(runId)}
        extra={
          flow.result
            ? applyResultRows(
                flow.result,
                accepted.map((r) => r.id),
                labelFor,
              )
            : undefined
        }
      />
      <ConfirmDialog
        isOpen={flow.confirmOpen}
        onClose={flow.closeConfirm}
        onConfirm={() => flow.confirm(applyInput)}
        variant="primary"
        title="Apply schema extraction"
        subtitle={`${runId} → ${scope.taxonomyLabel}${newClassCount > 0 ? ` · new classes go to ${targetLabel}` : ""}`}
        confirmLabel={`Apply ${counts.yes} accepted`}
        message={
          <div className="xr-stack-sm" data-testid="extraction-review-schema-confirm">
            <span>
              Creates draft classes, attributes, property definitions and relationships from the{" "}
              {counts.yes} accepted candidates. Rejected and pending candidates are skipped;
              entities that already exist with the same name (ignoring case and spacing) are reused.
            </span>
            {reusedCount > 0 && (
              <span className="xr-chip-row">
                <Chip variant="emerald">{reusedCount} reuse existing</Chip>
              </span>
            )}
            {orphaned.length > 0 && (
              <FormCallout
                variant="warn"
                icon="alert"
                data-testid="extraction-review-schema-orphan-warning"
              >
                {`${orphaned.length} accepted candidate${orphaned.length > 1 ? "s" : ""} point${orphaned.length > 1 ? "" : "s"} at a proposed class you did not accept and will be skipped unless that class already exists: ${orphaned.map((r) => r.label).join(", ")}.`}
              </FormCallout>
            )}
          </div>
        }
      />
    </>
  );
}

type SchemeOption = { id: string; title: string; identifier: string };

/** Where the accepted classes that don't exist yet are created. */
function TargetSchemePicker({
  schemes,
  loaded,
  error,
  value,
  onChange,
  newClassCount,
}: {
  schemes: SchemeOption[];
  loaded: boolean;
  error?: Error | null;
  value: string;
  onChange: (id: string) => void;
  newClassCount: number;
}) {
  const label = (s: SchemeOption) => `${s.title} · ${s.identifier}`;
  if (error) {
    return <ErrorBanner error={error} compact message="Could not load concept schemes" />;
  }
  if (!loaded) return <span className="xr-mono-muted">loading concept schemes…</span>;
  if (schemes.length === 0) {
    return (
      <span
        className="xr-target-error"
        role="alert"
        data-testid="extraction-review-schema-no-schemes"
      >
        This taxonomy has no concept schemes. Add one before applying new classes.
      </span>
    );
  }
  if (schemes.length === 1) {
    return (
      <span className="xr-mono" data-testid="extraction-review-schema-target-scheme">
        {label(schemes[0])}
      </span>
    );
  }
  const chosen = schemes.some((s) => s.id === value);
  return (
    <div className="xr-stack-sm">
      <Select
        value={chosen ? value : ""}
        onChange={onChange}
        placeholder="Choose a concept scheme"
        ariaLabel="Concept scheme for new classes"
        data-testid="extraction-review-schema-target-scheme"
      >
        {schemes.map((s) => (
          <Select.Item key={s.id} value={s.id}>
            {label(s)}
          </Select.Item>
        ))}
      </Select>
      {!chosen && (
        // A polite live region: says why Apply is disabled without shouting
        <span
          className="xr-target-hint"
          role="status"
          data-testid="extraction-review-schema-target-hint"
        >
          {`Choose where the ${newClassCount} new class${newClassCount > 1 ? "es go" : " goes"}.`}
        </span>
      )}
    </div>
  );
}
