/**
 * An extraction proposal reviewed against its whole source (#1611), worked out
 * in the browser: each element's verdict, its passages as highlights in the
 * source's text, the elements grouped by layer, the progress counts, and where
 * the selection moves after a decision.
 */
import type { ChangeProposal, ProposedOperation, RejectionReason } from "@/api/services/proposals";
import type { components } from "@/api/types";
import type { KeyedSpan } from "@/components/pipeline/extraction-review/reviewUtils";
import { DR_SOURCE } from "../decisionModel";
import { isAwaiting, type ChipVariant } from "../proposalModel";
import { relationshipEnds, sourcePassagesOf, type RelationshipEnd } from "../sourceModel";
import { offsetMap } from "./textOffsets";

type ClassResponse = components["schemas"]["ClassResponse"];

// ==================== Verdicts ====================

/** Where an element stands: awaiting a decision, or how it was decided. */
export type Verdict = "awaiting" | "correct" | "changed" | "rejected" | "added";

export const VERDICTS: Verdict[] = ["awaiting", "correct", "changed", "rejected", "added"];

export const VERDICT_LABEL: Record<Verdict, string> = {
  awaiting: "awaiting",
  correct: "correct",
  changed: "class changed",
  rejected: "not an element",
  added: "added",
};

/** The legend's wording, beside each highlight colour. */
export const VERDICT_LEGEND: Record<Verdict, string> = {
  awaiting: "Awaiting",
  correct: "Correct",
  changed: "Class changed",
  rejected: "Not an element",
  added: "Added by you",
};

export const VERDICT_CHIP: Record<Verdict, ChipVariant> = {
  awaiting: "amber",
  correct: "emerald",
  changed: "violet",
  rejected: "rose",
  added: "cyan",
};

/** An individual create: an element the extraction found in the text. */
export function isElement(operation: ProposedOperation): boolean {
  return operation.op === "create" && operation.kind === "individual";
}

export function isRelationship(operation: ProposedOperation): boolean {
  return operation.kind === "relationship";
}

function classIdsOf(fields: Record<string, unknown> | null | undefined): string[] {
  const ids = fields?.class_ids;
  return Array.isArray(ids) ? ids.filter((id): id is string => typeof id === "string") : [];
}

/** The class the extraction proposed for an element. */
export function proposedClassId(operation: ProposedOperation): string | undefined {
  return classIdsOf(operation.fields)[0];
}

/** The class an element has now: the one it applied with, else the proposed one. */
export function shownClassId(operation: ProposedOperation): string | undefined {
  return classIdsOf(operation.applied_fields)[0] ?? proposedClassId(operation);
}

/** Applied with other classes than proposed. */
export function classChanged(operation: ProposedOperation): boolean {
  if (operation.status !== "applied") return false;
  const applied = classIdsOf(operation.applied_fields);
  if (applied.length === 0) return false;
  const proposed = classIdsOf(operation.fields);
  return applied.length !== proposed.length || applied.some((id, i) => id !== proposed[i]);
}

/** A relationship create's type and ends, as an edit can change them. */
export const RELATIONSHIP_FIELDS = ["property_definition_id", "source_id", "target_id"] as const;

/** The fields an operation has now: the ones it applied with over the proposed ones. */
export function shownFields(operation: ProposedOperation): Record<string, unknown> {
  return { ...(operation.fields ?? {}), ...(operation.applied_fields ?? {}) };
}

/** An element's title as it stands (an edit's over the proposed one), else "#seq". */
export function shownTitle(operation: ProposedOperation): string {
  const title = shownFields(operation).title;
  return typeof title === "string" && title ? title : `#${operation.seq}`;
}

/** A relationship applied with another type or end than proposed. */
export function relationshipEdited(operation: ProposedOperation): boolean {
  if (operation.status !== "applied" || !operation.applied_fields) return false;
  return RELATIONSHIP_FIELDS.some(
    (name) =>
      name in operation.applied_fields! &&
      operation.applied_fields![name] !== operation.fields?.[name],
  );
}

export function verdictOf(operation: ProposedOperation): Verdict {
  if (isAwaiting(operation)) return "awaiting";
  if (operation.status === "rejected") return "rejected";
  if (operation.added_by_reviewer) return "added";
  if (isRelationship(operation)) return relationshipEdited(operation) ? "changed" : "correct";
  return classChanged(operation) ? "changed" : "correct";
}

/** A verdict's label for this operation: a relationship is "edited" or "not a relationship". */
export function verdictLabel(operation: ProposedOperation): string {
  const verdict = verdictOf(operation);
  if (isRelationship(operation)) {
    if (verdict === "changed") return "edited";
    if (verdict === "rejected") return "not a relationship";
  }
  return VERDICT_LABEL[verdict];
}

