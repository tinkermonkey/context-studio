import type { ReactNode } from "react";
import { Button, Chip, FormCallout, Icon, KVGrid, Panel } from "@tinkermonkey/heimdall-ui";
import type { NodeReference, SourceSpan } from "@/api/hooks/pipeline/useExtractionCandidates";
import { useClass } from "@/api/hooks/ontology/useClasses";
import type {
  ReviewKind,
  ReviewRunSlot,
  PipelineRunResponse,
} from "@/api/hooks/pipeline/useExtractionReviewRuns";
import type {
  ApplyRunResponse,
  ReviewDecisionValue,
} from "@/api/hooks/pipeline/useApplyReviewedRun";
import { drLayerOf, isLocated } from "./reviewUtils";
import "./ExtractionReview.css";

// ---- Provenance list (inspector) ----------------------------------------
export function ProvenanceList({ provenance }: { provenance: SourceSpan[] }) {
  if (provenance.length === 0) {
    return <span className="xr-mono-muted">no source spans</span>;
  }
  return (
    <div className="xr-stack-sm" data-testid="extraction-review-provenance">
      {provenance.map((s, i) => (
        <div key={i} className="xr-between">
          <span className="xr-quote">“{s.quote || "—"}”</span>
          {isLocated(s) ? (
            <span className="xr-mono-muted">
              {s.start}–{s.end}
            </span>
          ) : (
            <Chip variant="amber" data-testid="extraction-review-unlocated">
              unlocated
            </Chip>
          )}
        </div>
      ))}
    </div>
  );
}

// ---- Class id → title (class ids are UUIDs in the graph) ----------------
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function ClassLabel({ id }: { id: string }) {
  const { data } = useClass(UUID_RE.test(id) ? id : "");
  return <>{data?.title ?? id}</>;
}

// ---- NodeReference cell: label + mapped/new + DR layer · class ----------
export function NodeRefCell({ node }: { node: NodeReference }) {
  if (node.kind === "literal") {
    return (
      <div className="xr-node-ref">
        <div className="xr-node-ref__head">
          <span className="xr-mono">"{node.value ?? node.label}"</span>
          <Chip variant="neutral">literal</Chip>
        </div>
        {node.datatype && <span className="xr-mono-muted">{node.datatype}</span>}
      </div>
    );
  }
  const mapped = !!node.id;
  const cls = node.class_ids?.[0];
  const layer = drLayerOf(cls);
  return (
    <div className="xr-node-ref">
      <div className="xr-node-ref__head">
        <span className="xr-strong">{node.label}</span>
        <Chip variant={mapped ? "emerald" : "amber"}>{mapped ? "mapped" : "new"}</Chip>
      </div>
      {mapped && node.title && node.title !== node.label && (
        <span className="xr-muted" data-testid="extraction-review-node-title">
          → {node.title}
        </span>
      )}
      {cls && (
        <span className="xr-mono-muted">
          {layer ? `L${layer.num} · ` : ""}
          <ClassLabel id={cls} />
        </span>
      )}
    </div>
  );
}

// ---- Run state header for a tab -----------------------------------------
function runDuration(run?: PipelineRunResponse): string | null {
  if (!run?.started_at || !run.updated_at) return null;
  const ms = new Date(run.updated_at).getTime() - new Date(run.started_at).getTime();
  return Number.isFinite(ms) && ms >= 0 ? `${(ms / 1000).toFixed(1)}s` : null;
}

const STATUS_CHIP: Record<ReviewRunSlot["status"], ReactNode> = {
  idle: <Chip variant="neutral">NOT RUN</Chip>,
  running: <Chip variant="cyan">RUNNING</Chip>,
  completed: <Chip variant="emerald">COMPLETED</Chip>,
  failed: <Chip variant="rose">FAILED</Chip>,
};

export function RunMeta({
  slot,
  pipelineType,
  "data-testid": testId,
}: {
  slot: ReviewRunSlot;
  pipelineType: string;
  "data-testid"?: string;
}) {
  const run = slot.run;
  const duration = slot.status !== "running" ? runDuration(run) : null;
  return (
    <div className="xr-run-meta" data-testid={testId}>
      {run && <Chip form="id-tag">{run.id}</Chip>}
      {STATUS_CHIP[slot.status]}
      <span className="xr-mono-muted">
        {pipelineType}
        {run ? ` · ${run.configuration_slug} v${run.configuration_version}` : ""}
        {duration ? ` · ${duration}` : ""}
      </span>
    </div>
  );
}

// ---- Non-ready body for a tab: idle / running / failed / empty -----------
export type RunBodyState = "idle" | "running" | "failed" | "empty";

export function RunStateBody({
  state,
  kind,
  pipelineType,
  failureReason,
  onRetry,
}: {
  state: RunBodyState;
  kind: ReviewKind;
  pipelineType: string;
  failureReason?: string;
  onRetry?: () => void;
}) {
  if (state === "idle")
    return (
      <Panel data-testid={`extraction-review-${kind}-idle`}>
        <div className="xr-empty">
          <Icon name="zap" size={18} />
          <div>Paste a paragraph above and run extraction to review {pipelineType} candidates.</div>
        </div>
      </Panel>
    );
  if (state === "running")
    return (
      <Panel data-testid={`extraction-review-${kind}-running`}>
        <FormCallout variant="info" icon="clock">
          {`${pipelineType} is running. Candidates appear here when the run completes.`}
        </FormCallout>
      </Panel>
    );
  if (state === "failed")
    return (
      <Panel
        data-testid={`extraction-review-${kind}-failed`}
        footer={
          onRetry ? (
            <div className="xr-actions-end">
              <Button
                variant="secondary"
                size="sm"
                onClick={onRetry}
                data-testid={`extraction-review-${kind}-retry`}
              >
                <Icon name="reload" size={12} /> Re-run {pipelineType}
              </Button>
            </div>
          ) : undefined
        }
      >
        <FormCallout variant="error" icon="alert">
          {`Run failed: ${failureReason ?? "unknown error"}. The other extraction tab is unaffected.`}
        </FormCallout>
      </Panel>
    );
  return (
    <Panel data-testid={`extraction-review-${kind}-empty`}>
      <div className="xr-empty">
        <Icon name="search" size={18} />
        <div>The run completed but produced no candidates for this paragraph.</div>
      </div>
    </Panel>
  );
}

