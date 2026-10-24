import { useMemo, useState } from "react";
import {
  Button,
  Chip,
  ConfirmDialog,
  InspectorPanel,
  KVGrid,
  Panel,
  SegmentedControl,
  StatGrid,
  StatTile,
  Table,
  type StatusColor,
} from "@tinkermonkey/heimdall-ui";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import {
  useIndividualExtractionCandidates,
  useRecognitionPreview,
  type NodeReference,
  type PredicateReference,
  type RecognitionPreviewHit,
  type RecognitionPreviewResponse,
  type SourceSpan,
  type TripleCandidate,
} from "@/api/hooks/pipeline/useExtractionCandidates";
import type { ReviewRunSlot } from "@/api/hooks/pipeline/useExtractionReviewRuns";
import {
  REVIEW_RECOGNITION_THRESHOLD,
  type ReviewDecisionValue,
} from "@/api/hooks/pipeline/useApplyReviewedRun";
import { SourceText } from "./SourceText";
import { ReviewDecision } from "./ReviewDecision";
import {
  ApplyBar,
  applyResultRows,
  ClassLabel,
  NodeRefCell,
  ProvenanceList,
  RunMeta,
  RunStateBody,
  useClassMeta,
} from "./ReviewParts";
import { countDecisions, locateMention, pct } from "./reviewUtils";
import { useReviewApplyFlow } from "./useReviewApplyFlow";
import type { ReviewScope } from "./ExtractionReviewPage";
import "./ExtractionReview.css";

const PIPELINE_TYPE = "individual_extraction";
const PREVIEW_THRESHOLDS = {
  confidence_threshold: 0,
  recognition_threshold: REVIEW_RECOGNITION_THRESHOLD,
};
const METHOD_VARIANT: Record<string, StatusColor> = {
  exact: "emerald",
  vector: "cyan",
  llm: "violet",
};

export interface TripleRow {
  id: string;
  subject: NodeReference;
  predicate: PredicateReference;
  object: NodeReference;
  confidence: number;
  provenance: SourceSpan[];
}

export interface HitRow extends RecognitionPreviewHit {
  id: string;
  provenance: SourceSpan[];
}

const tripleLabel = (t: TripleRow) =>
  `${t.subject.label} → ${t.predicate.label} → ${t.object.label}`;
const isNewNode = (n: NodeReference) => n.kind !== "literal" && !n.id;
const usesMention = (t: TripleRow, m: string) => t.subject.label === m || t.object.label === m;

/** Inspector key/value grid for one triple endpoint (subject or object). */
function NodeKV({ node, hit }: { node: NodeReference; hit?: HitRow }) {
  const cls = node.kind === "literal" ? undefined : node.class_ids?.[0];
  const { title: clsTitle, layer } = useClassMeta(cls);
  if (node.kind === "literal") {
    return (
      <KVGrid
        rows={[
          { key: "kind", value: "literal" },
          { key: "value", value: <span className="xr-mono">{node.value ?? node.label}</span> },
          { key: "datatype", value: <span className="xr-mono">{node.datatype ?? "—"}</span> },
        ]}
      />
    );
  }
  return (
    <KVGrid
      rows={[
        { key: "label", value: node.label },
        {
          key: "status",
          value: node.id ? (
            <Chip variant="emerald">mapped</Chip>
          ) : (
            <Chip variant="amber">new individual</Chip>
          ),
        },
        ...(node.id
          ? [
              ...(node.title ? [{ key: "existing_title", value: node.title }] : []),
              { key: "individual_id", value: <span className="xr-mono-muted">{node.id}</span> },
            ]
          : []),
        { key: "class", value: cls ? clsTitle : "—" },
        ...(layer ? [{ key: "dr_layer", value: `L${layer.num} · ${layer.layer}` }] : []),
        ...(hit && hit.will_match_existing
          ? [
              {
                key: "recognized_as",
                value: `${hit.resolved_individual_title} (${hit.match_method ?? "?"} ${pct(hit.match_score)})`,
              },
            ]
          : []),
      ]}
    />
  );
}

export interface IndividualCandidateReviewProps {
  slot: ReviewRunSlot;
  text: string;
  scope: ReviewScope;
  onRetry: () => void;
}

