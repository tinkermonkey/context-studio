import type { ReactNode } from "react";
import { Chip, Icon, type Column } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  blockersOf,
  decisionState,
  flagVariant,
  isBelowThreshold,
  resolutionChip,
} from "./decisionModel";
import { OperationDiff } from "./OperationDiff";
import { isNearMatch } from "./sourceModel";
import {
  OP_VARIANT,
  formatProbability,
  isAwaiting,
  planKind,
  replacementDeletedFlag,
  replacementEndLabel,
  replacementFlag,
} from "./proposalModel";
import type { OperationContext } from "./useOperationContext";
import "./proposals.css";

type OperationColumn = Column<ProposedOperation>;

export interface ColumnOptions {
  showPlanKind: boolean;
  /** Probabilities below it are muted; undefined without a threshold bar. */
  threshold?: number;
  /**
   * Checkbox selection of awaiting operations, while the proposal takes
   * decisions; `eligible` says which may be bulk-decided at all.
   */
  selection?: {
    checked: Set<string>;
    toggle: (id: string) => void;
    eligible: (row: ProposedOperation) => boolean;
  };
  /** The proposal was reverted: what it applied reads as reverted. */
  reverted: boolean;
  /** Operations the threshold selects: marked in a leading column. */
  thresholdSelected?: Set<string>;
  /** Renders the Change cell instead of the operation's diff. */
  change?: (row: ProposedOperation) => ReactNode;
}

export function operationColumns(
  context: OperationContext,
  options: ColumnOptions,
): OperationColumn[] {
  const { showPlanKind, threshold, selection, reverted, thresholdSelected, change } = options;
  return [
    ...(thresholdSelected
      ? [
          {
            key: "id",
            label: "",
            width: "34px",
            render: (_: unknown, row: ProposedOperation) =>
              thresholdSelected.has(row.id) ? (
                <span
                  className="op-threshold-mark"
                  role="img"
                  aria-label={`Operation ${row.seq} is selected by the threshold`}
                  data-testid={`operation-threshold-mark-${row.id}`}
                >
                  <Icon name="check" size={13} />
                </span>
              ) : null,
          } as OperationColumn,
        ]
      : []),
    ...(selection
      ? [
          {
            key: "id",
            label: "",
            width: "34px",
            // Only an operation awaiting a decision can be picked for a bulk decision,
            // and never a judgment or conflict row of a change plan.
            render: (_: unknown, row: ProposedOperation) =>
              isAwaiting(row) && selection.eligible(row) ? (
                <input
                  type="checkbox"
                  className="table__checkbox"
                  checked={selection.checked.has(row.id)}
                  onChange={() => selection.toggle(row.id)}
                  onClick={(e) => e.stopPropagation()}
                  aria-label={`Select operation ${row.seq}`}
                  data-testid={`operation-check-${row.id}`}
                />
              ) : null,
          } as OperationColumn,
        ]
      : []),
    {
      key: "seq",
      label: "Seq",
      width: "52px",
      render: (value) => <span className="op-seq">{value as number}</span>,
    },
    {
      key: "op",
      label: "Op",
      width: "84px",
      // Neutral once decided: colour means there is something to decide.
      render: (value, row) => (
        <Chip
          variant={flagVariant(row, OP_VARIANT[value as ProposedOperation["op"]])}
          data-testid={`operation-op-${row.id}`}
        >
          {value as string}
        </Chip>
      ),
    },
    {
      key: "fields",
      label: "Change",
      render: (_, row) => (
        <div
          className={isAwaiting(row) ? "op-change-cell" : "op-change-cell op-change-cell--decided"}
        >
          {change ? change(row) : <OperationDiff operation={row} context={context} />}
        </div>
      ),
    },
    ...(showPlanKind
      ? [
          {
            key: "rationale",
            label: "Plan kind",
            width: "140px",
            render: (_: unknown, row: ProposedOperation) => (
              <span className="op-plan-kind">{planKind(row) ?? "—"}</span>
            ),
          } as OperationColumn,
        ]
      : []),
    {
      key: "probability",
      label: "P",
      width: "56px",
      render: (value, row) => (
        <span
          className={
            threshold !== undefined && isBelowThreshold(row, threshold)
              ? "op-probability op-probability--below"
              : "op-probability"
          }
          data-testid={`operation-probability-${row.id}`}
        >
          {formatProbability(value as number | null)}
        </span>
      ),
    },
    {
      key: "status",
      label: "Status",
      width: "180px",
      render: (_, row) => <OperationStatus operation={row} context={context} reverted={reverted} />,
    },
  ];
}

