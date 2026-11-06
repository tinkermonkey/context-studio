/**
 * Deciding a change proposal, worked out in the browser: the probability
 * threshold, stale causes, relationship-type deletes blocked by relationships
 * still using the type, a DR triple edit (checked as it is typed, and the
 * `edits` entry and decision line it makes), apply outcomes and what a revert
 * undoes. Read-only views live in proposalModel.
 */
import { ApiError } from "@/api/client/interceptors";
import type {
  ChangeProposal,
  ChangeProposalRevertConflict,
  DrDecision,
  ProposedOperation,
} from "@/api/services/proposals";
import type { components } from "@/api/types";
import { isAwaiting, propertyTriples, type ChipVariant, type TripleSource } from "./proposalModel";

export type DeleteBlockers = components["schemas"]["DeleteBlockersResponse"];
export type BlockingEdge = components["schemas"]["BlockingEdgeResponse"];
export type ReplacementType = components["schemas"]["ReplacementTypeResponse"];
export type Resolution = components["schemas"]["InUseResolutionRequest"];
export type Resolutions = Record<string, Resolution>;

// ==================== Who can decide ====================

/** A proposal takes decisions until it is reverted. */
export function takesDecisions(proposal: ChangeProposal): boolean {
  return proposal.status !== "reverted";
}

/** Awaiting operations among `ids`, split into those that apply and those needing Apply anyway. */
export function splitStale(
  operations: ProposedOperation[],
  ids: Iterable<string>,
): { fresh: string[]; stale: string[] } {
  const wanted = new Set(ids);
  const chosen = operations.filter((o) => wanted.has(o.id) && isAwaiting(o));
  return {
    fresh: chosen.filter((o) => !o.stale).map((o) => o.id),
    stale: chosen.filter((o) => o.stale).map((o) => o.id),
  };
}

// ==================== Probability threshold ====================

export const DEFAULT_THRESHOLD = 0.6;

export function hasProbabilities(operations: ProposedOperation[]): boolean {
  return operations.some((o) => typeof o.probability === "number");
}

/** Slider steps are 0.05; compare with a little slack so 0.6 counts as at 0.60. */
const EPSILON = 1e-9;

/** True when the operation has a probability below the threshold (muted in the table). */
export function isBelowThreshold(operation: ProposedOperation, threshold: number): boolean {
  return typeof operation.probability === "number" && operation.probability < threshold - EPSILON;
}

/**
 * The operations "Select N" picks: awaiting, not stale, not blocked, with a
 * probability at or above the threshold. Stale ones are never picked (they need
 * Apply anyway), nor blocked deletes (they need a resolution in the inspector).
 */
export function atOrAboveThreshold(
  operations: ProposedOperation[],
  threshold: number,
): ProposedOperation[] {
  return operations.filter(
    (o) =>
      isAwaiting(o) &&
      !o.stale &&
      !isBlocked(o) &&
      typeof o.probability === "number" &&
      !isBelowThreshold(o, threshold),
  );
}

// ==================== Stale operations ====================

/** Why a stale operation needs Apply anyway, as far as the browser can tell. */
export interface StaleCause {
  /** The target is gone; applying fails with target_missing even when forced. */
  gone: boolean;
  /** Fields that changed since proposed; empty when unknown. */
  fields: string[];
}

/** Bookkeeping that changes on every write; the server ignores it for staleness. */
const VOLATILE = new Set(["id", "created_at", "last_modified", "version"]);