// ---- Post-apply summary rows: what was created, merged and skipped --------
const MERGE_SOURCE_LABEL: Record<string, string> = {
  decision: "your merge",
  recognition: "recognition",
  existing_title: "same title",
};

export function applyResultRows(
  result: ApplyRunResponse,
  accepted: string[],
  labelFor: (candidateId: string) => string,
  titleFor: (individualId: string) => string = (id) => id,
): { key: string; value: ReactNode }[] {
  const created: [string, number][] = (
    [
      ["classes", result.classes_created],
      ["properties", result.properties_created],
      ["individuals", result.individuals_created],
      ["relationships", result.relationships_created],
    ] as [string, number][]
  ).filter(([, n]) => n > 0);
  // skipped_candidate_ids also lists everything not selected: surface only the
  // accepted candidates the server could not write.
  const appliedCount = (result.applied_candidate_ids ?? []).length;
  const skippedIds = new Set(result.skipped_candidate_ids ?? []);
  const skipped = accepted.filter((id) => skippedIds.has(id));
  const merged = result.merged_mentions ?? [];
  return [
    {
      key: "result",
      value: (
        <span className="xr-chip-row" data-testid="extraction-review-apply-result-created">
          <Chip variant="emerald">
            {appliedCount} of {accepted.length} accepted applied
          </Chip>
          {created.length === 0 ? (
            <span className="xr-mono-muted">no new entities (existing ones reused)</span>
          ) : (
            created.map(([kind, n]) => (
              <Chip key={kind} variant="neutral">
                {n} {kind} created
              </Chip>
            ))
          )}
        </span>
      ),
    },
    ...(merged.length > 0
      ? [
          {
            key: "merged",
            value: (
              <div className="xr-stack-sm" data-testid="extraction-review-apply-result-merged">
                {merged.map((m) => (
                  <span key={`${m.mention_label}-${m.individual_id}`} className="xr-chip-row">
                    <span>
                      {m.mention_label} → {titleFor(m.individual_id)}
                    </span>
                    <Chip variant="cyan">{MERGE_SOURCE_LABEL[m.source] ?? m.source}</Chip>
                  </span>
                ))}
              </div>
            ),
          },
        ]
      : []),
    ...(skipped.length > 0
      ? [
          {
            key: "skipped",
            value: (
              <div className="xr-stack-sm" data-testid="extraction-review-apply-result-skipped">
                <span className="xr-chip-row">
                  {skipped.map((id) => (
                    <Chip key={id} variant="amber">
                      {labelFor(id)}
                    </Chip>
                  ))}
                </span>
                <span className="xr-mono-muted">
                  Accepted but not written, e.g. a relationship whose predicate or endpoint class
                  was neither accepted nor already in the graph.
                </span>
              </div>
            ),
          },
        ]
      : []),
  ];
}

// ---- Apply bar (same shape on both tabs) ---------------------------------
export function ApplyBar({
  kind,
  counts,
  scope,
  applied,
  busy,
  onApply,
  onRevert,
  extra,
}: {
  kind: ReviewKind;
  counts: Record<ReviewDecisionValue, number>;
  scope: { taxonomyLabel: string; conceptSchemeLabel?: string };
  applied: boolean;
  busy?: boolean;
  onApply: () => void;
  onRevert: () => void;
  extra?: { key: string; value: ReactNode }[];
}) {
  return (
    <Panel
      data-testid={`extraction-review-${kind}-apply-bar`}
      title={applied ? "Applied" : "Apply to graph"}
      subtitle={
        applied
          ? "Draft entities were written. Revert removes everything this run created."
          : "Accepted candidates are written as DRAFT entities in the run's scope."
      }
    >
      <div className="xr-apply-bar">
        <KVGrid
          keyWidth={150}
          rows={[
            { key: "taxonomy", value: <span className="xr-mono">{scope.taxonomyLabel}</span> },
            ...(kind === "schema"
              ? [
                  {
                    key: "concept_scheme",
                    value: <span className="xr-mono">{scope.conceptSchemeLabel ?? "—"}</span>,
                  },
                ]
              : []),
            {
              key: "decisions",
              value: (
                <span className="xr-chip-row">
                  <Chip variant="emerald">{counts.yes} accepted</Chip>
                  <Chip variant="rose">{counts.no} rejected</Chip>
                  <Chip variant="neutral">{counts.pending} pending</Chip>
                </span>
              ),
            },
            ...(extra ?? []),
          ]}
        />
        <div className="xr-apply-bar__actions">
          {applied ? (
            <Button
              variant="danger"
              onClick={onRevert}
              disabled={busy}
              aria-busy={busy}
              data-testid={`extraction-review-${kind}-revert`}
            >
              <Icon name="reload" size={13} /> Revert run
            </Button>
          ) : (
            <Button
              variant="primary"
              disabled={counts.yes === 0 || busy}
              aria-busy={busy}
              onClick={onApply}
              data-testid={`extraction-review-${kind}-apply`}
            >
              <Icon name="check" size={13} /> Apply {counts.yes} accepted
            </Button>
          )}
        </div>
      </div>
    </Panel>
  );
}