/**
 * The operation's decision state, then its flags: coloured while it awaits a
 * decision, neutral once decided (a record of what was there).
 */
function OperationStatus({
  operation,
  context,
  reverted,
}: {
  operation: ProposedOperation;
  context: OperationContext;
  reverted: boolean;
}) {
  const state = decisionState(operation, reverted);
  const blockers = blockersOf(operation);
  const resolved = resolutionChip(operation);
  return (
    <div
      className="op-status"
      data-testid={`operation-status-${operation.id}`}
      data-status={operation.status}
      data-state={state.state}
    >
      <Chip
        variant={state.variant}
        data-testid={`operation-state-${operation.id}`}
        title={`status: ${operation.status}`}
      >
        {state.label}
      </Chip>
      {operation.stale && (
        <Chip
          variant={flagVariant(operation, "rose")}
          data-testid={`operation-stale-${operation.id}`}
        >
          stale
        </Chip>
      )}
      {operation.matched ? (
        <Chip variant="neutral" data-testid={`operation-near-match-chip-${operation.id}`}>
          used existing
        </Chip>
      ) : (
        isNearMatch(operation) && (
          <Chip
            variant={flagVariant(operation, "violet")}
            data-testid={`operation-near-match-chip-${operation.id}`}
          >
            near match
          </Chip>
        )
      )}
      {operation.domain_range_mismatch && (
        <Chip
          variant="amber"
          data-testid={`operation-domain-range-${operation.id}`}
          title={operation.domain_range_mismatch}
        >
          doesn't fit type
        </Chip>
      )}
      {blockers && (
        <Chip variant="amber" data-testid={`operation-blocked-${operation.id}`}>
          {blockers.edges.length} in use: move or drop
        </Chip>
      )}
      {resolved && (
        <Chip variant="neutral" data-testid={`operation-resolved-${operation.id}`}>
          {resolved}
        </Chip>
      )}
      <ReplacementChip operation={operation} context={context} />
    </div>
  );
}

/** A delete whose named replacement links a different or reversed pair, or is gone. */
function ReplacementChip({
  operation,
  context,
}: {
  operation: ProposedOperation;
  context: OperationContext;
}) {
  const check = operation.replacement_check;
  if (!check) return null;
  const flag = replacementFlag(check, (end) =>
    replacementEndLabel(end, (id) => context.endLabel(id, operation)),
  );
  const gone = replacementDeletedFlag(check, deletedIdentifier(operation));
  if (check.pair === "same" && !gone) return null;
  const text = [check.pair === "same" ? undefined : flag.text, gone?.text]
    .filter(Boolean)
    .join(" ");
  return (
    <span
      className="op-replacement-chips"
      role="note"
      aria-label={text}
      title={text}
      data-testid={`operation-replacement-chip-${operation.id}`}
      data-pair={flag.pair}
      data-replacement-deleted={gone ? (check.cycle ? "cycle" : "chain") : undefined}
    >
      {check.pair !== "same" && (
        <Chip variant={flagVariant(operation, flag.variant)}>{flag.chip}</Chip>
      )}
      {gone && <Chip variant={flagVariant(operation, "rose")}>{gone.chip}</Chip>}
    </span>
  );
}

/** A delete's own type, by identifier, for naming it in a cycle. */
function deletedIdentifier(operation: ProposedOperation): string {
  const identifier = operation.base?.identifier;
  return typeof identifier === "string" ? identifier : (operation.target_id ?? "this type");
}
