import { Fragment, type ReactNode } from "react";
import { Chip } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import {
  SCOPE_VARIANT,
  changeRows,
  fieldLabel,
  fieldLines,
  formatProbability,
  formatValue,
  operationSubject,
  planKind,
  type ChangeRow,
} from "../proposalModel";
import { plainEvidenceOf } from "../sourceModel";
import { showsAsTextDiff, wordDiff, type WordSegment } from "../textDiff";
import type { OperationContext } from "../useOperationContext";
import { ClassPill } from "./ReviewPills";
import type { ReviewSchema } from "./reviewSchema";

/** Fields that name classes: read as class pills (with their hovers) when the schema knows them. */
const CLASS_FIELDS = new Set([
  "class_ids",
  "class_id",
  "parent_class_id",
  "domain_class_id",
  "range_class_id",
]);

/** Fields that name other entities by id: read by name, the id in a tooltip. */
const NAMED_FIELDS = new Set([
  "concept_scheme_id",
  "taxonomy_id",
  "dataset_id",
  "source_id",
  "target_id",
  "property_definition_id",
]);

/** A field's value as a list of items, when it is one; undefined for a single value. */
function listOf(value: unknown): unknown[] | undefined {
  return Array.isArray(value) ? value : undefined;
}

/** A key for comparing list items: strings as they are, anything else as JSON. */
function itemKey(item: unknown): string {
  return typeof item === "string" ? item : JSON.stringify(item);
}

/** Whether a list change gains or loses an item; false when its items were only reordered. */
function listGainsOrLoses(before: unknown[] | undefined, after: unknown[] | undefined): boolean {
  const was = new Set((before ?? []).map(itemKey));
  const now = new Set((after ?? []).map(itemKey));
  return [...now].some((key) => !was.has(key)) || [...was].some((key) => !now.has(key));
}

interface ValueProps {
  field: string;
  value: unknown;
  operation: ProposedOperation;
  /** The proposal's operations, for a "$ref" to one of its creates. */
  operations: ProposedOperation[];
  context: OperationContext;
  schema: ReviewSchema;
}

/** A "$ref" to a create of this proposal: "#seq title (new in this proposal)". */
export function newInProposal(id: string, operations: ProposedOperation[]): string | undefined {
  if (!id.startsWith("$")) return undefined;
  const create = operations.find((o) => o.op === "create" && o.ref && `$${o.ref}` === id);
  return create ? `#${create.seq} ${operationSubject(create)} (new in this proposal)` : undefined;
}

/**
 * Classes by id, as a reviewer reads them: a class pill (with its hover) when
 * the taxonomy has it, an earlier create of this proposal as new in it, else
 * its name; an id that resolves to nothing stays as it is, never blank.
 */
export function ClassRefs({
  ids,
  operation,
  operations,
  context,
  schema,
}: {
  ids: string[];
  operation: ProposedOperation;
  operations: ProposedOperation[];
  context: OperationContext;
  schema: ReviewSchema;
}) {
  return (
    <span className="review-chips">
      {ids.map((id, i) => {
        const created = newInProposal(id, operations);
        if (!created && schema.classOf(id)) return <ClassPill key={`${id}-${i}`} classId={id} />;
        return (
          <span
            key={`${id}-${i}`}
            className={created ? "review-diff__name review-diff__name--new" : "review-diff__name"}
            title={id}
          >
            {created ?? context.nameOf(id, operation) ?? id}
          </span>
        );
      })}
    </span>
  );
}

