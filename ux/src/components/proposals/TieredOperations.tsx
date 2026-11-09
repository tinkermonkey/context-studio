import { useState, type MouseEvent } from "react";
import { Button, Chip, Table } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import { decisionState, isBlocked } from "./decisionModel";
import { OperationDiff } from "./OperationDiff";
import { operationColumns } from "./OperationColumns";
import { formatProbability, isAwaiting } from "./proposalModel";
import {
  QUESTION_LABELS,
  bestAlternative,
  contradicts,
  keptNote,
  kindOf,
  mechanicalAtOrAbove,
  pRangeLabel,
  tieredSections,
  type ConflictCluster,
} from "./tieredModel";
import type { OperationContext } from "./useOperationContext";
import type { ProposalActions } from "./useProposalActions";
import "./proposals.css";

interface TieredOperationsProps {
  /** The operations the filter shows. */
  operations: ProposedOperation[];
  /** Every operation of the proposal: conflicts are worked out over all of them. */
  allOperations: ProposedOperation[];
  context: OperationContext;
  /** The proposal takes decisions (it isn't reverted). */
  deciding: boolean;
  reverted: boolean;
  threshold: number;
  onThresholdChange: (threshold: number) => void;
  actions: ProposalActions;
  selectedOperationId?: string;
  onSelectOperation: (operationId: string | undefined) => void;
  /** What to say when the filters show nothing. */
  emptyMessage: string;
}

/**
 * A change plan grouped by kind: mechanical changes accepted by threshold,
 * judgment changes decided row by row, and conflicts side by side. Judgment
 * and conflict rows are never bulk-selected.
 */
export function TieredOperations({
  operations,
  allOperations,
  context,
  deciding,
  reverted,
  threshold,
  onThresholdChange,
  actions,
  selectedOperationId,
  onSelectOperation,
  emptyMessage,
}: TieredOperationsProps) {
  // A card lists the members the filter shows, and goes once it shows none.
  const { mechanical, judgment, clusters, other } = tieredSections(operations, allOperations);
  const shown = new Set(operations.map((o) => o.id));
  const mechanicalOps = mechanical.flatMap((g) => g.operations);
  const picked = deciding ? mechanicalAtOrAbove(mechanicalOps, threshold) : [];
  const pickedIds = new Set(picked.map((o) => o.id));
  const awaitingMechanical = mechanicalOps.filter(isAwaiting).length;
  const selected = selectedOperationId ? [selectedOperationId] : [];
  const onRowClick = (row: ProposedOperation) =>
    onSelectOperation(row.id === selectedOperationId ? undefined : row.id);

  if (operations.length === 0) {
    return <p className="entity-note">{emptyMessage}</p>;
  }

  return (
    <div className="tiered" data-testid="tiered-operations">
      {mechanical.length > 0 && (
        <section
          className="tiered-section"
          aria-labelledby="tiered-mechanical-title"
          data-testid="tiered-mechanical"
        >
          <header className="tiered-section__head">
            <h3 id="tiered-mechanical-title" className="tiered-section__title">
              Mechanical · accept by threshold
            </h3>
            {deciding && awaitingMechanical > 0 && (
              <div className="tiered-threshold" data-testid="tiered-threshold">
                <label htmlFor="tiered-threshold-slider" className="proposal-bar__label">
                  p ≥
                </label>
                <input
                  id="tiered-threshold-slider"
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={threshold}
                  onChange={(e) => onThresholdChange(Number(e.target.value))}
                  className="proposal-bar__slider"
                  aria-label="Accept threshold"
                  aria-valuetext={threshold.toFixed(2)}
                  data-testid="tiered-threshold-slider"
                />
                <span className="proposal-bar__value" data-testid="tiered-threshold-value">
                  {threshold.toFixed(2)}
                </span>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={actions.busy || picked.length === 0}
                  onClick={() => actions.acceptFresh(picked.map((o) => o.id))}
                  data-testid="tiered-accept-threshold"
                >
                  Accept {picked.length} at or above
                </Button>
              </div>
            )}
          </header>
          {mechanical.map((group) => {
            const awaiting = group.operations.filter(isAwaiting).length;
            const k = group.operations.filter((o) => pickedIds.has(o.id)).length;
            return (
              <div
                key={group.kind}
                className="tiered-group"
                data-testid={`tiered-group-${group.kind}`}
              >
                <div className="tiered-group__head">
                  <Chip form="id-tag">{group.kind}</Chip>
                  <span className="tiered-group__meta">
                    {group.operations.length} · {pRangeLabel(group.operations)}
                  </span>
                  {deciding && awaiting > 0 && (
                    <span
                      className="tiered-group__selected"
                      data-testid={`tiered-group-selected-${group.kind}`}
                    >
                      {k} of {awaiting} selected
                    </span>
                  )}
                </div>
                <div className="schema-table-wrap">
                  <Table<ProposedOperation>
                    rowKey="id"
                    columns={operationColumns(context, {
                      showPlanKind: false,
                      threshold: deciding ? threshold : undefined,
                      thresholdSelected: deciding ? pickedIds : undefined,
                      reverted,
                    })}
                    data={group.operations}
                    selectedRows={selected}
                    onRowClick={onRowClick}
                  />
                </div>
              </div>
            );
          })}
        </section>
      )}

      {judgment.length > 0 && (
        <section
          className="tiered-section"
          aria-labelledby="tiered-judgment-title"
          data-testid="tiered-judgment"
        >
          <header className="tiered-section__head">
            <h3 id="tiered-judgment-title" className="tiered-section__title">
              Judgment · decide row by row
            </h3>
            <span className="tiered-section__note">
              Never bulk-selected: open each to weigh the plan&apos;s pick against the alternatives.
            </span>
          </header>
          {judgment.map((group) => (
            <div
              key={group.kind}
              className="tiered-group"
              data-testid={`tiered-group-${group.kind}`}
            >
              <div className="tiered-group__head">
                <Chip form="id-tag">{group.kind}</Chip>
                <span className="tiered-group__meta">
                  {group.operations.length} · {pRangeLabel(group.operations)}
                </span>
              </div>
              <div className="schema-table-wrap">
                <Table<ProposedOperation>
                  rowKey="id"
                  columns={operationColumns(context, {
                    showPlanKind: false,
                    reverted,
                    change: (row) => <JudgmentChange operation={row} context={context} />,
                  })}
                  data={group.operations}
                  selectedRows={selected}
                  onRowClick={onRowClick}
                />
              </div>
            </div>
          ))}
        </section>
      )}

      {clusters.length > 0 && (
        <section
          className="tiered-section"
          aria-labelledby="tiered-conflicts-title"
          data-testid="tiered-conflicts"
        >
          <header className="tiered-section__head">
            <h3 id="tiered-conflicts-title" className="tiered-section__title">
              Conflicts · {clusters.length}
            </h3>
            <span className="tiered-section__note">
              Reflections that disagree about the same types: keep one, or decide each.
            </span>
          </header>
          {clusters.map((cluster) => (
            <ConflictCard
              key={cluster.id}
              cluster={cluster}
              context={context}
              deciding={deciding}
              reverted={reverted}
              actions={actions}
              shown={shown}
              selectedOperationId={selectedOperationId}
              onSelectOperation={onSelectOperation}
            />
          ))}
        </section>
      )}

      {other.length > 0 && (
        <section className="tiered-section" data-testid="tiered-other">
          <header className="tiered-section__head">
            <h3 className="tiered-section__title">Other</h3>
          </header>
          <div className="schema-table-wrap">
            <Table<ProposedOperation>
              rowKey="id"
              columns={operationColumns(context, { showPlanKind: true, reverted })}
              data={other}
              selectedRows={selected}
              onRowClick={onRowClick}
            />
          </div>
        </section>
      )}
    </div>
  );
}

