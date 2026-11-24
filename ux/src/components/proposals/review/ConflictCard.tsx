import { useState, type MouseEvent } from "react";
import { Button, Chip } from "@tinkermonkey/heimdall-ui";
import { decisionState, isBlocked } from "../decisionModel";
import { OperationDiff } from "../OperationDiff";
import { formatProbability, isAwaiting } from "../proposalModel";
import { contradicts, keptNote, kindOf, type ConflictCluster } from "../tieredModel";
import type { OperationContext } from "../useOperationContext";
import type { ProposalActions } from "../useProposalActions";

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
export function ConflictCard({
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
