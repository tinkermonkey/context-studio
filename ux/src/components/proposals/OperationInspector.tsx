import { Fragment, type ReactNode } from "react";
import { Chip, FormCallout, InspectorPanel, SideBySideDiff } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import { decisionState, flagVariant } from "./decisionModel";
import {
  CLASS_ID_FIELDS,
  asApplied,
  isAwaiting,
  SCOPE_VARIANT,
  changeRows,
  fieldLabel,
  fieldLines,
  formatProbability,
  formatValue,
  planKind,
  propertyTriples,
  replacementEndLabel,
  replacementDeletedFlag,
  replacementFlag,
} from "./proposalModel";
import { subjectOf } from "./OperationDiff";
import { EvidencePack, ReflectionAnswers } from "./ReflectionAnswers";
import { RelationshipEndsSection, SourcePassageSection } from "./SourcePassage";
import { plainEvidenceOf, relationshipEnds, sourcePassagesOf } from "./sourceModel";
import { textDiffOf } from "./textDiff";
import type { OptionDefinition, Picks, ReflectionOption } from "./tieredModel";
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
  // Once decided the warnings are a record: plain text and neutral chips.
  const awaiting = isAwaiting(operation);
  return (
    <InspectorPanel.Section title="Replacement">
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
    </InspectorPanel.Section>
  );
}

interface OperationInspectorProps {
  operation: ProposedOperation;
  context: OperationContext;
  /** The Decision section goes first: accept / reject / edit, or a decided operation's record. */
  decision?: ReactNode;
  /** The proposal was reverted: what it applied reads as reverted. */
  reverted?: boolean;
  /** A reflection operation's answers the reviewer picked over the plan's. */
  picks?: Picks;
  /** Picking an answer; absent when the answers are read-only. */
  onPick?: (question: string, option: string) => void;
  /** A reflection answer's definition, for its overlay. */
  definitionOf?: (question: string, option: ReflectionOption) => OptionDefinition | undefined;
  /** The proposal's operations, to tell which ends of a relationship create are new in it. */
  operations?: ProposedOperation[];
}

/** The selected operation: its change field by field, rationale and evidence. */
export function OperationInspector({
  operation,
  context,
  decision,
  reverted = false,
  picks = {},
  onPick,
  definitionOf,
  operations = [],
}: OperationInspectorProps) {
  const rows = changeRows(operation);
  const state = decisionState(operation, reverted);
  // A decided operation's Decision section carries its state chip; don't repeat it here.
  const showState = isAwaiting(operation) || !decision;
  const kind = planKind(operation);
  // Source passages show beside the decision; the Evidence section keeps the rest.
  const passages = sourcePassagesOf(operation);
  const evidence = plainEvidenceOf(operation) as EvidenceItem[];
  const ends = relationshipEnds(operation, operations);
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
    // A distinguish_from reads "ClassLabel: when" per entry; evidence signals in their order.
    const lines = fieldLines(field, v, (id) => context.endLabel(id, operation));
    if (lines && lines.length > 0) {
      const List = field === "evidence_signals" ? "ol" : "ul";
      return (
        <List
          className={
            List === "ol" ? "op-change__lines op-change__lines--ordered" : "op-change__lines"
          }
          data-testid={`operation-change-lines-${field}`}
        >
          {lines.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </List>
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

        {/* The passage it came from, right beside the decision. */}
        {passages.length > 0 && <SourcePassageSection passages={passages} />}
        <RelationshipEndsSection ends={ends} />

        {/* Before the change: a replacement linking a different pair is what to judge first. */}
        {operation.replacement_check && (
          <ReplacementSection operation={operation} context={context} />
        )}

        {/* Why, before the details: after the replacement, ahead of the answers and the change. */}
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

        {operation.notes && (
          <InspectorPanel.Section title="Notes">
            <p className="op-inspector__notes" data-testid="operation-notes">
              {operation.notes}
            </p>
          </InspectorPanel.Section>
        )}

        {operation.reflection && operation.reflection.questions.length > 0 && (
          <ReflectionAnswers
            operationId={operation.id}
            reflection={operation.reflection}
            picks={picks}
            onPick={onPick}
            definitionOf={definitionOf}
          />
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
              {showState && (
                <Chip variant={state.variant} data-status={operation.status}>
                  {state.label}
                </Chip>
              )}
              {operation.reason && (
                <span className="op-inspector__reason" data-testid="operation-reason">
                  {operation.reason}
                </span>
              )}
            </div>
            {rows.length > 0 ? (
              <dl className="op-change-list" data-testid="operation-change-table">
                {rows.map((row, index) => {
                  // A long text change reads as a diff that marks the sentences that changed.
                  const diff =
                    operation.op !== "create" && operation.op !== "delete" && row.changed
                      ? textDiffOf(row.before, row.after)
                      : undefined;
                  return diff ? (
                    <div
                      key={row.field}
                      className="op-change"
                      data-testid={`operation-change-row-${row.field}`}
                    >
                      <dt className="op-change__field">{label(row.field)}</dt>
                      <dd className="op-text-diff">
                        <SideBySideDiff
                          lines={diff}
                          aria-label={`${label(row.field)}: what changed`}
                          data-testid={`operation-text-diff-${row.field}`}
                        />
                      </dd>
                    </div>
                  ) : (
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
                  );
                })}
              </dl>
            ) : (
              <p className="entity-note">No field changes recorded.</p>
            )}
          </div>
        </InspectorPanel.Section>

        {operation.reflection ? (
          <EvidencePack blocks={operation.reflection.evidence_pack ?? []} />
        ) : passages.length > 0 && evidence.length === 0 ? null : (
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
        )}
      </InspectorPanel>
    </div>
  );
}
