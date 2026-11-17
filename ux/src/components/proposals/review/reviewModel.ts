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

export function verdictOf(operation: ProposedOperation): Verdict {
  if (isAwaiting(operation)) return "awaiting";
  if (operation.status === "rejected") return "rejected";
  if (operation.added_by_reviewer) return "added";
  return classChanged(operation) ? "changed" : "correct";
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

/** Record a class the reviewer picked: most recent first, each once. */
export function rememberPick(recent: string[], classId: string): string[] {
  return [classId, ...recent.filter((id) => id !== classId)];
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
  return operations.filter(
    (o) =>
      isRelationship(o) &&
      (names(o.fields?.source_id, element) || names(o.fields?.target_id, element)),
  );
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

// ==================== Not an element ====================

export const REJECTION_REASONS: { code: RejectionReason; label: string }[] = [
  { code: "not_in_text", label: "Not in this text" },
  { code: "too_generic", label: "Too generic" },
  { code: "mentioned_only", label: "Mentioned only" },
  { code: "out_of_scope", label: "Out of scope" },
  { code: "duplicate", label: "Duplicate" },
  { code: "other", label: "Other" },
];

export function reasonLabel(code: RejectionReason | null | undefined): string | undefined {
  return REJECTION_REASONS.find((r) => r.code === code)?.label;
}