export function IndividualCandidateReview({
  slot,
  text,
  scope,
  onRetry,
}: IndividualCandidateReviewProps) {
  const runId = slot.run?.id ?? "";
  const completed = slot.status === "completed";
  const triplesQuery = useIndividualExtractionCandidates(runId, completed);
  const previewQuery = useRecognitionPreview(runId, PREVIEW_THRESHOLDS, completed);

  let body;
  if (slot.status !== "completed") {
    body = (
      <RunStateBody
        state={slot.status}
        kind="individual"
        pipelineType={PIPELINE_TYPE}
        failureReason={slot.error}
        onRetry={onRetry}
      />
    );
  } else if (triplesQuery.error) {
    body = (
      <ErrorBanner
        error={triplesQuery.error}
        onRetry={() => triplesQuery.refetch()}
        message="Failed to load triples"
      />
    );
  } else if (triplesQuery.isLoading || !triplesQuery.data) {
    body = <RunStateBody state="running" kind="individual" pipelineType={PIPELINE_TYPE} />;
  } else if (triplesQuery.data.length === 0) {
    body = <RunStateBody state="empty" kind="individual" pipelineType={PIPELINE_TYPE} />;
  } else {
    body = (
      <IndividualCandidateReviewBody
        key={runId}
        runId={runId}
        triples={triplesQuery.data}
        recognition={previewQuery.data}
        recognitionError={previewQuery.error}
        text={text}
        scope={scope}
      />
    );
  }

  return (
    <div data-testid="extraction-review-individual">
      <RunMeta
        slot={slot}
        pipelineType={PIPELINE_TYPE}
        data-testid="extraction-review-individual-run-meta"
      />
      {body}
    </div>
  );
}