function sameJson(a: unknown, b: unknown): boolean {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

/**
 * A stale operation's cause: from its failure reason when an apply already
 * said ("target_changed: a, b changed since proposed", "target_missing: …"),
 * else by comparing its base with the current target (`current`, when loaded;
 * `targetGone` when it is known not to exist).
 */
export function staleCause(
  operation: ProposedOperation,
  current?: Record<string, unknown>,
  targetGone = false,
): StaleCause {
  const reason = operation.reason ?? "";
  if (reason.startsWith("target_missing")) return { gone: true, fields: [] };
  const changed = /^target_changed: (.+) changed since proposed/.exec(reason);
  if (changed) return { gone: false, fields: changed[1].split(", ") };
  if (current) {
    const base = operation.base ?? {};
    const fields = Object.keys(base)
      .filter((name) => !VOLATILE.has(name) && name in current)
      .filter((name) => !sameJson(current[name], base[name]))
      .sort();
    return { gone: false, fields };
  }
  return { gone: targetGone, fields: [] };
}

/** "description changed since it was proposed." / "Its target is gone, …" */
export function staleCauseText(cause: StaleCause): string {
  if (cause.gone) return "Its target is gone, so applying it fails even with Apply anyway.";
  if (cause.fields.length > 0) return `${cause.fields.join(", ")} changed since it was proposed.`;
  return "Its target changed after it was proposed.";
}

// ==================== Blocked relationship-type deletes ====================

/** An awaiting relationship-type delete's blockers: the relationships still using the type. */
export function blockersOf(operation: ProposedOperation): DeleteBlockers | undefined {
  const blockers = operation.blockers;
  return isAwaiting(operation) && blockers && blockers.edges.length > 0 ? blockers : undefined;
}

export function isBlocked(operation: ProposedOperation): boolean {
  return !!blockersOf(operation);
}

/**
 * Awaiting operations among `ids`, split into those a bulk accept sends and
 * the blocked deletes it skips: those need a resolution, chosen in the inspector.
 */
export function splitBlocked(
  operations: ProposedOperation[],
  ids: Iterable<string>,
): { unblocked: string[]; blocked: string[] } {
  const wanted = new Set(ids);
  const chosen = operations.filter((o) => wanted.has(o.id) && isAwaiting(o));
  return {
    unblocked: chosen.filter((o) => !isBlocked(o)).map((o) => o.id),
    blocked: chosen.filter(isBlocked).map((o) => o.id),
  };
}

export function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

/** "Entity Changed Event (BusinessEvent)" */
export function edgeEndLabel(end: BlockingEdge["source"]): string {
  const classes = end.class_titles ?? [];
  return classes.length > 0 ? `${end.title} (${classes.join(", ")})` : end.title;
}

/** The resolve button names its scope: what it moves or deletes, then the type. */
export function resolutionLabel(
  blockers: DeleteBlockers,
  strategy: Resolution["strategy"],
  replacementIdentifier?: string,
): string {
  const edges = plural(blockers.edges.length, "relationship");
  return strategy === "move"
    ? `Apply: move ${edges} to ${replacementIdentifier ?? "another type"} and delete the type`
    : `Apply: delete ${edges} and the type`;
}

/** A move target in the picker: "(proposed)" and "(reversed: ends swap)" as they apply. */
export function replacementLabel(replacement: ReplacementType, proposed: boolean): string {
  const notes = [proposed && "proposed", replacement.reversed && "reversed: ends swap"].filter(
    Boolean,
  );
  return notes.length > 0
    ? `${replacement.identifier} (${notes.join(", ")})`
    : replacement.identifier;
}

/** What an applied resolution did, or undefined for an operation without one. */
export function resolutionResult(operation: ProposedOperation): string | undefined {
  const resolution = operation.resolution;
  if (operation.status !== "applied" || !resolution) return undefined;
  const edges = plural(resolution.edges?.length ?? 0, "relationship");
  const replacement = resolution.replacement_identifier ?? resolution.replacement_property_id;
  const swapped = resolution.reversed ? " with their ends swapped" : "";
  return resolution.strategy === "move"
    ? `moved ${edges} to ${replacement}${swapped}, removed the type`
    : `deleted ${edges} and the type`;
}

// ==================== Decision state (colour means you have something to decide) ====================

/**
 * Where an operation stands for the reviewer. Amber: it needs a decision or a
 * choice; rose: it failed; once decided it is applied (emerald) or rejected.
 */
export type DecisionState =
  | "needs_decision"
  | "needs_choice"
  | "failed"
  | "applied"
  | "applied_with_edits"
  | "rejected";

export interface DecisionStateView {
  state: DecisionState;
  label: string;
  variant: ChipVariant;
}

/** The one status chip an operation row shows, from its status, blockers and edit. */
export function decisionState(operation: ProposedOperation): DecisionStateView {
  if (isBlocked(operation)) {
    return { state: "needs_choice", label: "needs a choice", variant: "amber" };
  }
  switch (operation.status) {
    case "pending":
      return { state: "needs_decision", label: "needs decision", variant: "amber" };
    case "failed":
      return { state: "failed", label: "failed", variant: "rose" };
    case "applied":
      return operation.applied_fields
        ? { state: "applied_with_edits", label: "applied with edits", variant: "emerald" }
        : { state: "applied", label: "applied", variant: "emerald" };
    default:
      return { state: "rejected", label: "rejected", variant: "neutral" };
  }
}

/** A flag's colour while the operation awaits a decision; neutral (a record) once decided. */
export function flagVariant(operation: ProposedOperation, variant: ChipVariant): ChipVariant {
  return isAwaiting(operation) ? variant : "neutral";
}

/** "moved 2 relationships" / "dropped 1 relationship": a decided delete's resolution, for its row. */
export function resolutionChip(operation: ProposedOperation): string | undefined {
  const resolution = operation.resolution;
  if (isAwaiting(operation) || !resolution) return undefined;
  const verb = resolution.strategy === "move" ? "moved" : "dropped";
  const count = resolution.edges?.length;
  return count ? `${verb} ${plural(count, "relationship")}` : `${verb} relationships`;
}

const PAIR_RECORD: Partial<Record<string, string>> = {
  reversed: "The replacement linked the pair reversed",
  different: "The replacement linked a different pair",
  missing: "The named replacement was gone",
};

/**
 * One line on what a decided operation did beyond its change: how its
 * replacement's pair compared and what happened to the relationships using the
 * type ("The replacement linked the pair reversed; 2 relationships moved to x
 * with their ends swapped."). Undefined when there is nothing to add.
 */
export function decidedRecord(operation: ProposedOperation): string | undefined {
  if (isAwaiting(operation)) return undefined;
  const parts: string[] = [];
  const pair = PAIR_RECORD[operation.replacement_check?.pair ?? ""];
  if (pair) parts.push(pair);
  const resolution = operation.status === "applied" ? operation.resolution : undefined;
  if (resolution) {
    const count = resolution.edges?.length;
    const edges = count ? plural(count, "relationship") : "relationships";
    const replacement = resolution.replacement_identifier;
    const swapped = resolution.reversed ? " with their ends swapped" : "";
    parts.push(
      resolution.strategy === "move"
        ? `${edges} moved${replacement ? ` to ${replacement}` : ""}${swapped}`
        : `${edges} deleted with the type`,
    );
  }
  if (operation.status === "applied" && operation.applied_fields) {
    parts.push("applied with a reviewer's edit");
  }
  if (parts.length === 0) return undefined;
  const text = parts.join("; ");
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.`;
}

/** "by you · Nov 6, 12:53" from a recorded decision; undefined when none was recorded. */
export function decidedByLabel(
  decidedBy: string | null | undefined,
  decidedAt: string | null | undefined,
  timeZone?: string,
): string | undefined {
  const parts: string[] = [];
  if (decidedBy && decidedBy !== "unknown") {
    parts.push(`by ${decidedBy === "user" ? "you" : decidedBy}`);
  }
  const at = decidedAt ? new Date(decidedAt) : undefined;
  if (at && !Number.isNaN(at.getTime())) {
    const date = new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      timeZone,
    }).format(at);
    const time = new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
      timeZone,
    }).format(at);
    parts.push(`${date}, ${time}`);
  }
  return parts.length > 0 ? parts.join(" · ") : undefined;
}

// ==================== Decision progress (the summary banner) ====================

export interface DecisionProgress {
  total: number;
  /** Still needing a decision: pending or failed. */
  awaiting: number;
  applied: number;
  rejected: number;
  /** Pending, not blocked, not stale: accept or reject. */
  toDecide: number;
  /** Blocked deletes (pending or failed): move or drop the relationships using the type. */
  needChoice: number;
  /** Failed, not blocked: apply again or reject. */
  failed: number;
  /** Pending and stale, not blocked: Apply anyway or reject. */
  stale: number;
  /** What "Accept N ready" sends: awaiting, not stale, not blocked. */
  ready: number;
  /** Share decided (applied or rejected), 0 to 100. */
  percent: number;
}

/** The banner's counts; toDecide + needChoice + failed + stale = awaiting. */
export function decisionProgress(operations: ProposedOperation[]): DecisionProgress {
  const awaiting = operations.filter(isAwaiting);
  const unblocked = awaiting.filter((o) => !isBlocked(o));
  const total = operations.length;
  return {
    total,
    awaiting: awaiting.length,
    applied: operations.filter((o) => o.status === "applied").length,
    rejected: operations.filter((o) => o.status === "rejected").length,
    toDecide: unblocked.filter((o) => o.status === "pending" && !o.stale).length,
    needChoice: awaiting.length - unblocked.length,
    failed: unblocked.filter((o) => o.status === "failed").length,
    stale: unblocked.filter((o) => o.status === "pending" && o.stale).length,
    ready: unblocked.filter((o) => !o.stale).length,
    percent: total === 0 ? 100 : Math.round(((total - awaiting.length) / total) * 100),
  };
}

/** "3 of 79 need a decision", or "All 79 decided". */
export function decisionHeadline(progress: DecisionProgress): string {
  return progress.awaiting > 0
    ? `${progress.awaiting} of ${progress.total} need a decision`
    : `All ${progress.total} decided`;
}

export interface ProgressPill {
  key: "to-decide" | "need-choice" | "failed" | "stale";
  count: number;
  label: string;
  variant: "amber" | "rose";
}

/** The banner's breakdown of what needs a decision, each only when non-zero. */
export function progressPills(progress: DecisionProgress): ProgressPill[] {
  const pills: ProgressPill[] = [
    {
      key: "to-decide",
      count: progress.toDecide,
      label: `${progress.toDecide} to accept or reject`,
      variant: "amber",
    },
    {
      key: "need-choice",
      count: progress.needChoice,
      label: `${progress.needChoice} need an in-use choice`,
      variant: "amber",
    },
    {
      key: "failed",
      count: progress.failed,
      label: `${progress.failed} failed: retry or reject`,
      variant: "rose",
    },
    {
      key: "stale",
      count: progress.stale,
      label: `${progress.stale} stale: apply anyway or reject`,
      variant: "rose",
    },
  ];
  return pills.filter((pill) => pill.count > 0);
}

// ==================== Table filter ====================

export type OperationFilter = "needs" | "decided" | "all";

/**
 * "Needs decision" while anything awaits, else "All". A deep link to a decided
 * operation opens on "All", so its row is in the table.
 */
export function defaultOperationFilter(
  progress: DecisionProgress,
  linked?: ProposedOperation,
): OperationFilter {
  if (linked && !isAwaiting(linked)) return "all";
  return progress.awaiting > 0 ? "needs" : "all";
}

export function filterOperations(
  operations: ProposedOperation[],
  filter: OperationFilter,
): ProposedOperation[] {
  if (filter === "all") return operations;
  return operations.filter((o) => isAwaiting(o) === (filter === "needs"));
}

// ==================== DR triple edits (accept with edit) ====================

export const DR_SOURCE = "documentation_robotics";
export const DR_TAXONOMY_IDENTIFIER = "dr_spec";
const DR_SPEC_REFERENCE = "spec";

/** A DR relationship's triple by spec node ids: business.businessrole performs business.businessprocess. */
export interface DrTriple {
  source: string;
  predicate: string;
  destination: string;
}

/** What checking an edited DR triple needs: dr_spec's classes and predicate catalog. */
export interface DrSpec {
  /** Spec node id (e.g. "business.businessrole") -> class id. */
  classIdByNode: Map<string, string>;
  nodeByClassId: Map<string, string>;
  /** The predicate catalog; undefined when the import stored none (no edit can apply then). */
  predicates?: Set<string>;
}

interface ExternalRef {
  source: string;
  identifier: string;
  metadata?: Record<string, unknown> | null;
}

/** The DR id among external references (spec node id of a class, relationship id of a property). */
export function drIdentifier(refs: unknown): string | undefined {
  if (!Array.isArray(refs)) return undefined;
  const ref = (refs as ExternalRef[]).find(
    (r) => r && r.source === DR_SOURCE && typeof r.identifier === "string",
  );
  return ref?.identifier;
}

/** dr_spec's predicate catalog, kept on its DR "spec" reference at import. */
export function drPredicateCatalog(taxonomy?: {
  external_references?: ExternalRef[] | null;
}): Set<string> | undefined {
  const spec = (taxonomy?.external_references ?? []).find(
    (r) => r.source === DR_SOURCE && r.identifier === DR_SPEC_REFERENCE,
  );
  const predicates = spec?.metadata?.predicates;
  return predicates && typeof predicates === "object" && Object.keys(predicates).length > 0
    ? new Set(Object.keys(predicates))
    : undefined;
}

export function drSpecOf(
  classes: { id: string; external_references?: ExternalRef[] | null }[],
  predicates?: Set<string>,
): DrSpec {
  const classIdByNode = new Map<string, string>();
  const nodeByClassId = new Map<string, string>();
  for (const cls of classes) {
    const node = drIdentifier(cls.external_references);
    if (!node) continue;
    classIdByNode.set(node, cls.id);
    nodeByClassId.set(cls.id, node);
  }
  return { classIdByNode, nodeByClassId, predicates };
}

/** "business.businessrole.performs.business.businessprocess" */
export function drTripleId(triple: DrTriple): string {
  return `${triple.source}.${triple.predicate}.${triple.destination}`;
}

/** Parse a DR relationship id into its triple (spec node ids have one dot). */
export function parseDrTripleId(id: string): DrTriple | undefined {
  const parts = id.split(".");
  if (parts.length !== 5 || parts.some((p) => !p)) return undefined;
  return {
    source: `${parts[0]}.${parts[1]}`,
    predicate: parts[2],
    destination: `${parts[3]}.${parts[4]}`,
  };
}

export function sameDrTriple(a?: DrTriple, b?: DrTriple): boolean {
  return (
    !!a &&
    !!b &&
    a.source === b.source &&
    a.predicate === b.predicate &&
    a.destination === b.destination
  );
}

/** True for a property update or delete on dr_spec: the reviewer can edit its triple. */
export function isDrEditable(
  operation: ProposedOperation,
  taxonomyIdentifier: string | undefined,
): boolean {
  return (
    taxonomyIdentifier === DR_TAXONOMY_IDENTIFIER &&
    operation.kind === "property" &&
    (operation.op === "update" || operation.op === "delete") &&
    !!operation.target_id
  );
}

/**
 * An operation's current and proposed triples by spec node id. The current one
 * is the target's (or a delete's base); the proposed one an update's result.
 */
export function drTriplesOf(
  operation: ProposedOperation,
  spec: DrSpec,
  current?: TripleSource,
): { current?: DrTriple; proposed?: DrTriple } {
  const { before, after } = propertyTriples(operation, current);
  const toDr = (t?: typeof before): DrTriple | undefined => {
    if (!t?.predicate || !t.domain || !t.range) return undefined;
    const source = spec.nodeByClassId.get(t.domain);
    const destination = spec.nodeByClassId.get(t.range);
    return source && destination ? { source, predicate: t.predicate, destination } : undefined;
  };
  return { current: toDr(before), proposed: toDr(after) };
}

/** A property definition as far as the "already exists" check reads it. */
export interface ExistingProperty {
  id: string;
  identifier: string;
  canonical_predicate?: string | null;
  domain_class_id?: string | null;
  range_class_id?: string | null;
}

export const NO_CATALOG =
  "The DR spec was imported without its predicate catalog; re-import it to edit triples.";

export interface TripleErrors {
  source?: string;
  predicate?: string;
  destination?: string;
  /** About the triple as a whole: it already exists, or another operation makes it. */
  triple?: string;
  /** No predicate catalog: the server refuses every edit until the DR spec is re-imported. */
  catalog?: string;
}

export function hasTripleErrors(errors: TripleErrors): boolean {
  return !!(
    errors.source ||
    errors.predicate ||
    errors.destination ||
    errors.triple ||
    errors.catalog
  );
}

/**
 * Check an edited triple the way DrRelationshipRules will: both ends are
 * imported dr_spec classes, the predicate is in the catalog, no other
 * relationship type has the triple, and no other open operation of the
 * proposal makes it. The server checks again on apply.
 *
 * Args:
 *   existing: Property definitions whose domain is the edited source class
 *   operation: The operation being edited (its target may keep its own triple)
 *   others: The proposal's other operations
 *   current: The target's current triple; a replaced delete must change it
 */
export function checkDrTriple(
  triple: DrTriple,
  spec: DrSpec,
  context: {
    existing?: ExistingProperty[];
    operation: ProposedOperation;
    others: ProposedOperation[];
    current?: DrTriple;
    /** An update's proposed triple: editing back to it applies as proposed. */
    proposed?: DrTriple;
  },
): TripleErrors {
  const errors: TripleErrors = {};
  if (!spec.predicates) errors.catalog = NO_CATALOG;
  const end = (node: string) =>
    !node ? "Required" : spec.classIdByNode.has(node) ? undefined : `No class ${node} in dr_spec`;
  errors.source = end(triple.source);
  errors.destination = end(triple.destination);
  if (!triple.predicate) errors.predicate = "Required";
  else if (/[.\s]/.test(triple.predicate))
    errors.predicate = `${triple.predicate} is not a DR predicate`;
  else if (spec.predicates && !spec.predicates.has(triple.predicate)) {
    errors.predicate = `${triple.predicate} is not in the predicate catalog`;
  }
  if (errors.source || errors.destination || errors.predicate) return errors;

  const id = drTripleId(triple);
  const { operation } = context;
  if (sameDrTriple(triple, context.current) && !sameDrTriple(triple, context.proposed)) {
    errors.triple = `${id} is the current triple. To keep it, reject the ${operation.op}.`;
    return errors;
  }
  const domain = spec.classIdByNode.get(triple.source);
  const range = spec.classIdByNode.get(triple.destination);
  const holder = (context.existing ?? []).find(
    (p) =>
      p.id !== operation.target_id &&
      p.canonical_predicate === triple.predicate &&
      p.domain_class_id === domain &&
      p.range_class_id === range,
  );
  if (holder) {
    errors.triple = `${id} already exists as ${holder.identifier}. Reject this operation instead, or pick another triple.`;
    return errors;
  }
  const producer = context.others.find((o) => {
    if (o.id === operation.id || !isAwaiting(o)) return false;
    const made = parseDrTripleId(drIdentifier(o.fields?.external_references) ?? "");
    return sameDrTriple(made, triple);
  });
  if (producer) errors.triple = `seq ${producer.seq} also produces ${id}.`;
  return errors;
}

/** The `edits[op_id]` entry for an edited triple, in Context Studio fields. */
export function drEditFields(triple: DrTriple, spec: DrSpec): Record<string, unknown> {
  return {
    canonical_predicate: triple.predicate,
    domain_class_id: spec.classIdByNode.get(triple.source),
    range_class_id: spec.classIdByNode.get(triple.destination),
  };
}

/** What DR's decisions file will say for the operation once applied (with the edit, if any). */
export function decisionPreview(
  operation: ProposedOperation,
  edited?: DrTriple,
): Omit<DrDecision, "result_entity_id"> {
  return {
    seq: operation.seq,
    op_id: operation.id,
    status: "applied",
    ...(edited
      ? {
          fields: {
            predicate: edited.predicate,
            source_spec_node_id: edited.source,
            destination_spec_node_id: edited.destination,
          },
        }
      : {}),
    reason: null,
  };
}

// ==================== Apply outcomes ====================

export interface OutcomeRow {
  operation: ProposedOperation;
  /** A reviewer's edit was applied (applied_fields set). */
  edited: boolean;
  /** A blocked delete was applied with its relationships moved or deleted (resolution set). */
  resolved: boolean;
  /** "<code>: <detail>" on a failure, else what it made or changed. */
  result: string;
}

/** The outcome of each operation an apply sent, in seq order, as they stand now. */
export function outcomeRows(proposal: ChangeProposal, operationIds: string[]): OutcomeRow[] {
  const sent = new Set(operationIds);
  return proposal.operations
    .filter((o) => sent.has(o.id))
    .map((operation) => {
      const edited = operation.status === "applied" && !!operation.applied_fields;
      const appliedIdentifier =
        operation.applied_fields?.identifier ?? operation.fields?.identifier;
      const resolved = resolutionResult(operation);
      let result: string;
      if (resolved) {
        result = resolved;
      } else if (operation.status === "failed" || operation.status === "rejected") {
        result = operation.reason ?? operation.status;
      } else if (operation.status === "applied") {
        result =
          operation.op === "delete" && !edited
            ? "removed"
            : typeof appliedIdentifier === "string"
              ? appliedIdentifier
              : (operation.result_entity_id ?? "applied");
      } else {
        result = "not applied";
      }
      return { operation, edited, resolved: !!resolved, result };
    });
}

// ==================== Revert ====================

export interface RevertSummary {
  applied: number;
  created: number;
  updated: number;
  deleted: number;
  edited: number;
  /** Relationships applied deletes moved or deleted with their type: restored on it. */
  relationships: number;
  /** Pending or failed: rejected by the revert. */
  open: number;
}

/** What reverting the proposal undoes. */
export function revertSummary(proposal: ChangeProposal): RevertSummary {
  const applied = proposal.operations.filter((o) => o.status === "applied");
  const count = (test: (o: ProposedOperation) => boolean) => applied.filter(test).length;
  const edited = (o: ProposedOperation) => !!o.applied_fields;
  return {
    applied: applied.length,
    created: count((o) => o.op === "create"),
    // An edited delete applied as an update.
    updated: count((o) => o.op === "update" || o.op === "move" || (o.op === "delete" && edited(o))),
    deleted: count((o) => o.op === "delete" && !edited(o)),
    edited: count(edited),
    relationships: applied.reduce((sum, o) => sum + (o.resolution?.edges?.length ?? 0), 0),
    open: proposal.operations.filter(isAwaiting).length,
  };
}

/** The blocked-revert explanation in a 409, or undefined for any other error. */
export function revertConflictOf(error: unknown): ChangeProposalRevertConflict | undefined {
  if (!(error instanceof ApiError) || error.status !== 409) return undefined;
  const body = error.body as Partial<ChangeProposalRevertConflict> | undefined;
  return {
    message: typeof body?.message === "string" ? body.message : error.detail,
    blocking: Array.isArray(body?.blocking) ? body.blocking : [],
  };
}
