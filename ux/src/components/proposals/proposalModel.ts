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

/**
 * The operation as it applied: one a reviewer edited applied its
 * `applied_fields` as an update (an edited delete too); others as proposed.
 */
export function asApplied(operation: ProposedOperation): ProposedOperation {
  return operation.applied_fields
    ? { ...operation, op: "update", fields: operation.applied_fields }
    : operation;
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
  const check = operation.replacement_check;
  for (const end of [check?.deleted_domain, check?.deleted_range, check?.domain, check?.range]) {
    const id = end?.id && resolveRef(end.id, refs);
    if (id && !id.startsWith("$")) ids.push(id);
  }
  // A reflection's class answers, for their definitions.
  for (const question of operation.reflection?.questions ?? []) {
    for (const option of question.options) if (option.class_id) ids.push(option.class_id);
  }
  return ids;
}

export type ReplacementCheck = NonNullable<ProposedOperation["replacement_check"]>;
export type ReplacementEnd = ReplacementCheck["deleted_domain"];

/**
 * A replacement check's class end by the label the rest of the review uses
 * (`endLabel`), falling back to the title the server sent while the classes load.
 */
export function replacementEndLabel(
  end: ReplacementEnd,
  endLabel: (classId: string | null) => string,
): string {
  const id = end.id ?? null;
  const label = endLabel(id);
  return id !== null && label === id && end.title ? end.title : label;
}

export interface ReplacementFlag {
  pair: ReplacementCheck["pair"];
  /** A short label for the operation row. */
  chip: string;
  variant: ChipVariant;
  /** The full sentence, for the inspector and the chip's accessible name. */
  text: string;
  /** Whether a reviewer should look twice: a different pair, or a replacement that is gone. */
  warn: boolean;
}

/**
 * How a relationship-type delete's named replacement compares with the deleted
 * type: "Replacement links a different pair: A → C instead of A → B". `label`
 * names a class end (an id of null: untyped).
 */
export function replacementFlag(
  check: ReplacementCheck,
  label: (end: ReplacementEnd) => string,
): ReplacementFlag {
  const name = check.identifier ?? check.replacement_id;
  const pairOf = (domain: ReplacementEnd, range: ReplacementEnd) =>
    `${label(domain)} → ${label(range)}`;
  const deleted = pairOf(check.deleted_domain, check.deleted_range);
  const replacing = check.domain && check.range ? pairOf(check.domain, check.range) : deleted;
  switch (check.pair) {
    case "different":
      return {
        pair: check.pair,
        chip: "different pair",
        variant: "rose",
        text: `Replacement links a different pair: ${replacing} instead of ${deleted}. ${name} can't take over this type's relationships as they are.`,
        warn: true,
      };
    case "reversed":
      return {
        pair: check.pair,
        chip: "reversed pair",
        variant: "amber",
        text: `Replacement ${name} links the same pair reversed: ${replacing} instead of ${deleted}.`,
        warn: false,
      };
    case "missing":
      return {
        pair: check.pair,
        chip: "replacement gone",
        variant: "rose",
        text: `The named replacement ${name} no longer exists, or its create was rejected.`,
        warn: true,
      };
    default:
      return {
        pair: check.pair,
        chip: "same pair",
        variant: "emerald",
        text: `Replacement ${name} links the same pair: ${deleted}.`,
        warn: false,
      };
  }
}

export interface ReplacementDeletedFlag {
  /** "replacement deleted" or "replacement cycle", for the row chip. */
  chip: string;
  /** The full sentence, naming the chain or the cycle. */
  text: string;
}

/**
 * When the proposal also deletes a delete's named replacement: the chain of
 * replacements to the type it ends at, or the cycle ("A and B each name the
 * other; both are deleted"). Undefined when the replacement stays.
 */
export function replacementDeletedFlag(
  check: ReplacementCheck,
  deletedIdentifier: string,
): ReplacementDeletedFlag | undefined {
  const chain = check.chain ?? [];
  if (!check.replacement_deleted || chain.length === 0) return undefined;
  const name = (link: (typeof chain)[number]) => link.identifier ?? link.replacement_id;
  const step = (link: (typeof chain)[number]) =>
    link.deleted_by_seq != null
      ? `${name(link)} (deleted by seq ${link.deleted_by_seq})`
      : name(link);
  const first = chain[0];
  if (check.cycle) {
    const text =
      chain.length === 1
        ? `${deletedIdentifier} and ${name(first)} each name the other as replacement; both are deleted (seq ${first.deleted_by_seq}), so neither replaces the other.`
        : `The replacements loop: ${chain.map(step).join(" → ")} → back round; every type in it is deleted, so nothing replaces ${deletedIdentifier}.`;
    return { chip: "replacement cycle", text };
  }
  const last = chain[chain.length - 1];
  const ending =
    last.deleted_by_seq == null
      ? `the chain ends at ${name(last)}, which this proposal doesn't delete`
      : `the chain ends with no replacement (seq ${last.deleted_by_seq} names none)`;
  return {
    chip: "replacement deleted",
    text: `The replacement ${name(first)} is deleted too (seq ${first.deleted_by_seq}). Following each delete's replacement: ${chain.map(step).join(" → ")}; ${ending}.`,
  };
}

