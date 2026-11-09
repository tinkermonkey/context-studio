/**
 * Tiered apply, worked out in the browser: a reflection proposal's operations
 * grouped by change kind. Mechanical kinds are accepted by a probability
 * threshold; judgment kinds and conflicts are decided one by one and never
 * bulk-selected. A reviewer can pick other reflection answers than the plan's:
 * those become an accept-with-edit and the chosen alternative recorded in gold.
 */
import type { ProposedOperation } from "@/api/services/proposals";
import { atOrAboveThreshold } from "./decisionModel";
import { isAwaiting, planKind } from "./proposalModel";

export type Reflection = NonNullable<ProposedOperation["reflection"]>;
export type ReflectionOption = Reflection["questions"][number]["options"][number];

export const MECHANICAL_KINDS = ["remove-duplicate", "rename-predicate", "reverse"] as const;
export const JUDGMENT_KINDS = ["retarget", "compound"] as const;
export const CONFLICT_KIND = "conflict";

const MECHANICAL = new Set<string>(MECHANICAL_KINDS);
const NEVER_BULK = new Set<string>([...JUDGMENT_KINDS, CONFLICT_KIND]);

export type GroupBy = "kind" | "sequence";

/** The change plan's kind: the reflection's, else the "Plan kind x" a rationale names. */
export function kindOf(operation: ProposedOperation): string | undefined {
  return operation.reflection?.plan_kind ?? planKind(operation);
}

export function isMechanical(operation: ProposedOperation): boolean {
  return MECHANICAL.has(kindOf(operation) ?? "");
}

/**
 * True unless the operation is a judgment or conflict row, or sits in a
 * conflict card (`conflicted`, see conflictedIds): those are decided one by
 * one, never by a threshold, a checkbox or "Accept N ready".
 */
export function isBulkEligible(
  operation: ProposedOperation,
  conflicted: ReadonlySet<string> = new Set(),
): boolean {
  return !NEVER_BULK.has(kindOf(operation) ?? "") && !conflicted.has(operation.id);
}

/** The operations conflict cards show. */
export function conflictedIds(operations: ProposedOperation[]): Set<string> {
  return new Set(conflictClusters(operations).flatMap((c) => c.operations.map((o) => o.id)));
}

/** Group by is offered when some operation carries a plan kind. */
export function offersGroupBy(operations: ProposedOperation[]): boolean {
  return operations.some((o) => kindOf(o) !== undefined);
}

/** Change kind when the operations carry reflection data, else the flat sequence. */
export function defaultGroupBy(operations: ProposedOperation[]): GroupBy {
  return operations.some((o) => o.reflection) ? "kind" : "sequence";
}

/** The mechanical, awaiting, non-stale, non-blocked operations at or above the threshold. */
export function mechanicalAtOrAbove(
  operations: ProposedOperation[],
  threshold: number,
  conflicted: ReadonlySet<string> = new Set(),
): ProposedOperation[] {
  return atOrAboveThreshold(
    operations.filter((o) => isMechanical(o) && !conflicted.has(o.id)),
    threshold,
  );
}

// ==================== Groups ====================

export interface KindGroup {
  kind: string;
  operations: ProposedOperation[];
}

/** The non-empty groups of `kinds`, in that order, each in seq order. */
export function kindGroups(operations: ProposedOperation[], kinds: readonly string[]): KindGroup[] {
  return kinds
    .map((kind) => ({ kind, operations: operations.filter((o) => kindOf(o) === kind) }))
    .filter((group) => group.operations.length > 0);
}

/** "p 0.62–0.95", "p 0.80" for one value, "p —" without any. */
export function pRangeLabel(operations: ProposedOperation[]): string {
  const ps = operations.map((o) => o.probability).filter((p): p is number => typeof p === "number");
  if (ps.length === 0) return "p —";
  const low = Math.min(...ps).toFixed(2);
  const high = Math.max(...ps).toFixed(2);
  return low === high ? `p ${low}` : `p ${low}–${high}`;
}

// ==================== Sections ====================

/** What the change-kind view shows, section by section, in display order. */
export interface TieredSections {
  mechanical: KindGroup[];
  judgment: KindGroup[];
  /** Conflict cards with a shown member; a card lists all its members. */
  clusters: ConflictCluster[];
  other: ProposedOperation[];
}

/**
 * The change-kind sections for the shown `operations`. Conflicts are worked
 * out over `allOperations`, so a card keeps every member while any is shown.
 */
export function tieredSections(
  operations: ProposedOperation[],
  allOperations: ProposedOperation[],
): TieredSections {
  const shown = new Set(operations.map((o) => o.id));
  const allClusters = conflictClusters(allOperations);
  const clustered = new Set(allClusters.flatMap((c) => c.operations.map((o) => o.id)));
  const rest = operations.filter((o) => !clustered.has(o.id));
  const known = new Set<string>([...MECHANICAL_KINDS, ...JUDGMENT_KINDS]);
  return {
    mechanical: kindGroups(rest, MECHANICAL_KINDS),
    judgment: kindGroups(rest, JUDGMENT_KINDS),
    clusters: allClusters.filter((c) => c.operations.some((o) => shown.has(o.id))),
    other: rest.filter((o) => !known.has(kindOf(o) ?? "")),
  };
}

