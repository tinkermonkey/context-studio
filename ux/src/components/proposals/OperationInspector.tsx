import { Fragment, type ReactNode } from "react";
import { Chip, FormCallout, InspectorPanel } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  CLASS_ID_FIELDS,
  OPERATION_STATUS_VARIANT,
  asApplied,
  SCOPE_VARIANT,
  changeRows,
  fieldLabel,
  formatProbability,
  formatValue,
  planKind,
  propertyTriples,
  replacementEndLabel,
  replacementDeletedFlag,
  replacementFlag,
} from "./proposalModel";
import { subjectOf } from "./OperationDiff";
import type { OperationContext } from "./useOperationContext";
import "./proposals.css";

/** A property operation's triple fields under the names a reviewer reads them by. */
const PROPERTY_FIELD_LABELS: Record<string, string> = {
  canonical_predicate: "predicate",
  domain_class_id: "source",
  range_class_id: "destination",
  // A DR relationship type's x-dr-evidence lines, not the proposal's evidence.
  evidence: "spec evidence",
};

/** Fields whose values are ids or references: monospace, breaking after dots and underscores. */
const ID_FIELDS = new Set([
  "canonical_predicate",
  "domain_class_id",
  "range_class_id",
  "parent_class_id",
  "identifier",
  "external_references",
  "concept_scheme_id",
  "taxonomy_id",
]);

/** An id with line-break opportunities after its dots and underscores. */
function breakable(text: string): ReactNode {
  return text.split(/(?<=[._])/).map((part, i) => (
    <Fragment key={i}>
      {i > 0 && <wbr />}
      {part}
    </Fragment>
  ));
}

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

export function operationTitle(proposed: ProposedOperation, context: OperationContext): string {
  const operation = asApplied(proposed);
  if (operation.kind === "property") {
    const { before, after } = propertyTriples(
      operation,
      context.currentProperty(operation.target_id),
    );
    const triple = after ?? before;
    const text = triple
      ? `${context.endLabel(triple.domain, operation)} ${triple.predicate ?? "—"} ${context.endLabel(triple.range, operation)}`
      : operation.kind;
    return operation.op === "delete" ? `Remove ${text}` : text;
  }
  const subject = subjectOf(operation, context);
  return operation.op === "delete" ? `Remove ${subject}` : subject;
}

/** The type a delete names as its replacement, and how its pair compares with the deleted type's. */
function ReplacementSection({
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
  return (
    <InspectorPanel.Section title="Replacement">
      <div
        className="op-inspector__stack op-replacement"
        data-testid="operation-replacement"
        data-pair={flag.pair}
      >
        <FormCallout
          variant={flag.warn ? "warn" : "info"}
          icon={flag.warn ? "alert" : "info"}
          data-testid="operation-replacement-callout"
        >
          {flag.text}
        </FormCallout>
        {gone && (
          <FormCallout
            variant="warn"
            icon="alert"
            data-testid="operation-replacement-deleted-callout"
            data-cycle={check.cycle ? "true" : "false"}
          >
            {gone.text}
          </FormCallout>
        )}
        <div className="op-inspector__chips">
          <Chip form="id-tag">{check.identifier ?? check.replacement_id}</Chip>
          <Chip variant={flag.variant}>{flag.chip}</Chip>
          {gone && <Chip variant="rose">{gone.chip}</Chip>}
        </div>
      </div>
    </InspectorPanel.Section>
  );
}

interface OperationInspectorProps {
  operation: ProposedOperation;
  context: OperationContext;
  /** The Decision section (accept / reject / edit) goes first; decided operations have none. */
  decision?: ReactNode;
}

/** The selected operation: its change field by field, rationale and evidence. */
export function OperationInspector({ operation, context, decision }: OperationInspectorProps) {
  const rows = changeRows(operation);
  const kind = planKind(operation);
  const evidence = (operation.evidence ?? []) as EvidenceItem[];
  const label = (field: string) =>
    operation.kind === "property" ? (PROPERTY_FIELD_LABELS[field] ?? field) : fieldLabel(field);
  const value = (field: string, v: unknown): ReactNode => {
    if (field === "evidence" && Array.isArray(v) && v.length > 0) {
      return (
        <ul className="op-change__lines">
          {v.map((line, i) => (
            <li key={i}>{formatValue(line)}</li>
          ))}
        </ul>
      );
    }
    const text =
      CLASS_ID_FIELDS.has(field) && typeof v === "string"
        ? context.endLabel(v, operation)
        : formatValue(v);
    return ID_FIELDS.has(field) ? breakable(text) : text;
  };
  const valueClass = (field: string) =>
    ID_FIELDS.has(field) ? "op-change__value op-change__value--id" : "op-change__value";

  return (
    <div data-testid="operation-inspector" className="operation-inspector">
      <InspectorPanel
        eyebrow={`OPERATION · seq ${operation.seq} · ${operation.op} · ${operation.kind}`}
        title={operationTitle(operation, context)}
        id={operation.id}
      >
        {decision}

        {/* Before the change: a replacement linking a different pair is what to judge first. */}
        {operation.replacement_check && (
          <ReplacementSection operation={operation} context={context} />
        )}

        <InspectorPanel.Section title="Change">
          <div className="op-inspector__stack">
            {/* The Decision section, when there is one, explains a stale operation itself. */}
            {operation.stale && !decision && (
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
              <dl className="op-change-list" data-testid="operation-change-table">
                {rows.map((row, index) => (
                  <div
                    key={row.field}
                    className="op-change"
                    data-testid={`operation-change-row-${row.field}`}
                  >
                    <dt className="op-change__field">{label(row.field)}</dt>
                    {operation.op !== "create" && (
                      <dd
                        className={`${valueClass(row.field)} ${
                          row.changed ? "op-change__before--changed" : "op-change__unchanged"
                        }`}
                      >
                        {value(row.field, row.before)}
                      </dd>
                    )}
                    {operation.op === "delete"
                      ? index === 0 && <dd className="op-change__removed">removed</dd>
                      : row.changed && (
                          <dd
                            className={[
                              valueClass(row.field),
                              operation.op === "create" ? "" : "op-change__after--changed",
                            ]
                              .filter(Boolean)
                              .join(" ")}
                          >
                            {value(row.field, row.after)}
                          </dd>
                        )}
                  </div>
                ))}
              </dl>
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
