/**
 * Read-only views of a change proposal, worked out in the browser from its
 * operations: the tally, the strictest scope, the op mix, a property
 * operation's triple and an operation's field / before / after change rows.
 */
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";

export type ChipVariant = "emerald" | "amber" | "rose" | "cyan" | "violet" | "neutral";
export type OperationStatus = ProposedOperation["status"];
export type ChangeScope = ProposedOperation["scope"];

export interface OperationTally {
  total: number;
  pending: number;
  applied: number;
  rejected: number;
  failed: number;
  /** Still waiting for a decision: pending or failed (a failed one can be applied or rejected). */
  awaiting: number;
}

export function tallyOperations(operations: ProposedOperation[]): OperationTally {
  const tally: OperationTally = {
    total: operations.length,
    pending: 0,
    applied: 0,
    rejected: 0,
    failed: 0,
    awaiting: 0,
  };
  for (const operation of operations) tally[operation.status] += 1;
  tally.awaiting = tally.pending + tally.failed;
  return tally;
}

/** True while an operation waits for a decision: pending, or failed and retryable. */
export function isAwaiting(operation: ProposedOperation): boolean {
  return operation.status === "pending" || operation.status === "failed";
}

/** "22 pending · 0 applied · 0 rejected · 0 failed" */
export function tallyLabel(tally: OperationTally): string {
  return `${tally.pending} pending · ${tally.applied} applied · ${tally.rejected} rejected · ${tally.failed} failed`;
}

/**
 * "5 of 14 · 9 applied": operations awaiting a decision (pending or failed) of
 * the total, plus how many are applied and, if any, how many failed.
 */
export function pendingLabel(tally: OperationTally): string {
  const parts = [`${tally.awaiting} of ${tally.total}`];
  if (tally.applied > 0) parts.push(`${tally.applied} applied`);
  if (tally.failed > 0) parts.push(`${tally.failed} failed`);
  return parts.join(" · ");
}

/** Share of operations decided (applied or rejected), 0 to 100. */
export function decidedPercent(tally: OperationTally): number {
  if (tally.total === 0) return 100;
  return Math.round(((tally.total - tally.awaiting) / tally.total) * 100);
}

const SCOPE_ORDER: ChangeScope[] = ["editorial", "additive", "breaking"];

/** The strictest scope among the operations: breaking > additive > editorial. */
export function strictestScope(operations: ProposedOperation[]): ChangeScope | undefined {
  let strictest: ChangeScope | undefined;
  for (const { scope } of operations) {
    if (!strictest || SCOPE_ORDER.indexOf(scope) > SCOPE_ORDER.indexOf(strictest)) {
      strictest = scope;
    }
  }
  return strictest;
}

/** "7 update · 15 delete", in create / update / move / delete order. */
export function opMixLabel(operations: ProposedOperation[]): string {
  const order: ProposedOperation["op"][] = ["create", "update", "move", "delete"];
  return order
    .map((op) => [op, operations.filter((o) => o.op === op).length] as const)
    .filter(([, count]) => count > 0)
    .map(([op, count]) => `${count} ${op}`)
    .join(" · ");
}

export const SCOPE_VARIANT: Record<ChangeScope, ChipVariant> = {
  editorial: "neutral",
  additive: "emerald",
  breaking: "rose",
};

export const OPERATION_STATUS_VARIANT: Record<OperationStatus, ChipVariant> = {
  pending: "amber",
  applied: "emerald",
  rejected: "neutral",
  failed: "rose",
};

export const PROPOSAL_STATUS_VARIANT: Record<ChangeProposal["status"], ChipVariant> = {
  open: "amber",
  done: "emerald",
  reverted: "neutral",
};

export const OP_VARIANT: Record<ProposedOperation["op"], ChipVariant> = {
  create: "emerald",
  update: "cyan",
  move: "violet",
  delete: "rose",
};

export const SOURCE_VARIANT: Record<ChangeProposal["source"], ChipVariant> = {
  pipeline: "violet",
  chat: "cyan",
  mcp: "cyan",
  bundle: "neutral",
  user: "neutral",
};

/** "just now", "5h ago": formatAge as a phrase. */
export function formatAgo(createdAt: string, now: Date = new Date()): string {
  const age = formatAge(createdAt, now);
  if (age === "now") return "just now";
  if (age === "—") return "at an unknown time";
  return `${age} ago`;
}

