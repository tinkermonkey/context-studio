/**
 * The wide diff (#1661): which of an operation's changes are long text, read
 * side by side in an overlay over the panes left of the inspector.
 */
import type { ProposedOperation } from "@/api/services/proposals";
import { changeRows } from "../proposalModel";
import { textDiffOf } from "../textDiff";

/** Characters per diff row in the overlay, at 12px monospace (about 7.2px a character). */
export const WIDE_CHAR_PX = 7.2;
/** The overlay never wraps rows narrower than this. */
export const WIDE_MIN_WIDTH = 60;

/** The fields an update changes as long text with something a diff marks, in row order. */
export function longChangeFields(operation: ProposedOperation): string[] {
  if (operation.op !== "update") return [];
  return changeRows(operation)
    .filter((row) => row.changed && textDiffOf(row.before, row.after) !== undefined)
    .map((row) => row.field);
}

/** The field before or after `field` among `fields`, wrapping around; `field` when it's the only one. */
export function stepField(fields: string[], field: string, by: 1 | -1): string {
  const index = fields.indexOf(field);
  if (fields.length === 0) return field;
  if (index < 0) return fields[0];
  return fields[(index + by + fields.length) % fields.length];
}

/**
 * The next (or previous) operation in `order` after `operationId` that has a
 * long change, with its first long field; undefined when there is none.
 */
export function stepLongChange(
  order: string[],
  operations: ProposedOperation[],
  operationId: string,
  by: 1 | -1,
): { operationId: string; field: string } | undefined {
  const byId = new Map(operations.map((o) => [o.id, o]));
  const start = order.indexOf(operationId);
  for (let i = start + by; i >= 0 && i < order.length; i += by) {
    const operation = byId.get(order[i]);
    const fields = operation ? longChangeFields(operation) : [];
    if (operation && fields.length > 0) return { operationId: operation.id, field: fields[0] };
  }
  return undefined;
}