/** A judgment row: the current triple struck through, the plan's pick and the best alternative. */
function JudgmentChange({
  operation,
  context,
}: {
  operation: ProposedOperation;
  context: OperationContext;
}) {
  const reflection = operation.reflection;
  if (!reflection?.current || !reflection.replacement) {
    return <OperationDiff operation={operation} context={context} />;
  }
  const { current } = reflection;
  const alternative = bestAlternative(reflection);
  return (
    <div className="op-diff judgment-change" data-testid={`judgment-change-${operation.id}`}>
      <s className="judgment-change__current">
        {current.source} {current.predicate} {current.target}
      </s>
      <span className="judgment-change__plan">
        <span className="op-diff__to">plan</span> {reflection.replacement}
      </span>
      {alternative && (
        <span className="judgment-change__alternative" data-testid={`judgment-alt-${operation.id}`}>
          <span className="op-diff__to">alt</span>{" "}
          {QUESTION_LABELS[alternative.question]?.toLowerCase() ?? alternative.question}{" "}
          {alternative.option}
          {alternative.current ? " (current)" : ""} · p {alternative.probability.toFixed(2)}
        </span>
      )}
    </div>
  );
}

interface ConflictCardProps {
  cluster: ConflictCluster;
  context: OperationContext;
  deciding: boolean;
  reverted: boolean;
  actions: ProposalActions;
  /** The operations the filter shows: the card lists only those of its members. */
  shown: ReadonlySet<string>;
  selectedOperationId?: string;
  onSelectOperation: (operationId: string | undefined) => void;
}

/**
 * Operations that contradict each other, side by side: keep one (it applies,
 * the others are rejected as "conflict: kept seq N"), keep them all to decide
 * each in the inspector, or reject them all. Once one is applied, by Keep or
 * in the inspector, the rest can only be rejected as kept against it.
 */
