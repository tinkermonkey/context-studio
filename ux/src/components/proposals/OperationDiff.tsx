import type { ProposedOperation } from "@/api/services/proposals";
import {
  CLASS_ID_FIELDS,
  asApplied,
  changeRows,
  dataValues,
  fieldLabel,
  formatValue,
  operationSubject,
  propertyTriples,
  type Triple,
} from "./proposalModel";
import type { OperationContext } from "./useOperationContext";
import "./proposals.css";

/** Changed fields shown inline for a non-property update; the inspector has them all. */
const INLINE_FIELDS = 2;

interface TripleLineProps {
  triple: Triple;
  operation: ProposedOperation;
  context: OperationContext;
  /** The triple this one replaces: parts that differ from it are highlighted. */
  previous?: Triple;
  className?: string;
}

function TripleLine({ triple, operation, context, previous, className = "" }: TripleLineProps) {
  const changed = (part: keyof Triple) =>
    previous && previous[part] !== triple[part] ? " op-diff__changed" : "";
  return (
    <span className={`op-diff__triple ${className}`.trim()}>
      <span
        className={`op-diff__class${changed("domain")}`}
        title={context.endTitle(triple.domain, operation)}
      >
        {context.endLabel(triple.domain, operation)}
      </span>{" "}
      <span className={`op-diff__predicate${changed("predicate")}`}>{triple.predicate ?? "—"}</span>{" "}
      <span
        className={`op-diff__class${changed("range")}`}
        title={context.endTitle(triple.range, operation)}
      >
        {context.endLabel(triple.range, operation)}
      </span>
    </span>
  );
}

function sameTriple(a?: Triple, b?: Triple): boolean {
  return a?.predicate === b?.predicate && a?.domain === b?.domain && a?.range === b?.range;
}

/** Longest inline value; the inspector shows the whole of it. */
const INLINE_CHARS = 80;

function fieldText(
  field: string,
  value: unknown,
  operation: ProposedOperation,
  context: OperationContext,
): string {
  const text =
    CLASS_ID_FIELDS.has(field) && typeof value === "string"
      ? context.endLabel(value, operation)
      : formatValue(value);
  return clipped(text);
}

function clipped(text: string): string {
  return text.length > INLINE_CHARS ? `${text.slice(0, INLINE_CHARS - 1)}…` : text;
}

/** "brand Makita, watts 1200": the attribute values an individual create sets. */
function createdValues(operation: ProposedOperation): string {
  if (operation.kind !== "individual" || operation.op !== "create") return "";
  return Object.entries(dataValues(operation.fields?.data_properties))
    .map(([key, value]) => `${key} ${formatValue(value)}`)
    .join(", ");
}

function text(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

/**
 * The entity an operation creates or targets, by name. Its own fields name it
 * when they can (a create's, a delete's whole-entity base); else a lookup does,
 * as an update's base holds only the fields it touches. A class reads by its
 * identifier, an attribute with its owning class ("Task · Status"), a
 * relationship as its triple; the id is the last resort.
 */
export function subjectOf(operation: ProposedOperation, context: OperationContext): string {
  const subject = operationSubject(operation);
  const target = operation.target_id;
  switch (operation.kind) {
    case "class":
      return target && subject === target ? context.endLabel(target, operation) : subject;
    case "attribute": {
      const values = {
        ...context.attribute(target),
        ...operation.base,
        ...(operation.op === "create" ? operation.fields : {}),
      } as Record<string, unknown>;
      const name = text(values.title) ?? text(values.identifier);
      if (!name) return subject;
      const owner = context.nameOf(text(values.class_id), operation);
      return owner ? `${owner} · ${name}` : name;
    }
    case "relationship": {
      // An update's base may hold only the attributes it changes: the ends come from a lookup.
      const values = {
        ...context.relationship(target),
        ...operation.base,
        ...operation.fields,
      } as Record<string, unknown>;
      const end = (key: string) => context.nameOf(text(values[key]), operation) ?? "?";
      const predicate = context.predicateOf(text(values.property_definition_id));
      return predicate || values.source_id || values.target_id
        ? `${end("source_id")} ${predicate ?? "?"} ${end("target_id")}`
        : subject;
    }
    default:
      return target && subject === target
        ? (context.nameOf(target, operation) ?? subject)
        : subject;
  }
}

interface OperationDiffProps {
  operation: ProposedOperation;
  context: OperationContext;
}

/**
 * An operation's change in one table cell. A property operation reads as its
 * triple: an update shows the current triple, then the new one with the
 * changed parts highlighted; a delete strikes the triple through; a create
 * shows the new one. Other kinds show the entity and the fields that change.
 */
export function OperationDiff({ operation: proposed, context }: OperationDiffProps) {
  const testId = `operation-diff-${proposed.id}`;
  // An edited operation shows the triple it applied.
  const operation = asApplied(proposed);

  if (operation.kind === "property") {
    const { before, after } = propertyTriples(
      operation,
      context.currentProperty(operation.target_id),
    );
    const otherFields = changeRows(operation)
      .filter(
        (row) =>
          row.changed &&
          !["canonical_predicate", "domain_class_id", "range_class_id"].includes(row.field),
      )
      .map((row) => row.field);
    return (
      <div className="op-diff" data-testid={testId} data-op={operation.op}>
        {operation.op === "create" && after && (
          <TripleLine triple={after} operation={operation} context={context} />
        )}
        {operation.op === "delete" && before && (
          <TripleLine
            triple={before}
            operation={operation}
            context={context}
            className="op-diff__removed"
          />
        )}
        {(operation.op === "update" || operation.op === "move") && before && after && (
          <>
            <TripleLine
              triple={before}
              operation={operation}
              context={context}
              className="op-diff__before"
            />
            {!sameTriple(before, after) ? (
              <span className="op-diff__after">
                <span className="op-diff__to">to</span>{" "}
                <TripleLine
                  triple={after}
                  operation={operation}
                  context={context}
                  previous={before}
                />
              </span>
            ) : (
              <span className="op-diff__note">changes {otherFields.join(", ") || "nothing"}</span>
            )}
          </>
        )}
      </div>
    );
  }

  const subject = subjectOf(operation, context);
  if (operation.op === "create" || operation.op === "delete") {
    const values = createdValues(operation);
    return (
      <div className="op-diff" data-testid={testId} data-op={operation.op}>
        <span className={operation.op === "delete" ? "op-diff__removed" : undefined}>
          <span className="op-diff__kind">{operation.kind}</span> {subject}
        </span>
        {values && (
          <span className="op-diff__note" data-testid={`operation-diff-data-${operation.id}`}>
            {clipped(values)}
          </span>
        )}
      </div>
    );
  }

  const changed = changeRows(operation).filter((row) => row.changed);
  return (
    <div className="op-diff" data-testid={testId} data-op={operation.op}>
      <span>
        <span className="op-diff__kind">{operation.kind}</span> {subject}
      </span>
      {changed.slice(0, INLINE_FIELDS).map((row) => (
        <span key={row.field} className="op-diff__field">
          <span className="op-diff__to">{fieldLabel(row.field)}</span>{" "}
          <span className="op-diff__before">
            {fieldText(row.field, row.before, operation, context)}
          </span>{" "}
          <span className="op-diff__to">→</span>{" "}
          <span className="op-diff__changed">
            {fieldText(row.field, row.after, operation, context)}
          </span>
        </span>
      ))}
      {changed.length > INLINE_FIELDS && (
        <span className="op-diff__note">and {changed.length - INLINE_FIELDS} more</span>
      )}
    </div>
  );
}