/** One value of a field, as a reviewer reads it: a class pill, a name, lines, or text. */
function Value({ field, value, operation, operations, context, schema }: ValueProps): ReactNode {
  if (CLASS_FIELDS.has(field)) {
    const ids = typeof value === "string" ? [value] : (listOf(value) ?? []);
    if (ids.length > 0 && ids.every((id): id is string => typeof id === "string")) {
      return (
        <ClassRefs
          ids={ids}
          operation={operation}
          operations={operations}
          context={context}
          schema={schema}
        />
      );
    }
  }
  if (NAMED_FIELDS.has(field) && typeof value === "string" && value) {
    const created = newInProposal(value, operations);
    const name =
      created ??
      (field === "property_definition_id"
        ? context.predicateOf(value)
        : context.nameOf(value, operation));
    return (
      <span
        className={created ? "review-diff__name review-diff__name--new" : "review-diff__name"}
        title={value}
      >
        {name ?? value}
      </span>
    );
  }
  const lines = fieldLines(field, value, (id) => context.endLabel(id, operation));
  if (lines && lines.length > 0) {
    return (
      <ul className="review-diff__lines">
        {lines.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
    );
  }
  return formatValue(value);
}

/** A long text's change as one inline word diff: removed words struck, added ones marked. */
function WordDiff({
  segments,
  label,
  field,
}: {
  segments: WordSegment[];
  label: string;
  field: string;
}) {
  return (
    <p
      className="review-word-diff"
      aria-label={`${label}: what changed`}
      data-testid={`review-diff-text-${field}`}
    >
      {segments.map((segment, i) => (
        <Fragment key={i}>
          {i > 0 && " "}
          {segment.type === "removed" ? (
            <del className="review-word-diff__removed">{segment.text}</del>
          ) : segment.type === "added" ? (
            <ins className="review-word-diff__added">{segment.text}</ins>
          ) : segment.type === "folded" ? (
            <span className="review-word-diff__folded" title={`${segment.count} unchanged words`}>
              {segment.text}
            </span>
          ) : (
            segment.text
          )}
        </Fragment>
      ))}
    </p>
  );
}

/** One row of the change: was → now, a word diff for long text, or what a list gained and lost. */
function ChangeRowView({
  row,
  operation,
  operations,
  context,
  schema,
}: {
  row: ChangeRow;
  operation: ProposedOperation;
  operations: ProposedOperation[];
  context: OperationContext;
  schema: ReviewSchema;
}) {
  const label = fieldLabel(row.field);
  const value = (v: unknown) => (
    <Value
      field={row.field}
      value={v}
      operation={operation}
      operations={operations}
      context={context}
      schema={schema}
    />
  );
  // A long text's change as words; a change of whitespace alone marks nothing, so it reads as was → now.
  const words =
    operation.op === "update" &&
    showsAsTextDiff(row.before, row.after) &&
    typeof row.before === "string" &&
    typeof row.after === "string"
      ? wordDiff(row.before, row.after)
      : undefined;
  const marksWords = !!words?.some((w) => w.type === "removed" || w.type === "added");
  const before = listOf(row.before);
  const after = listOf(row.after);
  let body: ReactNode;
  if (operation.op === "create") {
    body = <div className="review-diff__now">{value(row.after)}</div>;
  } else if (operation.op === "delete") {
    body = <div className="review-diff__was">{value(row.before)}</div>;
  } else if (words && marksWords) {
    body = <WordDiff segments={words} label={label} field={row.field} />;
  } else if ((before || after) && listGainsOrLoses(before, after)) {
    // A list: what it gains and what it loses, by item.
    const kept = new Set((before ?? []).map(itemKey));
    const now = new Set((after ?? []).map(itemKey));
    const added = (after ?? []).filter((item) => !kept.has(itemKey(item)));
    const removed = (before ?? []).filter((item) => !now.has(itemKey(item)));
    body = (
      <div className="review-diff__list">
        {removed.length > 0 && (
          <div className="review-diff__was" data-testid={`review-diff-removed-${row.field}`}>
            <span className="review-diff__sign">−</span>
            {value(removed)}
          </div>
        )}
        {added.length > 0 && (
          <div className="review-diff__now" data-testid={`review-diff-added-${row.field}`}>
            <span className="review-diff__sign">+</span>
            {value(added)}
          </div>
        )}
      </div>
    );
  } else {
    // A single value, or a list whose items only moved: was → now.
    body = (
      <>
        {(before || after) && (before?.length ?? 0) === (after?.length ?? 0) && (
          <span className="review-muted" data-testid={`review-diff-reordered-${row.field}`}>
            Reordered
          </span>
        )}
        <div className="review-diff__was">{value(row.before)}</div>
        <div className="review-diff__now">{value(row.after)}</div>
      </>
    );
  }
  return (
    <div
      className="review-diff__row"
      data-op={operation.op}
      data-testid={`review-diff-row-${row.field}`}
    >
      <dt className="review-diff__field">{label}</dt>
      <dd className="review-diff__values">{body}</dd>
    </div>
  );
}

/**
 * THE CHANGE: one row per field it changes. An update reads was → now (long
 * text as an inline word diff, a list as what it gains and loses); a create
 * lists what it sets, a delete what it removes.
 */
export function ChangeBlock({
  operation,
  operations,
  context,
  schema,
}: {
  operation: ProposedOperation;
  operations: ProposedOperation[];
  context: OperationContext;
  schema: ReviewSchema;
}) {
  const rows = changeRows(operation).filter((row) => operation.op !== "update" || row.changed);
  const unchanged = operation.op === "update" ? changeRows(operation).length - rows.length : 0;
  return (
    <>
      {rows.length > 0 ? (
        <dl className="review-diff" data-testid="review-diff">
          {rows.map((row) => (
            <ChangeRowView
              key={row.field}
              row={row}
              operation={operation}
              operations={operations}
              context={context}
              schema={schema}
            />
          ))}
        </dl>
      ) : (
        <span className="review-muted" data-testid="review-diff">
          No field changes recorded.
        </span>
      )}
      {operation.op === "delete" && (
        <span className="review-block__subtitle">
          {`Removes ${operationSubject(operation)} and the fields above.`}
        </span>
      )}
      {unchanged > 0 && (
        <span className="review-block__subtitle" data-testid="review-diff-unchanged">
          {unchanged === 1
            ? "1 other field stays as it is."
            : `${unchanged} other fields stay as they are.`}
        </span>
      )}
    </>
  );
}

/** WHY: the rationale, the change plan's kind, how sure it is, its scope, and who proposed it. */
export function WhyBlock({
  operation,
  origin,
}: {
  operation: ProposedOperation;
  /** Who proposed it: the proposal's source and its detail. */
  origin?: string;
}) {
  const kind = planKind(operation);
  return (
    <>
      <p className="review-why" data-testid="review-why-rationale">
        {operation.rationale || "No rationale given."}
      </p>
      {operation.notes && (
        <p className="review-why review-muted" data-testid="review-why-notes">
          {operation.notes}
        </p>
      )}
      <div className="review-chips" data-testid="review-why-chips">
        {kind && <Chip form="id-tag">{kind}</Chip>}
        {operation.probability !== null && operation.probability !== undefined && (
          <Chip form="id-tag">p {formatProbability(operation.probability)}</Chip>
        )}
        <Chip variant={SCOPE_VARIANT[operation.scope]}>{operation.scope}</Chip>
        {origin && <span className="review-muted">{origin}</span>}
      </div>
    </>
  );
}

interface EvidenceItem {
  quote?: unknown;
  claim_id?: unknown;
  url?: unknown;
  entity_id?: unknown;
}

/** A sourceless operation's evidence: each quote with its caption (claim, entity, url). */
export function CaptionedEvidence({ operation }: { operation: ProposedOperation }) {
  const items = plainEvidenceOf(operation) as EvidenceItem[];
  if (items.length === 0) return null;
  return (
    <>
      {items.map((item, i) => {
        const caption = [item.claim_id, item.entity_id, item.url].filter(
          (v): v is string => typeof v === "string" && v.length > 0,
        );
        return (
          <figure key={i} className="review-quote" data-testid={`review-quote-${i + 1}`}>
            <blockquote className="review-evidence review-evidence--plain">
              {typeof item.quote === "string" ? item.quote : formatValue(item.quote)}
            </blockquote>
            {caption.length > 0 && (
              <figcaption className="review-quote__caption">{caption.join(" · ")}</figcaption>
            )}
          </figure>
        );
      })}
    </>
  );
}
