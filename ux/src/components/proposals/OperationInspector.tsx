import type { ReactNode } from "react";
import { Chip, FormCallout, InspectorPanel } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  CLASS_ID_FIELDS,
  OPERATION_STATUS_VARIANT,
  SCOPE_VARIANT,
  changeRows,
  formatProbability,
  formatValue,
  planKind,
  propertyTriples,
} from "./proposalModel";
import { subjectOf } from "./OperationDiff";
import type { OperationContext } from "./useOperationContext";
import "./proposals.css";

/** A property operation's triple fields under the names a reviewer reads them by. */
const PROPERTY_FIELD_LABELS: Record<string, string> = {
  canonical_predicate: "predicate",
  domain_class_id: "source",
  range_class_id: "destination",
};

interface EvidenceItem {
  quote?: unknown;
  claim_id?: unknown;
  url?: unknown;
  entity_id?: unknown;
}

function evidenceCaption(item: EvidenceItem): string[] {
  return [item.claim_id, item.entity_id, item.url].filter(
    (v): v is string => typeof v === "string" && v.length > 0,
  );
}

export function operationTitle(operation: ProposedOperation, context: OperationContext): string {
  if (operation.kind === "property") {
    const { before, after } = propertyTriples(
      operation,
      context.currentProperty(operation.target_id),
    );
    const triple = after ?? before;
    const text = triple
      ? `${context.classLabel(triple.domain)} ${triple.predicate ?? "—"} ${context.classLabel(triple.range)}`
      : operation.kind;
    return operation.op === "delete" ? `Remove ${text}` : text;
  }
  const subject = subjectOf(operation, context);
  return operation.op === "delete" ? `Remove ${subject}` : subject;
}

interface OperationInspectorProps {
  operation: ProposedOperation;
  context: OperationContext;
  /** The Decision section (accept / reject / edit) goes first; the review queue's read-only view has none. */
  decision?: ReactNode;
}

/** The selected operation: its change field by field, rationale and evidence. */
export function OperationInspector({ operation, context, decision }: OperationInspectorProps) {
  const rows = changeRows(operation);
  const kind = planKind(operation);
  const evidence = (operation.evidence ?? []) as EvidenceItem[];
  const label = (field: string) =>
    operation.kind === "property" ? (PROPERTY_FIELD_LABELS[field] ?? field) : field;
  const value = (field: string, v: unknown) =>
    CLASS_ID_FIELDS.has(field) && typeof v === "string" ? context.classLabel(v) : formatValue(v);

  return (
    <div data-testid="operation-inspector">
      <InspectorPanel
        eyebrow={`OPERATION · seq ${operation.seq} · ${operation.op} · ${operation.kind}`}
        title={operationTitle(operation, context)}
        id={operation.id}
      >
        {decision}

        <InspectorPanel.Section title="Change">
          <div className="op-inspector__stack">
            {operation.stale && (
              <FormCallout variant="warn" icon="alert" data-testid="operation-stale-callout">
                The target changed after this was proposed, so the before values may no longer match
                the workspace.
              </FormCallout>
            )}
            <div className="op-inspector__status">
              <Chip variant={OPERATION_STATUS_VARIANT[operation.status]}>{operation.status}</Chip>
              {operation.reason && (
                <span className="op-inspector__reason" data-testid="operation-reason">
                  {operation.reason}
                </span>
              )}
            </div>
            {rows.length > 0 ? (
              <table className="op-change-table" data-testid="operation-change-table">
                <thead>
                  <tr>
                    <th scope="col">Field</th>
                    <th scope="col">Before</th>
                    <th scope="col">After</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, index) => (
                    <tr key={row.field} data-testid={`operation-change-row-${row.field}`}>
                      <td className="op-change-table__field">{label(row.field)}</td>
                      <td
                        className={
                          row.changed && row.before !== undefined
                            ? "op-change-table__before--changed"
                            : "op-change-table__muted"
                        }
                      >
                        {operation.op === "create" ? "" : value(row.field, row.before)}
                      </td>
                      <td
                        className={
                          operation.op === "delete"
                            ? "op-change-table__removed"
                            : row.changed
                              ? "op-change-table__after--changed"
                              : "op-change-table__muted"
                        }
                      >
                        {operation.op === "delete"
                          ? index === 0
                            ? "removed"
                            : ""
                          : value(row.field, row.after)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="entity-note">No field changes recorded.</p>
            )}
          </div>
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Rationale">
          <div className="op-inspector__stack">
            <p className="op-inspector__rationale" data-testid="operation-rationale">
              {operation.rationale || "No rationale given."}
            </p>
            <div className="op-inspector__chips">
              {kind && <Chip form="id-tag">{kind}</Chip>}
              <Chip form="id-tag">p {formatProbability(operation.probability)}</Chip>
              <Chip variant={SCOPE_VARIANT[operation.scope]}>{operation.scope}</Chip>
            </div>
          </div>
        </InspectorPanel.Section>

        <InspectorPanel.Section title="Evidence" count={evidence.length}>
          {evidence.length > 0 ? (
            <div className="op-inspector__stack" data-testid="operation-evidence">
              {evidence.map((item, index) => {
                const caption = evidenceCaption(item);
                return (
                  <figure key={index} className="op-evidence">
                    <blockquote className="op-evidence__quote">
                      {typeof item.quote === "string" ? item.quote : formatValue(item.quote)}
                    </blockquote>
                    {caption.length > 0 && (
                      <figcaption className="op-evidence__caption">
                        {caption.join(" · ")}
                      </figcaption>
                    )}
                  </figure>
                );
              })}
            </div>
          ) : (
            <p className="entity-note">No evidence given.</p>
          )}
        </InspectorPanel.Section>
      </InspectorPanel>
    </div>
  );
}
