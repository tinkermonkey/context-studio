import { Chip } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import { blockersOf, flagVariant, resolutionChip } from "../decisionModel";
import { replacementDeletedFlag, replacementEndLabel, replacementFlag } from "../proposalModel";
import { isNearMatch, lacksPassage } from "../sourceModel";
import type { OperationContext } from "../useOperationContext";

/**
 * What a row flags beside its status: stale, a near match (or the existing
 * individual it used), no passage, a misfit for its type, a delete still in
 * use or how it was resolved, and a replacement that links another pair or is gone.
 */
export function RowFlags({
  operation,
  context,
}: {
  operation: ProposedOperation;
  context: OperationContext;
}) {
  const blockers = blockersOf(operation);
  const resolved = resolutionChip(operation);
  return (
    <span className="op-status review-row__flags" data-testid={`operation-status-${operation.id}`}>
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
      {lacksPassage(operation) && (
        <Chip
          variant={flagVariant(operation, "amber")}
          role="note"
          aria-label="No passage: the extraction couldn't place this in its source"
          title="The extraction couldn't place this in its source. Bulk accept holds it back."
          data-testid={`operation-no-passage-${operation.id}`}
        >
          no passage
        </Chip>
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
    </span>
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