/** The operation ids the change-kind view shows, top to bottom. */
export function tieredOrder(
  operations: ProposedOperation[],
  allOperations: ProposedOperation[],
): string[] {
  const { mechanical, judgment, clusters, other } = tieredSections(operations, allOperations);
  return [
    ...mechanical.flatMap((g) => g.operations),
    ...judgment.flatMap((g) => g.operations),
    ...clusters.flatMap((c) => c.operations),
    ...other,
  ].map((o) => o.id);
}

// ==================== Conflicts ====================

export interface ConflictCluster {
  /** The lowest seq's operation id. */
  id: string;
  operations: ProposedOperation[];
}

function tripleText(triple: { source: string; predicate: string; target: string }): string {
  return `${triple.source} ${triple.predicate} ${triple.target}`;
}

/** What identifies the type an operation changes: its target and current triple. */
function keysOf(operation: ProposedOperation): string[] {
  const current = operation.reflection?.current;
  return [operation.target_id, current ? tripleText(current) : undefined].filter(
    (k): k is string => !!k,
  );
}

/** The triple an operation's change makes (the plan's replacement). */
function linksOf(operation: ProposedOperation): string[] {
  const replacement = operation.reflection?.replacement;
  return replacement ? [replacement] : [];
}

/**
 * Conflict operations with the operations they contradict (the reflection
 * pipeline's rule): two operations are linked when they change the same type,
 * or one's replacement triple is the current triple of a type the other
 * changes. A delete that merely names another operation's type as its
 * replacement depends on it, but doesn't contradict it. Each cluster holds at
 * least one conflict-kind operation. Clusters and their operations are in seq
 * order.
 */
export function conflictClusters(operations: ProposedOperation[]): ConflictCluster[] {
  const parent = new Map(operations.map((o) => [o.id, o.id]));
  const find = (id: string): string => {
    const up = parent.get(id)!;
    if (up === id) return id;
    const root = find(up);
    parent.set(id, root);
    return root;
  };
  const owners = new Map<string, string[]>();
  for (const o of operations) {
    for (const key of keysOf(o)) owners.set(key, [...(owners.get(key) ?? []), o.id]);
  }
  for (const o of operations) {
    for (const key of [...keysOf(o), ...linksOf(o)]) {
      for (const other of owners.get(key) ?? []) parent.set(find(other), find(o.id));
    }
  }
  const byRoot = new Map<string, ProposedOperation[]>();
  for (const o of [...operations].sort((a, b) => a.seq - b.seq)) {
    const root = find(o.id);
    byRoot.set(root, [...(byRoot.get(root) ?? []), o]);
  }
  return [...byRoot.values()]
    .filter((ops) => ops.some((o) => kindOf(o) === CONFLICT_KIND))
    .map((ops) => ({ id: ops[0].id, operations: ops }))
    .sort((a, b) => a.operations[0].seq - b.operations[0].seq);
}

/**
 * True when two operations contradict each other directly: they change the
 * same type, or one's replacement triple is the other's current triple. A
 * cluster can chain A-B-C; keeping A rejects B, not C.
 */
export function contradicts(a: ProposedOperation, b: ProposedOperation): boolean {
  if (a.id === b.id) return false;
  const keysA = keysOf(a);
  const keysB = keysOf(b);
  return (
    keysA.some((k) => keysB.includes(k)) ||
    linksOf(a).some((k) => keysB.includes(k)) ||
    linksOf(b).some((k) => keysA.includes(k))
  );
}

/** The reject note of the operations a "Keep seq N" leaves out. */
export function keptNote(seq: number): string {
  return `conflict: kept seq ${seq}`;
}

// ==================== Reflection answers ====================

export const QUESTION_LABELS: Record<string, string> = {
  source_for: "Best source",
  target_for: "Best destination",
  predicate_for: "Best predicate",
};

const NONE = "none";
const REVERSE = "reverse:";

/** Question -> the option the reviewer picked, where it differs from what was shown. */
export type Picks = Record<string, string>;

function questionOf(reflection: Reflection, question: string) {
  return reflection.questions.find((q) => q.question === question);
}

/** The option a question settles on: the reviewer's pick, else the plan's, else the current. */
export function effectiveOption(
  reflection: Reflection,
  question: string,
  picks: Picks = {},
): ReflectionOption | undefined {
  const options = questionOf(reflection, question)?.options ?? [];
  const picked = picks[question];
  return (
    (picked !== undefined ? options.find((o) => o.option === picked) : undefined) ??
    options.find((o) => o.plan) ??
    options.find((o) => o.current)
  );
}

