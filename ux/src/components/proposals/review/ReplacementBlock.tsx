import { Chip, FormCallout } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import { flagVariant } from "../decisionModel";
import {
  isAwaiting,
  replacementDeletedFlag,
  replacementEndLabel,
  replacementFlag,
} from "../proposalModel";
import type { OperationContext } from "../useOperationContext";

/** The type a delete names as its replacement, and how its pair compares with the deleted type's. */
export function ReplacementBlock({
  operation,
  context,
}: {
  operation: ProposedOperation;
  context: OperationContext;
}) {
  const check = operation.replacement_check!;
  const flag = replacementFlag(check, (end) =>
    replacementEndLabel(end, (id) => context.endLabel(id, operation)),
  );
  const identifier = operation.base?.identifier;
  const gone = replacementDeletedFlag(
    check,
    typeof identifier === "string" ? identifier : (operation.target_id ?? "this type"),
  );
  // Once decided the warnings are a record: plain text and neutral chips.
  const awaiting = isAwaiting(operation);
  return (
    <section className="review-block" aria-label="Replacement">
      <span className="review-eyebrow">REPLACEMENT</span>
      <div
        className="op-inspector__stack op-replacement"
        data-testid="operation-replacement"
        data-pair={flag.pair}
      >
        {awaiting ? (
          <FormCallout
            variant={flag.warn ? "warn" : "info"}
            icon={flag.warn ? "alert" : "info"}
            data-testid="operation-replacement-callout"
          >
            {flag.text}
          </FormCallout>
        ) : (
          <p className="op-decided__note" data-testid="operation-replacement-callout">
            {flag.text}
          </p>
        )}
        {gone &&
          (awaiting ? (
            <FormCallout
              variant="warn"
              icon="alert"
              data-testid="operation-replacement-deleted-callout"
              data-cycle={check.cycle ? "true" : "false"}
            >
              {gone.text}
            </FormCallout>
          ) : (
            <p
              className="op-decided__note"
              data-testid="operation-replacement-deleted-callout"
              data-cycle={check.cycle ? "true" : "false"}
            >
              {gone.text}
            </p>
          ))}
        <div className="op-inspector__chips">
          <Chip
            form="id-tag"
            className="op-replacement__id"
            title={check.identifier ?? check.replacement_id}
            data-testid="operation-replacement-id"
          >
            <span className="op-replacement__id-text">
              {check.identifier ?? check.replacement_id}
            </span>
          </Chip>
          <Chip variant={flagVariant(operation, flag.variant)}>{flag.chip}</Chip>
          {gone && <Chip variant={flagVariant(operation, "rose")}>{gone.chip}</Chip>}
        </div>
      </div>
    </section>
  );
}