// ==================== Progress ====================

export interface ReviewProgress {
  decided: number;
  total: number;
  percent: number;
  correct: number;
  changed: number;
  rejected: number;
  added: number;
}

/** How far the review is: decided of total, and how each was decided. */
export function reviewProgress(operations: ProposedOperation[]): ReviewProgress {
  const count = (verdict: Verdict) => operations.filter((o) => verdictOf(o) === verdict).length;
  const total = operations.length;
  const decided = total - count("awaiting");
  return {
    decided,
    total,
    percent: total === 0 ? 0 : Math.round((decided / total) * 100),
    correct: count("correct"),
    changed: count("changed"),
    rejected: count("rejected"),
    added: count("added"),
  };
}

/** "4:07", or "62:10" past the hour: minutes and seconds. */
export function formatDuration(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

// ==================== The source ====================

/** Whether any operation cites a passage in a source: the proposal can be reviewed against it. */
export function extractedFromSource(proposal: ChangeProposal | undefined): boolean {
  return (proposal?.operations ?? []).some(
    (o) => (isElement(o) || isRelationship(o)) && sourcePassagesOf(o).length > 0,
  );
}

/**
 * Whether proposal detail opens `operation` in the review inspector: an
 * individual or relationship create of an extraction from a source. Other
 * operations keep OperationInspector until the inspector learns them (#1660, #1662).
 */
export function opensReviewInspector(
  proposal: ChangeProposal | undefined,
  operation: ProposedOperation,
): boolean {
  return (
    operation.op === "create" &&
    (isElement(operation) || isRelationship(operation)) &&
    extractedFromSource(proposal)
  );
}

/** The source most of the elements' passages are in. */
export function reviewSourceId(operations: ProposedOperation[]): string | undefined {
  const counts = new Map<string, number>();
  for (const operation of operations) {
    for (const passage of sourcePassagesOf(operation)) {
      counts.set(passage.sourceId, (counts.get(passage.sourceId) ?? 0) + 1);
    }
  }
  let best: string | undefined;
  for (const [id, count] of counts) if (best === undefined || count > counts.get(best)!) best = id;
  return best;
}

/**
 * Every element's passages in the source's text, keyed by operation id, at
 * offsets into `text` (which starts at `textStart` in the whole text). The
 * passages' offsets count code points, as the server does; the spans' count
 * UTF-16 units, as the browser does. A passage whose text there isn't its
 * quote is left out, as placePassage does.
 */
export function reviewSpans(
  elements: ProposedOperation[],
  sourceId: string,
  text: string,
  textStart = 0,
): KeyedSpan[] {
  const offsets = offsetMap(text);
  return elements.flatMap((operation) =>
    sourcePassagesOf(operation).flatMap((passage) => {
      if (passage.sourceId !== sourceId) return [];
      const start = offsets.toUtf16(passage.start - textStart);
      const end = offsets.toUtf16(passage.end - textStart);
      if (start === undefined || end === undefined || end <= start) return [];
      const found = text.slice(start, end);
      if (passage.quote && found !== passage.quote) return [];
      return [{ key: operation.id, quote: found, start, end }];
    }),
  );
}

// ==================== Groups and selection ====================

export interface Layer {
  key: string;
  label: string;
}

export interface ElementGroup extends Layer {
  operations: ProposedOperation[];
}

export const RELATIONSHIPS_GROUP = "relationships";

/**
 * Elements grouped by layer, in the order the layers first appear, then the
 * relationship operations in a last "Relationships" group.
 */
export function groupForReview(
  elements: ProposedOperation[],
  relationships: ProposedOperation[],
  layerOf: (operation: ProposedOperation) => Layer,
): ElementGroup[] {
  const groups: ElementGroup[] = [];
  for (const operation of elements) {
    const layer = layerOf(operation);
    let group = groups.find((g) => g.key === layer.key);
    if (!group) {
      group = { ...layer, operations: [] };
      groups.push(group);
    }
    group.operations.push(operation);
  }
  if (relationships.length > 0) {
    groups.push({ key: RELATIONSHIPS_GROUP, label: "Relationships", operations: relationships });
  }
  return groups;
}

export type ElementFilter = "awaiting" | "all";

/** The groups the filter shows: Awaiting keeps the selected element, decided or not. */
export function filterGroups(
  groups: ElementGroup[],
  filter: ElementFilter,
  selectedId: string | undefined,
): ElementGroup[] {
  if (filter === "all") return groups;
  return groups
    .map((g) => ({
      ...g,
      operations: g.operations.filter((o) => isAwaiting(o) || o.id === selectedId),
    }))
    .filter((g) => g.operations.length > 0);
}

/** The operation ids top to bottom. */
export function orderOf(groups: ElementGroup[]): string[] {
  return groups.flatMap((g) => g.operations.map((o) => o.id));
}

/** The next (delta 1) or previous (-1) id in `order`, staying put at either end. */
export function step(order: string[], currentId: string | undefined, delta: 1 | -1) {
  if (order.length === 0) return undefined;
  const at = currentId ? order.indexOf(currentId) : -1;
  if (at < 0) return order[0];
  return order[Math.min(order.length - 1, Math.max(0, at + delta))];
}

/**
 * Where the selection goes after deciding `decidedId`: the next awaiting
 * operation below it, wrapping to the top; undefined when none awaits.
 */
export function nextAwaiting(
  order: string[],
  awaitingIds: Set<string>,
  decidedId: string,
): string | undefined {
  const at = Math.max(0, order.indexOf(decidedId));
  const rotated = [...order.slice(at + 1), ...order.slice(0, at)];
  return rotated.find((id) => id !== decidedId && awaitingIds.has(id));
}

// ==================== Classes ====================

/**
 * A class as the reviewer reads it: its DR reference ("product.feature") when
 * it mirrors a DR spec class, else its title, else its identifier.
 */
export function classLabel(cls: ClassResponse): string {
  const reference = cls.external_references?.find((r) => r.source === DR_SOURCE)?.identifier;
  return reference || cls.title || cls.identifier;
}

/** Classes with the given layer's (concept scheme's) first, each part in its own order. */
export function layerMatesFirst(classes: ClassResponse[], schemeId: string | undefined) {
  if (!schemeId) return classes;
  return [
    ...classes.filter((c) => c.concept_scheme_id === schemeId),
    ...classes.filter((c) => c.concept_scheme_id !== schemeId),
  ];
}

/** How many classes picked earlier in the review are offered as one-key suggestions. */
export const SUGGESTIONS = 3;

/** How many recently picked classes the review keeps; the oldest drops off. */
export const RECENT_CLASSES = 2;

/** Record a class the reviewer picked: most recent first, each once, at most `keep`. */
export function rememberPick(recent: string[], classId: string, keep = RECENT_CLASSES): string[] {
  return [classId, ...recent.filter((id) => id !== classId)].slice(0, keep);
}

/** Forget a recently picked class (the reviewer removed it). */
export function forgetPick(recent: string[], classId: string): string[] {
  return recent.filter((id) => id !== classId);
}

/** Classes picked earlier in this review, most recent first, other than the element's own. */
export function suggestedClasses(recent: string[], currentClassId: string | undefined): string[] {
  return recent.filter((id) => id !== currentClassId).slice(0, SUGGESTIONS);
}

// ==================== Relationships ====================

/** Whether an id field names this element: by its "$ref", or the entity it made. */
function names(value: unknown, element: ProposedOperation): boolean {
  if (typeof value !== "string") return false;
  if (element.ref && value === `$${element.ref}`) return true;
  return !!element.result_entity_id && value === element.result_entity_id;
}

/** The relationship operations with this element at either end. */
export function relationshipsOf(
  element: ProposedOperation,
  operations: ProposedOperation[],
): ProposedOperation[] {
  return operations.filter((o) => {
    if (!isRelationship(o)) return false;
    // As it applied (an edit may have moved an end), and as proposed.
    const ends = [shownFields(o).source_id, shownFields(o).target_id];
    if (o.status !== "applied") ends.push(o.fields?.source_id, o.fields?.target_id);
    return ends.some((end) => names(end, element));
  });
}

/** The operation an end value names: a "$ref" create of the proposal, or the entity one made. */
export function endOperation(
  value: unknown,
  operations: ProposedOperation[],
): ProposedOperation | undefined {
  if (typeof value !== "string") return undefined;
  return operations.find((o) => isElement(o) && names(value, o));
}

/**
 * The entity id an end value stands for: an id as it is, a "$ref" create's
 * result once it applied; undefined for a create not applied.
 */
export function endEntityId(value: unknown, operations: ProposedOperation[]): string | undefined {
  if (typeof value !== "string") return undefined;
  if (!value.startsWith("$")) return value;
  const create = endOperation(value, operations);
  return create?.status === "applied" ? (create.result_entity_id ?? undefined) : undefined;
}

/**
 * What a relationship accepted with this draft sends as its edit: each of
 * its type and ends the reviewer changed, against what it stands for now
 * (an end's entity id); undefined when nothing changed.
 */
export function relationshipEdit(
  operation: ProposedOperation,
  operations: ProposedOperation[],
  draft: Partial<Record<(typeof RELATIONSHIP_FIELDS)[number], string>>,
): Record<string, string> | undefined {
  const edit: Record<string, string> = {};
  for (const name of RELATIONSHIP_FIELDS) {
    const chosen = draft[name];
    if (!chosen) continue;
    const proposed = operation.fields?.[name];
    const current =
      name === "property_definition_id" ? proposed : endEntityId(proposed, operations);
    if (chosen !== current && chosen !== proposed) edit[name] = chosen;
  }
  return Object.keys(edit).length > 0 ? edit : undefined;
}

/**
 * A relationship create's ends that are creates of this proposal still
 * awaiting a decision (it applies once they have), and those rejected (it
 * can't apply).
 */
export function endsToDecide(
  operation: ProposedOperation,
  operations: ProposedOperation[],
): { undecided: RelationshipEnd[]; rejected: RelationshipEnd[] } {
  const ends = relationshipEnds(operation, operations).filter((e) => e.kind !== "existing");
  return {
    undecided: ends.filter((e) => e.status === "pending" || e.status === "failed"),
    rejected: ends.filter((e) => e.status === "rejected"),
  };
}

/** "#2 and #1" */
export function seqList(ends: RelationshipEnd[]): string {
  return [...new Set(ends.map((e) => `#${e.seq}`))].join(" and ");
}

// ==================== An end was rejected ====================

/** The reason a relationship is rejected with when an end of it was rejected. */
export const END_REJECTED_REASON: RejectionReason = "other";

/** The note it records: "An end was rejected: #51 is not an element". */
export function endRejectedNote(seqs: (number | undefined)[]): string {
  const unique = [...new Set(seqs.filter((s): s is number => s !== undefined))];
  return `An end was rejected: ${unique.map((s) => `#${s}`).join(" and ")} ${
    unique.length === 1 ? "is" : "are"
  } not an element`;
}

/** The relationships still awaiting a decision that use this element at either end. */
export function awaitingRelationshipsOf(
  element: ProposedOperation,
  operations: ProposedOperation[],
): ProposedOperation[] {
  return relationshipsOf(element, operations).filter(isAwaiting);
}

// ==================== Not an element ====================

/** What an operation does: a create adds something, any other operation changes what is there. */
export type OperationScope = "create" | "change";

/**
 * Every reason code with the operations it applies to. A create is rejected
 * because of what it proposes; an update, move, delete or type change because
 * of what is there now. The server takes any code on any operation; the offer
 * is the client's.
 */
export const REJECTION_REASONS: {
  code: RejectionReason;
  label: string;
  appliesTo: OperationScope[];
}[] = [
  { code: "not_in_text", label: "Not in this text", appliesTo: ["create"] },
  { code: "too_generic", label: "Too generic", appliesTo: ["create"] },
  { code: "mentioned_only", label: "Mentioned only", appliesTo: ["create"] },
  { code: "out_of_scope", label: "Out of scope", appliesTo: ["create", "change"] },
  { code: "duplicate", label: "Duplicate", appliesTo: ["create"] },
  { code: "incorrect", label: "Wrong", appliesTo: ["change"] },
  { code: "keep_current", label: "Keep as it is", appliesTo: ["change"] },
  { code: "outdated", label: "Out of date", appliesTo: ["change"] },
  { code: "other", label: "Other", appliesTo: ["create", "change"] },
];

export function scopeOf(operation: ProposedOperation): OperationScope {
  return operation.op === "create" ? "create" : "change";
}

/**
 * The reason codes to offer for rejecting these operations with one code:
 * those that apply to every one of them, with "Out of date" first when any is
 * stale. No operations give the codes for a create.
 */
export function reasonsFor(
  operations: ProposedOperation[],
): { code: RejectionReason; label: string }[] {
  const scopes = new Set(operations.map(scopeOf));
  if (scopes.size === 0) scopes.add("create");
  const offered = REJECTION_REASONS.filter((r) =>
    [...scopes].every((scope) => r.appliesTo.includes(scope)),
  );
  if (!operations.some((o) => o.stale)) return offered;
  return [
    ...offered.filter((r) => r.code === "outdated"),
    ...offered.filter((r) => r.code !== "outdated"),
  ];
}

export function reasonLabel(code: RejectionReason | null | undefined): string | undefined {
  return REJECTION_REASONS.find((r) => r.code === code)?.label;
}