/**
 * An option the reviewer can pick: never 'none'; a class option needs its
 * class id; a predicate only when the answers it makes can be applied as an
 * edit (an older proposal without class ids can still rename its type, but
 * not reverse or retarget it). The plan's own answer can always be picked back.
 */
export function isPickable(
  reflection: Reflection,
  question: string,
  option: ReflectionOption,
  picks: Picks = {},
): boolean {
  if (option.option === NONE) return false;
  // Without the current triple, whether a pick retargets the type is unknown: only the
  // plan's answers can be accepted.
  if (!reflection.current) return option.plan;
  if (question !== "predicate_for") return !!option.class_id;
  if (option.plan) return true;
  const outcome = pickOutcome(reflection, { ...picks, [question]: option.option });
  return !!outcome && (!outcome.changed || outcome.keepsCurrent || !!outcome.fields);
}

/** How a type's new pair of classes compares with its current one. */
export type PairChange = "same" | "reversed" | "different";

interface Resolved {
  triple: string;
  fields?: Record<string, unknown>;
  /** Unknown without the current triple. */
  pair?: PairChange;
}

function resolve(reflection: Reflection, picks: Picks): Resolved | undefined {
  const source = effectiveOption(reflection, "source_for", picks);
  const target = effectiveOption(reflection, "target_for", picks);
  const predicate = effectiveOption(reflection, "predicate_for", picks)?.option;
  if (!source || !target || !predicate) return undefined;
  const reversed = predicate.startsWith(REVERSE);
  const name = reversed ? predicate.slice(REVERSE.length) : predicate;
  const [from, to] = reversed ? [target, source] : [source, target];
  const current = reflection.current;
  const pair: PairChange | undefined = !current
    ? undefined
    : from.option === current.source && to.option === current.target
      ? "same"
      : from.option === current.target && to.option === current.source
        ? "reversed"
        : "different";
  return {
    triple: `${from.option} ${name} ${to.option}`,
    pair,
    // Never an edit whose pair change is unknown (no current triple): it could retarget
    // a type in use without a resolution.
    fields: !pair
      ? undefined
      : from.class_id && to.class_id
        ? { canonical_predicate: name, domain_class_id: from.class_id, range_class_id: to.class_id }
        : pair === "same"
          ? // No class ids recorded, but the pair stays: the predicate alone renames it.
            { canonical_predicate: name }
          : undefined,
  };
}

export interface PickOutcome {
  /** The triple the answers make. */
  triple: string;
  /** The plan's own triple. */
  planTriple: string;
  /** The picks make another triple than the plan's: accept with my picks. */
  changed: boolean;
  /** The picks make the current triple: nothing to accept (reject to keep it). */
  keepsCurrent: boolean;
  /** The `edits[op_id]` entry when changed; absent when the answers can't be applied. */
  fields?: Record<string, unknown>;
  /** How the picks' pair compares with the type's current one (a retarget is "different"). */
  pair?: PairChange;
  /** The gold record of the picks when changed. */
  chosenAlternative?: Record<string, unknown>;
}

/** What the reviewer's picks make of a reflection operation; undefined when the answers are incomplete. */
export function pickOutcome(reflection: Reflection, picks: Picks = {}): PickOutcome | undefined {
  const plan = resolve(reflection, {});
  const mine = resolve(reflection, picks);
  if (!plan || !mine) return undefined;
  const current = reflection.current ? tripleText(reflection.current) : undefined;
  const changed = mine.triple !== plan.triple;
  const keepsCurrent = changed && mine.triple === current;
  const answers = Object.fromEntries(
    reflection.questions.map((q) => [
      q.question,
      effectiveOption(reflection, q.question, picks)?.option ?? null,
    ]),
  );
  return {
    triple: mine.triple,
    planTriple: plan.triple,
    changed,
    keepsCurrent,
    pair: mine.pair,
    fields: changed && !keepsCurrent ? mine.fields : undefined,
    chosenAlternative:
      changed && !keepsCurrent ? { ...answers, triple: mine.triple, plan: plan.triple } : undefined,
  };
}

export interface BestAlternative {
  question: string;
  option: string;
  probability: number;
  current: boolean;
}

/**
 * The likeliest answer the plan did not take, among the questions it changed
 * (its runner-up there, which may be the current answer); 'none' is skipped.
 */
export function bestAlternative(reflection: Reflection): BestAlternative | undefined {
  let best: BestAlternative | undefined;
  for (const q of reflection.questions) {
    const plan = q.options.find((o) => o.plan);
    if (!plan || plan.current) continue;
    for (const o of q.options) {
      if (o.plan || o.option === NONE) continue;
      if (!best || o.probability > best.probability) {
        best = {
          question: q.question,
          option: o.option,
          probability: o.probability,
          current: o.current,
        };
      }
    }
  }
  return best;
}

/** True while the operation still awaits and has answers a reviewer can pick from. */
export function takesPicks(operation: ProposedOperation): boolean {
  return isAwaiting(operation) && !!operation.reflection?.questions.length;
}