function ConflictCard({
  cluster,
  context,
  deciding,
  reverted,
  actions,
  shown,
  selectedOperationId,
  onSelectOperation,
}: ConflictCardProps) {
  const [individually, setIndividually] = useState(false);
  const awaiting = cluster.operations.filter(isAwaiting);
  const kept = cluster.operations.find((o) => o.status === "applied");
  // Once one is applied, only what contradicts it directly is rejected as kept against it.
  const keptAgainst = kept ? awaiting.filter((o) => contradicts(kept, o)) : [];
  const both = cluster.operations.length === 2;
  // Actions only while the card shows a member awaiting a decision: under
  // Decided, a card never acts on members it hides.
  const open = deciding && awaiting.some((o) => shown.has(o.id));
  const rejectNote =
    awaiting.length === 1
      ? "conflict: rejected"
      : both
        ? "conflict: rejected both"
        : "conflict: rejected all";
  return (
    <div
      className="conflict-card"
      role="group"
      aria-label={`Conflict between seq ${cluster.operations.map((o) => o.seq).join(", ")}`}
      data-testid={`conflict-card-${cluster.id}`}
      data-kept={kept?.id}
    >
      <div className="conflict-card__ops">
        {cluster.operations
          .filter((o) => shown.has(o.id))
          .map((o) => {
            const state = decisionState(o, reverted);
            const selected = o.id === selectedOperationId;
            const select = () => onSelectOperation(selected ? undefined : o.id);
            // Clicking anywhere on the item selects it, as a row click does; the seq
            // button stays the control for keyboard and screen-reader users.
            const onItemClick = (e: MouseEvent<HTMLDivElement>) => {
              if ((e.target as HTMLElement).closest("button, a, input, select, textarea")) return;
              // Selecting text to copy it isn't a click on the item.
              if (window.getSelection()?.toString()) return;
              select();
            };
            return (
              <div
                key={o.id}
                className={selected ? "conflict-op conflict-op--selected" : "conflict-op"}
                onClick={onItemClick}
                data-testid={`conflict-op-${o.id}`}
              >
                <span className="conflict-op__head">
                  <button
                    type="button"
                    className="conflict-op__select"
                    aria-pressed={selected}
                    aria-label={`Inspect seq ${o.seq}`}
                    onClick={select}
                    data-testid={`conflict-select-${o.id}`}
                  >
                    seq {o.seq}
                  </button>
                  <Chip form="id-tag">{kindOf(o) ?? "—"}</Chip>
                  <span className="op-probability">p {formatProbability(o.probability)}</span>
                  <Chip variant={state.variant}>{state.label}</Chip>
                </span>
                <OperationDiff operation={o} context={context} />
                <span className="conflict-op__rationale">{o.rationale}</span>
              </div>
            );
          })}
      </div>
      {open &&
        (kept && keptAgainst.length > 0 ? (
          <div className="conflict-card__actions" role="group" aria-label="Resolve the conflict">
            <span className="tiered-section__note" data-testid={`conflict-kept-${cluster.id}`}>
              Seq {kept.seq} is applied.
            </span>
            <Button
              variant="danger"
              size="sm"
              disabled={actions.busy}
              onClick={() =>
                actions.rejectOperations(
                  keptAgainst.map((o) => o.id),
                  keptNote(kept.seq),
                )
              }
              data-testid={`conflict-reject-rest-${cluster.id}`}
            >
              Reject the rest ({keptNote(kept.seq)})
            </Button>
          </div>
        ) : kept || individually ? (
          <p className="tiered-section__note" data-testid={`conflict-individual-${cluster.id}`}>
            {kept ? `Seq ${kept.seq} is applied; nothing left contradicts it. ` : ""}
            Decide each in the inspector.{" "}
            {!kept && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIndividually(false)}
                data-testid={`conflict-back-${cluster.id}`}
              >
                Back
              </Button>
            )}
          </p>
        ) : (
          <div className="conflict-card__actions" role="group" aria-label="Resolve the conflict">
            {awaiting.map((o) => (
              <Button
                key={o.id}
                variant="secondary"
                size="sm"
                disabled={actions.busy || isBlocked(o)}
                title={
                  isBlocked(o)
                    ? "Relationships still use this type: resolve it in the inspector"
                    : undefined
                }
                onClick={() =>
                  actions.keepConflict(
                    o,
                    awaiting.filter((other) => contradicts(o, other)).map((other) => other.id),
                  )
                }
                data-testid={`conflict-keep-${o.id}`}
              >
                Keep seq {o.seq}
              </Button>
            ))}
            {awaiting.length > 1 && (
              <Button
                variant="ghost"
                size="sm"
                disabled={actions.busy}
                onClick={() => setIndividually(true)}
                data-testid={`conflict-keep-all-${cluster.id}`}
              >
                {both ? "Keep both" : "Keep all"}
              </Button>
            )}
            <Button
              variant="danger"
              size="sm"
              disabled={actions.busy}
              onClick={() =>
                actions.rejectOperations(
                  awaiting.map((o) => o.id),
                  rejectNote,
                )
              }
              data-testid={`conflict-reject-all-${cluster.id}`}
            >
              {awaiting.length === 1
                ? "Reject"
                : both
                  ? "Reject both"
                  : `Reject all ${awaiting.length}`}
            </Button>
          </div>
        ))}
    </div>
  );
}