/** Ids of the existing property definitions that property operations touch. */
export function referencedPropertyIds(operations: ProposedOperation[]): string[] {
  return operations
    .filter((o) => o.kind === "property" && o.op !== "create" && o.target_id)
    .map((o) => o.target_id as string);
}

/** Ids an operation names that only a lookup can put a name to, by what they are. */
export interface NamedEntityIds {
  attributes: string[];
  individuals: string[];
  taxonomies: string[];
  /** Relationship types (property definitions) a relationship operation names. */
  properties: string[];
  /** The classes an attribute create or delete belongs to. */
  classes: string[];
  schemes: string[];
  /** Relationships an update or delete names only by id: their ends come from a lookup. */
  relationships: string[];
  /** Predicates an update names only by id, and the replacement a predicate delete names. */
  predicates: string[];
}

/**
 * The attributes, individuals, taxonomies and relationship types the
 * operations name by id: targets whose base carries no name (an update's base
 * holds only the fields it touches; a delete's is the whole entity), and a
 * relationship's ends and type.
 * "$ref" ids resolve to what an applied create made; unapplied ones are left out.
 */
export function namedEntityIds(
  operations: ProposedOperation[],
  refsOf: (operation: ProposedOperation) => RefMap | undefined = () => undefined,
): NamedEntityIds {
  const ids: NamedEntityIds = {
    attributes: [],
    individuals: [],
    taxonomies: [],
    properties: [],
    classes: [],
    schemes: [],
    relationships: [],
    predicates: [],
  };
  for (const operation of operations) {
    // A delete's base is the whole entity, name included: only a target whose
    // base lacks what names it is looked up (an attribute also needs its class).
    const base = operation.base ?? {};
    const unnamed =
      (!text(base.title) && !text(base.identifier)) ||
      (operation.kind === "attribute" && !text(base.class_id)) ||
      (operation.kind === "relationship" && !text(base.source_id));
    const target = operation.op !== "create" && unnamed ? operation.target_id : undefined;
    if (target && operation.kind === "attribute") ids.attributes.push(target);
    if (target && operation.kind === "individual") ids.individuals.push(target);
    if (target && operation.kind === "taxonomy") ids.taxonomies.push(target);
    if (target && operation.kind === "scheme") ids.schemes.push(target);
    if (target && operation.kind === "relationship") ids.relationships.push(target);
    if (target && operation.kind === "predicate") ids.predicates.push(target);
    const replacement = operation.proposed_replacement_id;
    if (operation.kind === "predicate" && replacement && !replacement.startsWith("$")) {
      ids.predicates.push(replacement);
    }
    const values = { ...operation.base, ...operation.fields };
    const owner = operation.kind === "attribute" ? text(values.class_id) : undefined;
    const ownerId = owner && resolveRef(owner, refsOf(operation));
    if (ownerId && !ownerId.startsWith("$")) ids.classes.push(ownerId);
    if (operation.kind !== "relationship") continue;
    for (const key of ["source_id", "target_id"]) {
      const value = text(values[key]);
      const id = value && resolveRef(value, refsOf(operation));
      if (id && !id.startsWith("$")) ids.individuals.push(id);
    }
    const property = text(values.property_definition_id);
    if (property) ids.properties.push(property);
  }
  return ids;
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
  // A DR node type's distinguish sits by its description: DR lands both as given.
  "distinguish",
  "inverse",
  "category",
  "archimate_alignment",
  "semantics",
  "standard",
  "cardinality",
  "strength",
  "evidence",
];

function fieldRank(field: string): number {
  const index = FIELD_ORDER.indexOf(field);
  return index === -1 ? FIELD_ORDER.length : index;
}

/** Rows for an individual's attribute values are this plus the attribute identifier. */
export const DATA_FIELD_PREFIX = "data_properties.";

/** A row's field as shown: an attribute value's row by its attribute identifier. */
export function fieldLabel(field: string): string {
  return field.startsWith(DATA_FIELD_PREFIX) ? field.slice(DATA_FIELD_PREFIX.length) : field;
}

/**
 * An individual's attribute values by identifier: an operation's
 * data_properties map, or an entity snapshot's list (a delete's base).
 */