/** Compact age: "now", "12m", "5h", "6d". */
export function formatAge(createdAt: string, now: Date = new Date()): string {
  const created = new Date(createdAt);
  if (Number.isNaN(created.getTime())) return "—";
  const minutes = Math.max(0, Math.floor((now.getTime() - created.getTime()) / 60000));
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

/**
 * The plan kind a DR reflection plan writes into each operation's rationale
 * ("… Plan kind rename-predicate, p 0.82; …"), or undefined when absent.
 */
export function planKind(operation: ProposedOperation): string | undefined {
  const match = /\bPlan kind ([\w-]+)/.exec(operation.rationale ?? "");
  return match?.[1];
}

export function formatProbability(probability: number | null | undefined): string {
  return probability === null || probability === undefined ? "—" : probability.toFixed(2);
}

// ==================== Triples (property operations) ====================

/**
 * One end of a triple: a class id (or "$ref" to a create in the same
 * proposal), null for unconstrained ("any"), or undefined when unknown (an
 * update's untouched end whose current property isn't loaded or is gone).
 */
export type TripleEnd = string | null | undefined;

/** A relationship type as predicate plus domain and range ends. */
export interface Triple {
  predicate?: string;
  domain: TripleEnd;
  range: TripleEnd;
}

/** The property definition fields a triple reads; any object with them will do. */
export interface TripleSource {
  canonical_predicate?: string | null;
  title?: string;
  domain_class_id?: string | null;
  range_class_id?: string | null;
}

function text(value: unknown): string | undefined {
  return typeof value === "string" && value ? value : undefined;
}

function endOf(values: Record<string, unknown>, key: string, missing: null | undefined): TripleEnd {
  if (!(key in values)) return missing;
  return text(values[key]) ?? null;
}

/** `missingEnd` is what an absent end means: null (unconstrained) or undefined (unknown). */
function tripleOf(values: Record<string, unknown>, missingEnd: null | undefined): Triple {
  return {
    predicate: text(values.canonical_predicate) ?? text(values.title),
    domain: endOf(values, "domain_class_id", missingEnd),
    range: endOf(values, "range_class_id", missingEnd),
  };
}

/**
 * A property operation's triple before and after it applies.
 *
 * `base` holds only the touched fields' values when proposed (a delete: the
 * whole entity), so the untouched parts of an update come from the current
 * property definition; `base` wins over it because the current one may already
 * carry the applied change. Without the current property those parts are
 * unknown (undefined). A create's missing end is unconstrained (null). A
 * create has no before; a delete has no after.
 */
export function propertyTriples(
  operation: ProposedOperation,
  current?: TripleSource,
): { before?: Triple; after?: Triple } {
  const fields = operation.fields ?? {};
  if (operation.op === "create") return { after: tripleOf(fields, null) };
  const currentValues: Record<string, unknown> = current
    ? {
        canonical_predicate: current.canonical_predicate,
        title: current.title,
        domain_class_id: current.domain_class_id ?? null,
        range_class_id: current.range_class_id ?? null,
      }
    : {};
  const beforeValues = { ...currentValues, ...(operation.base ?? {}) };
  const before = tripleOf(beforeValues, undefined);
  if (operation.op === "delete") return { before };
  return { before, after: tripleOf({ ...beforeValues, ...fields }, undefined) };
}

// ==================== "$ref" (an earlier create in the same proposal) ====================

/** What a "$ref" names: the create's title, and the entity it made once applied. */
export interface RefTarget {
  title: string;
  resultId?: string;
}

/** "$ref" -> its create, for one proposal. */
export type RefMap = Map<string, RefTarget>;

export function proposalRefs(proposal: ChangeProposal): RefMap {
  const refs: RefMap = new Map();
  for (const op of proposal.operations) {
    if (op.op !== "create" || !op.ref) continue;
    refs.set(`$${op.ref}`, {
      title: text(op.fields?.title) ?? text(op.fields?.identifier) ?? `$${op.ref}`,
      resultId: op.status === "applied" ? (op.result_entity_id ?? undefined) : undefined,
    });
  }
  return refs;
}

/** Each operation's proposal's refs, by operation id. */
export function refsByOperation(proposals: ChangeProposal[]): Map<string, RefMap> {
  const byOperation = new Map<string, RefMap>();
  for (const proposal of proposals) {
    const refs = proposalRefs(proposal);
    for (const op of proposal.operations) byOperation.set(op.id, refs);
  }
  return byOperation;
}

/** A class id, or the entity an applied "$ref" create made; unapplied refs stay as given. */
export function resolveRef(id: string, refs?: RefMap): string {
  return id.startsWith("$") ? (refs?.get(id)?.resultId ?? id) : id;
}

/** Class ids an operation's triple or target refers to (for one lookup query). */
export function referencedClassIds(operation: ProposedOperation, refs?: RefMap): string[] {
  const ids: string[] = [];
  for (const values of [operation.fields ?? {}, operation.base ?? {}]) {
    for (const key of ["domain_class_id", "range_class_id", "parent_class_id"]) {
      const value = text(values[key]);
      const id = value && resolveRef(value, refs);
      if (id && !id.startsWith("$")) ids.push(id);
    }
  }
  if (operation.kind === "class" && operation.target_id) ids.push(operation.target_id);
  return ids;
}

/** Ids of the existing property definitions that property operations touch. */
export function referencedPropertyIds(operations: ProposedOperation[]): string[] {
  return operations
    .filter((o) => o.kind === "property" && o.op !== "create" && o.target_id)
    .map((o) => o.target_id as string);
}

/**
 * True when the operation touches a class: as its target, or as a property
 * operation's domain or range, before or after. An update's base carries only
 * the fields it touches, so pass the current property for the untouched ends;
 * pass the proposal's refs so an applied "$ref" end matches the class it made.
 */
export function operationTouchesClass(
  operation: ProposedOperation,
  classId: string,
  currentProperty?: TripleSource,
  refs?: RefMap,
): boolean {
  if (operation.target_id === classId) return true;
  if (operation.kind !== "property") return false;
  const current = (currentProperty ?? {}) as Record<string, unknown>;
  for (const values of [operation.fields ?? {}, operation.base ?? {}, current]) {
    for (const key of ["domain_class_id", "range_class_id"]) {
      const value = text(values[key]);
      if (value && resolveRef(value, refs) === classId) return true;
    }
  }
  return false;
}

// ==================== Change rows (field / before / after) ====================

export interface ChangeRow {
  field: string;
  before?: unknown;
  after?: unknown;
  /** True when before and after differ (or one side is missing). */
  changed: boolean;
}

/** Bookkeeping a delete's whole-entity base carries; not worth a row. */
const HIDDEN_FIELDS = new Set([
  "id",
  "created_at",
  "last_modified",
  "version",
  "status",
  "source_run_id",
  "lexical_senses",
  "ontology_mapping",
  "is_relevant",
]);

/** Fields first in this order, then the rest alphabetically. */
const FIELD_ORDER = [
  "canonical_predicate",
  "domain_class_id",
  "range_class_id",
  "identifier",
  "title",
  "description",
];

function fieldRank(field: string): number {
  const index = FIELD_ORDER.indexOf(field);
  return index === -1 ? FIELD_ORDER.length : index;
}

/**
 * Field / before / after rows for an operation, from `fields` vs `base`.
 * A create has only after values, a delete only before values; an update
 * lists the fields it touches.
 */
export function changeRows(operation: ProposedOperation): ChangeRow[] {
  const fields = operation.fields ?? {};
  const base = operation.base ?? {};
  const names =
    operation.op === "delete"
      ? Object.keys(base)
      : operation.op === "create"
        ? Object.keys(fields)
        : [...new Set([...Object.keys(fields), ...Object.keys(base)])];
  return names
    .filter((field) => !HIDDEN_FIELDS.has(field))
    .sort((a, b) => fieldRank(a) - fieldRank(b) || a.localeCompare(b))
    .map((field) => {
      const before = operation.op === "create" ? undefined : base[field];
      const after = operation.op === "delete" ? undefined : fields[field];
      return { field, before, after, changed: !sameValue(before, after) };
    })
    .filter((row) => !isEmpty(row.before) || !isEmpty(row.after));
}

function isEmpty(value: unknown): boolean {
  return (
    value === undefined ||
    value === null ||
    value === "" ||
    (Array.isArray(value) && value.length === 0)
  );
}

function sameValue(a: unknown, b: unknown): boolean {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

/** A field value as text: strings as-is, external references by identifier, the rest as JSON. */
export function formatValue(value: unknown): string {
  if (isEmpty(value)) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (
    Array.isArray(value) &&
    value.every((v) => v && typeof v === "object" && "identifier" in (v as object))
  ) {
    return value.map((v) => String((v as { identifier: unknown }).identifier)).join(", ");
  }
  return JSON.stringify(value);
}

/** Field names that hold a class id, so their values render as class labels. */
export const CLASS_ID_FIELDS = new Set(["domain_class_id", "range_class_id", "parent_class_id"]);

/** A short name for the entity an operation creates or targets, from its own fields. */
export function operationSubject(operation: ProposedOperation): string {
  const values = operation.op === "create" ? operation.fields : operation.base;
  return (
    text(values?.title) ??
    text(values?.identifier) ??
    text(operation.fields?.title) ??
    (operation.ref ? `$${operation.ref}` : undefined) ??
    operation.target_id ??
    operation.kind
  );
}
