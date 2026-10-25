import { useMemo, useState } from "react";
import {
  Chip,
  ConfirmDialog,
  FormCallout,
  InspectorPanel,
  KVGrid,
  Panel,
  SegmentedControl,
  StatGrid,
  StatTile,
  Table,
} from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
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
  return {
    ...base,
    label: c.label,
    proposed_definition: c.proposed_definition ?? null,
    proposed_domain: c.candidate_type === "schema_property" ? c.proposed_domain : undefined,
    proposed_range: c.candidate_type === "schema_property" ? c.proposed_range : undefined,
  };
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
    { confidence_threshold: 0, concept_scheme_id: scope.conceptSchemeId },
    completed && !!scope.conceptSchemeId,
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
    () =>
      (["schema_class", "schema_property", "schema_connection"] as const).find(countOf) ??
      "schema_class",
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

  const applyInput = {
    runId,
    kind: "schema" as const,
    scope: { taxonomy_id: scope.taxonomyId, concept_scheme_id: scope.conceptSchemeId },
    decisions,
  };
  const accepted = rows.filter((r) => decisions[r.id] === "yes");
  // A connection whose endpoint is a proposed class that is not accepted (and does
  // not already exist) is skipped on apply.
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
  const orphaned = accepted.filter(
    (r) =>
      r.candidate_type === "schema_connection" &&
      [r.subject_ref, r.object_ref].some((ref) =>
        unacceptedClassLabels.has(ref?.toLowerCase() ?? ""),
      ),
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
  const existingCol = {
    key: "id" as const,
    label: "Existing",
    width: "180px",
    render: (k: unknown) => (
      <ExistingMatchCell
        hit={hitById.get(String(k))}
        loaded={recognitionHits !== undefined}
        data-testid={`extraction-review-schema-existing-${k}`}
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
        render: (v: unknown) => <span className="xr-strong">{String(v)}</span>,
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
      <StatGrid columns={4}>
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
              <InspectorPanel.Section title="Existing match">
                <div data-testid="extraction-review-schema-inspector-match">
                  <KVGrid rows={matchRows(r)} />
                </div>
              </InspectorPanel.Section>
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
          subtitle={`Accept or reject each proposal. Existing: "exists" is reused on apply, "similar" is close to a class already in ${scope.conceptSchemeLabel}.`}
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
        scope={{ taxonomyLabel: scope.taxonomyLabel, conceptSchemeLabel: scope.conceptSchemeLabel }}
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
        subtitle={`${runId} → ${scope.taxonomyLabel} / ${scope.conceptSchemeLabel}`}
        confirmLabel={`Apply ${counts.yes} accepted`}
        message={
          <div className="xr-stack-sm" data-testid="extraction-review-schema-confirm">
            <span>
              Creates draft classes, property definitions and relationships from the {counts.yes}{" "}
              accepted candidates. Rejected and pending candidates are skipped; entities that
              already exist with the same name (ignoring case and spacing) are reused.
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
                {`${orphaned.length} accepted connection${orphaned.length > 1 ? "s" : ""} point${orphaned.length > 1 ? "" : "s"} at a proposed class you did not accept and will be skipped unless that class already exists: ${orphaned.map((r) => r.label).join(", ")}.`}
              </FormCallout>
            )}
          </div>
        }
      />
    </>
  );
}