export function dataValues(value: unknown): Record<string, unknown> {
  if (Array.isArray(value)) {
    return Object.fromEntries(
      value
        .filter((item) => item && typeof item === "object" && "property_identifier" in item)
        .map((item) => [String(item.property_identifier), item.value]),
    );
  }
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

/**
 * Field / before / after rows for an operation, from `fields` vs `base`.
 * A create has only after values, a delete only before values; an update
 * lists the fields it touches. An individual's attribute values get a row
 * each (DATA_FIELD_PREFIX + identifier).
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
  const value = (field: string, side: "before" | "after") =>
    side === "before"
      ? operation.op === "create"
        ? undefined
        : base[field]
      : operation.op === "delete"
        ? undefined
        : fields[field];
  const rows = names
    .filter((field) => !HIDDEN_FIELDS.has(field))
    .map((field) => {
      const before = value(field, "before");
      const after = value(field, "after");
      return { field, before, after, changed: !sameValue(before, after) };
    });
  const data = rows.find((row) => row.field === "data_properties");
  if (operation.kind === "individual" && data) {
    rows.splice(rows.indexOf(data), 1);
    const before = dataValues(data.before);
    const after = dataValues(data.after);
    for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) {
      rows.push({
        field: `${DATA_FIELD_PREFIX}${key}`,
        before: before[key],
        after: after[key],
        changed: !sameValue(before[key], after[key]),
      });
    }
  }
  const references = rows.find((row) => row.field === "external_references");
  const drFields = DR_FIELDS[operation.kind];
  if (drFields && references) {
    // References read by identifier; the DR fields on a DR reference get rows of their own.
    references.changed = !sameValue(
      withoutDrFields(references.before, drFields),
      withoutDrFields(references.after, drFields),
    );
    const before = drMetadata(references.before, drFields);
    const after = drMetadata(references.after, drFields);
    for (const field of drFields) {
      if (!(field in before) && !(field in after)) continue;
      rows.push({
        field,
        before: before[field],
        after: after[field],
        changed: !sameValue(before[field], after[field]),
      });
    }
  }
  return rows
    .sort((a, b) => fieldRank(a.field) - fieldRank(b.field) || a.field.localeCompare(b.field))
    .filter((row) => !isEmpty(row.before) || !isEmpty(row.after));
}

/** A DR relationship type's spec attributes, kept on its DR reference's metadata. */
export const DR_ATTRIBUTES = ["cardinality", "strength", "evidence"] as const;
/** A DR predicate's catalog fields, kept on its DR reference's metadata (#1481). */
export const DR_PREDICATE_FIELDS = [
  "inverse",
  "category",
  "archimate_alignment",
  "semantics",
] as const;
/** A DR node type's x-dr fields, kept on its class's DR reference's metadata (#1481). */
export const DR_NODE_FIELDS = ["distinguish", "standard", "evidence"] as const;

/** Per kind, the DR fields that get rows of their own. */
const DR_FIELDS: Record<string, readonly string[]> = {
  property: DR_ATTRIBUTES,
  predicate: DR_PREDICATE_FIELDS,
  class: DR_NODE_FIELDS,
};

/**
 * References compared by full value (source, identifier, uri, metadata), less
 * the DR fields, which have rows of their own; key order doesn't count.
 */
function withoutDrFields(references: unknown, drFields: readonly string[]): unknown {
  if (!Array.isArray(references)) return references;
  return references.map((r) => {
    if (!r || typeof r !== "object") return r;
    const { source, identifier, uri, metadata } = r as Record<string, unknown>;
    const rest = Object.entries((metadata ?? {}) as Record<string, unknown>)
      .filter(([key]) => !drFields.includes(key))
      .sort(([a], [b]) => a.localeCompare(b));
    return {
      source,
      identifier,
      uri: uri ?? null,
      metadata: rest.length ? Object.fromEntries(rest) : null,
    };
  });
}

/** The DR fields on the DR ("documentation_robotics") reference among references. */
function drMetadata(references: unknown, drFields: readonly string[]): Record<string, unknown> {
  if (!Array.isArray(references)) return {};
  const ref = references.find(
    (r) =>
      r && typeof r === "object" && (r as { source?: unknown }).source === "documentation_robotics",
  ) as { metadata?: Record<string, unknown> | null } | undefined;
  const metadata = ref?.metadata ?? {};
  return Object.fromEntries(drFields.filter((k) => k in metadata).map((k) => [k, metadata[k]]));
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
export const CLASS_ID_FIELDS = new Set([
  "domain_class_id",
  "range_class_id",
  "parent_class_id",
  "class_id",
]);

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