export function IndividualCandidateReviewBody({
  runId,
  triples: rawTriples,
  recognition,
  recognitionError,
  text,
  scope,
}: {
  runId: string;
  triples: TripleCandidate[];
  recognition?: RecognitionPreviewResponse;
  recognitionError?: Error | null;
  text: string;
  scope: ReviewScope;
}) {
  const triples = useMemo<TripleRow[]>(
    () =>
      rawTriples.map((t) => ({
        id: t.candidate_id,
        subject: t.subject,
        predicate: t.predicate,
        object: t.object,
        confidence: t.confidence,
        provenance: t.provenance ?? [],
      })),
    [rawTriples],
  );
  // Hits carry no spans: locate each mention label in the run text client-side.
  const hits = useMemo<HitRow[]>(
    () =>
      (recognition?.hits ?? []).map((h, i) => ({
        ...h,
        id: `hit-${i}`,
        provenance: [locateMention(text, h.mention_label)],
      })),
    [recognition, text],
  );

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, ReviewDecisionValue>>({});
  const [merges, setMerges] = useState<Record<string, ReviewDecisionValue>>({});
  const [nodeFilter, setNodeFilter] = useState<"all" | "mapped" | "new">("all");
  const flow = useReviewApplyFlow({
    applied: "Individuals applied",
    reverted: "draft individuals removed",
  });

  const allItems = useMemo<Array<{ id: string }>>(() => [...triples, ...hits], [triples, hits]);
  const matchedHits = hits.filter((h) => h.will_match_existing);
  const hasNewNode = (t: TripleRow) => isNewNode(t.subject) || isNewNode(t.object);
  const filtered = triples.filter((t) =>
    nodeFilter === "all" ? true : nodeFilter === "new" ? hasNewNode(t) : !hasNewNode(t),
  );
  const nodes = Object.values(
    Object.fromEntries(
      triples
        .flatMap((t) => [t.subject, t.object])
        .filter((n) => n.kind !== "literal")
        .map((n) => [n.label, n]),
    ),
  );
  const counts = countDecisions(
    decisions,
    triples.map((t) => t.id),
  );
  const mergeCounts = countDecisions(
    merges,
    matchedHits.map((h) => h.id),
  );
  const selectedId =
    allItems.find((it) => it.id === selectedKey)?.id ?? filtered[0]?.id ?? triples[0]?.id;
  const hitFor = (node: NodeReference) => hits.find((h) => h.mention_label === node.label);
  const spans = useMemo(
    () => [
      ...triples.flatMap((t) => t.provenance.map((s) => ({ ...s, key: t.id }))),
      ...hits.flatMap((h) => h.provenance.map((s) => ({ ...s, key: h.id }))),
    ],
    [triples, hits],
  );
  const setDecision = (k: string, v: ReviewDecisionValue) =>
    setDecisions((d) => ({ ...d, [k]: v }));

  const applyInput = {
    runId,
    kind: "individual" as const,
    scope: { taxonomy_id: scope.taxonomyId },
    decisions,
    mentions: matchedHits.map((h) => ({
      mention_label: h.mention_label,
      individual_id: h.resolved_individual_id ?? "",
      decision: merges[h.id] ?? "pending",
    })),
  };
  const accepted = triples.filter((t) => decisions[t.id] === "yes").map((t) => t.id);
  const undecidedMatches = mergeCounts.pending;

  const renderInspector = (item: { id: string }) => {
    const t = triples.find((x) => x.id === item.id);
    const h = hits.find((x) => x.id === item.id);
    return (
      <div className="xr-stack">
        <Panel
          title="Source text"
          subtitle="Highlights link to triples and mentions. Click one to select it."
          data-testid="extraction-review-individual-source-panel"
        >
          <SourceText
            text={text}
            spans={spans}
            activeKey={item.id}
            onSelectKey={setSelectedKey}
            data-testid="extraction-review-individual-source"
          />
        </Panel>
        {t && (
          <InspectorPanel
            eyebrow="TRIPLE CANDIDATE"
            title={tripleLabel(t)}
            id={`${runId} · ${t.id} · ${pct(t.confidence)}`}
            actions={
              <ReviewDecision
                value={decisions[t.id] ?? "pending"}
                onChange={(v) => setDecision(t.id, v)}
                data-testid="extraction-review-individual-inspector-decision"
              />
            }
            data-testid="extraction-review-individual-inspector"
          >
            <InspectorPanel.Section title="Subject">
              <NodeKV node={t.subject} hit={hitFor(t.subject)} />
            </InspectorPanel.Section>
            <InspectorPanel.Section title="Predicate">
              <KVGrid
                rows={[
                  { key: "label", value: <span className="xr-mono">{t.predicate.label}</span> },
                  {
                    key: "property",
                    value: t.predicate.property_definition_id ? (
                      <Chip variant="emerald">mapped</Chip>
                    ) : (
                      <Chip variant="amber">new property</Chip>
                    ),
                  },
                ]}
              />
            </InspectorPanel.Section>
            <InspectorPanel.Section title="Object">
              <NodeKV node={t.object} hit={hitFor(t.object)} />
            </InspectorPanel.Section>
            <InspectorPanel.Section title="Provenance" count={t.provenance.length}>
              <ProvenanceList provenance={t.provenance} />
            </InspectorPanel.Section>
          </InspectorPanel>
        )}
        {h && (
          <InspectorPanel
            eyebrow="RECOGNITION HIT"
            title={h.mention_label}
            id={h.resolved_individual_id || "no match"}
            data-testid="extraction-review-recognition-inspector"
          >
            <InspectorPanel.Section title="Match">
              <KVGrid
                rows={[
                  {
                    key: "will_match",
                    value: h.will_match_existing ? "existing individual" : "created as new",
                  },
                  { key: "resolved_title", value: h.resolved_individual_title || "—" },
                  { key: "method", value: h.match_method || "—" },
                  { key: "score", value: <span className="xr-mono">{pct(h.match_score)}</span> },
                  {
                    key: "classes",
                    value: (
                      <span className="xr-chip-row">
                        {(h.candidate_class_ids ?? []).map((c) => (
                          <Chip key={c} form="id-tag">
                            <ClassLabel id={c} />
                          </Chip>
                        ))}
                      </span>
                    ),
                  },
                ]}
              />
            </InspectorPanel.Section>
            <InspectorPanel.Section
              title="Triples using this mention"
              count={triples.filter((x) => usesMention(x, h.mention_label)).length}
            >
              <div className="xr-stack-sm">
                {triples
                  .filter((x) => usesMention(x, h.mention_label))
                  .map((x) => (
                    <Button
                      key={x.id}
                      variant="link"
                      size="sm"
                      className="xr-link-wrap"
                      onClick={() => setSelectedKey(x.id)}
                    >
                      {tripleLabel(x)}
                    </Button>
                  ))}
              </div>
            </InspectorPanel.Section>
          </InspectorPanel>
        )}
      </div>
    );
  };

  return (
    <>
      <StatGrid columns={4}>
        <StatTile
          label="TRIPLES"
          value={triples.length}
          color="violet"
          icon="link"
          meta={`${counts.yes} accepted · ${counts.no} rejected`}
        />
        <StatTile
          label="MAPPED NODES"
          value={nodes.filter((n) => n.id).length}
          color="emerald"
          icon="check"
          meta="resolve to existing individuals"
        />
        <StatTile
          label="NEW NODES"
          value={nodes.filter((n) => !n.id).length}
          color="amber"
          icon="plus"
          meta="created on apply"
        />
        <StatTile
          label="RECOGNITION"
          value={recognition ? `${recognition.matched_count} / ${recognition.total_mentions}` : "—"}
          color="cyan"
          icon="search"
          meta={
            recognition
              ? `${recognition.unmatched_count} unmatched · ${recognition.skipped_count} skipped`
              : "loading preview"
          }
        />
      </StatGrid>
      <div className="xr-gap" />
      <SchemaPageLayout
        data={allItems}
        selectedId={selectedId}
        renderInspectorContent={renderInspector}
      >
        <div className="xr-stack">
          <Panel
            noPadding
            title="Extracted triples"
            subtitle="Mapped nodes resolve to an existing individual. New nodes are created on apply."
            headerAction={
              <SegmentedControl
                value={nodeFilter}
                onChange={(v) => setNodeFilter(v as "all" | "mapped" | "new")}
                options={[
                  { value: "all", label: "All" },
                  { value: "mapped", label: "Mapped only" },
                  { value: "new", label: "Has new node" },
                ]}
              />
            }
            data-testid="extraction-review-triples"
          >
            <Table<TripleRow>
              columns={[
                {
                  key: "subject",
                  label: "Subject",
                  render: (v) => <NodeRefCell node={v as NodeReference} />,
                },
                {
                  key: "predicate",
                  label: "Predicate",
                  width: "140px",
                  render: (v) => {
                    const p = v as PredicateReference;
                    return (
                      <div className="xr-node-ref">
                        <span className="xr-mono">{p.label}</span>
                        {p.property_definition_id ? (
                          <span className="xr-mono-muted">↳ {p.property_definition_id}</span>
                        ) : (
                          <span>
                            <Chip variant="amber">new property</Chip>
                          </span>
                        )}
                      </div>
                    );
                  },
                },
                {
                  key: "object",
                  label: "Object",
                  render: (v) => <NodeRefCell node={v as NodeReference} />,
                },
                {
                  key: "confidence",
                  label: "Conf",
                  width: "60px",
                  render: (v) => <span className="xr-mono">{pct(v as number)}</span>,
                },
                {
                  key: "id",
                  label: "Decision",
                  width: "84px",
                  render: (k) => (
                    <ReviewDecision
                      compact
                      value={decisions[String(k)] ?? "pending"}
                      onChange={(v) => setDecision(String(k), v)}
                      data-testid={`extraction-review-individual-decision-${k}`}
                    />
                  ),
                },
              ]}
              data={filtered}
              rowKey="id"
              selectedRows={selectedId ? [selectedId] : []}
              onRowClick={(r) => setSelectedKey(r.id)}
              emptyState={<div className="xr-empty">No triples match this filter.</div>}
            />
          </Panel>

          <Panel
            noPadding
            title="Recognition · dedup hits"
            subtitle={`Mentions that match an existing individual (recognition ≥ ${pct(REVIEW_RECOGNITION_THRESHOLD)}). Merge reuses the existing node; keep separate creates a new one.`}
            headerAction={
              <span className="xr-chip-row">
                <Chip variant="emerald">{mergeCounts.yes} merge</Chip>
                <Chip variant="neutral">{mergeCounts.no} separate</Chip>
              </span>
            }
            data-testid="extraction-review-recognition"
          >
            {recognitionError ? (
              <ErrorBanner error={recognitionError} compact message="Recognition preview failed" />
            ) : (
              <Table<HitRow>
                columns={[
                  {
                    key: "mention_label",
                    label: "Mention",
                    width: "170px",
                    render: (v) => <span className="xr-strong">{String(v)}</span>,
                  },
                  {
                    key: "resolved_individual_title",
                    label: "Existing individual",
                    render: (v, h) =>
                      h.will_match_existing ? (
                        <div className="xr-node-ref">
                          <span>{String(v ?? "—")}</span>
                          <span className="xr-mono-muted">
                            {h.candidate_class_ids?.[0] ? (
                              <ClassLabel id={h.candidate_class_ids[0]} />
                            ) : (
                              h.resolved_individual_id
                            )}
                          </span>
                        </div>
                      ) : (
                        <span className="xr-mono-muted">no match · created as new</span>
                      ),
                  },
                  {
                    key: "match_method",
                    label: "Method",
                    width: "84px",
                    render: (v) =>
                      v ? (
                        <Chip variant={METHOD_VARIANT[String(v)] ?? "neutral"}>{String(v)}</Chip>
                      ) : (
                        <span className="xr-mono-muted">—</span>
                      ),
                  },
                  {
                    key: "match_score",
                    label: "Score",
                    width: "64px",
                    render: (v) => <span className="xr-mono">{pct(v as number | null)}</span>,
                  },
                  {
                    key: "id",
                    label: "Decision",
                    width: "236px",
                    render: (k, h) =>
                      h.will_match_existing ? (
                        <ReviewDecision
                          value={merges[String(k)] ?? "pending"}
                          onChange={(v) => setMerges((m) => ({ ...m, [String(k)]: v }))}
                          yes="Merge"
                          no="Keep separate"
                          data-testid={`extraction-review-recognition-decision-${k}`}
                        />
                      ) : (
                        <Chip variant="amber">new</Chip>
                      ),
                  },
                ]}
                data={hits}
                rowKey="id"
                selectedRows={selectedId ? [selectedId] : []}
                onRowClick={(r) => setSelectedKey(r.id)}
                emptyState={
                  <div className="xr-empty">
                    {recognition ? "No mentions previewed." : "Loading recognition preview…"}
                  </div>
                }
              />
            )}
          </Panel>
        </div>
      </SchemaPageLayout>
      <div className="xr-gap" />
      <ApplyBar
        kind="individual"
        counts={counts}
        scope={{ taxonomyLabel: scope.taxonomyLabel }}
        applied={flow.applied}
        busy={flow.busy}
        onApply={flow.openConfirm}
        onRevert={() => flow.revertRun(runId)}
        extra={[
          ...(flow.result
            ? applyResultRows(
                flow.result,
                accepted,
                (id) =>
                  triples.find((t) => t.id === id)
                    ? tripleLabel(triples.find((t) => t.id === id)!)
                    : id,
                (id) =>
                  hits.find((h) => h.resolved_individual_id === id)?.resolved_individual_title ??
                  id,
              )
            : []),
          {
            key: "recognition",
            value: (
              <span className="xr-chip-row">
                <Chip variant="emerald">{mergeCounts.yes} merge</Chip>
                <Chip variant="neutral">{mergeCounts.no} keep separate</Chip>
                <span className="xr-mono-muted">
                  threshold {REVIEW_RECOGNITION_THRESHOLD.toFixed(2)}
                </span>
              </span>
            ),
          },
        ]}
      />
      <ConfirmDialog
        isOpen={flow.confirmOpen}
        onClose={flow.closeConfirm}
        onConfirm={() => flow.confirm(applyInput)}
        variant="primary"
        title="Apply individual extraction"
        subtitle={`${runId} → ${scope.taxonomyLabel}`}
        confirmLabel={`Apply ${counts.yes} accepted`}
        message={
          <div className="xr-stack-sm" data-testid="extraction-review-individual-confirm">
            <span>
              Creates draft individuals and relationships from {counts.yes} accepted triples;
              rejected and pending triples are skipped.
            </span>
            <span className="xr-chip-row">
              <Chip variant="emerald">{mergeCounts.yes} merge into existing</Chip>
              <Chip variant="neutral">{mergeCounts.no} kept separate</Chip>
              {undecidedMatches > 0 && (
                <Chip variant="cyan">{undecidedMatches} left to recognition</Chip>
              )}
            </span>
            {undecidedMatches > 0 && (
              <span className="xr-mono-muted">
                {`Undecided mentions merge automatically when recognition scores ≥ ${pct(REVIEW_RECOGNITION_THRESHOLD)}.`}
              </span>
            )}
          </div>
        }
      />
    </>
  );
}
