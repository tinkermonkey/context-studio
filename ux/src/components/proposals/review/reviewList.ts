/**
 * The review list (#1663): every operation of a proposal, grouped by layer,
 * change kind or sequence, with conflict cards in the change-kind view. Pure
 * functions; the list component and the page compose them.
 */
import type { ChipVariant } from "@tinkermonkey/heimdall-ui";
import type { ProposedOperation } from "@/api/services/proposals";
import { decisionState } from "../decisionModel";
import { offersGroupBy, pRangeLabel, tieredSections, type ConflictCluster } from "../tieredModel";
import {
  RELATIONSHIPS_GROUP,
  VERDICT_CHIP,
  isElement,
  isRelationship,
  verdictLabel,
  verdictOf,
  type Layer,
} from "./reviewModel";

export type ListGroupBy = "layer" | "kind" | "sequence";

export const GROUP_BY_LABELS: Record<ListGroupBy, string> = {
  layer: "Layer",
  kind: "Change kind",
  sequence: "Sequence",
};

export type ListItem =
  | { type: "row"; operation: ProposedOperation }
  | { type: "conflict"; cluster: ConflictCluster };

export interface ListSection {
  key: string;
  label: string;
  /** What the section is for, under its label (a change plan's tiers). */
  note?: string;
  items: ListItem[];
}

/** Whether an operation reads as an extraction's element or relationship (the layer view's). */
function extracted(operation: ProposedOperation): boolean {
  return isElement(operation) || isRelationship(operation);
}

/**
 * The groupings worth offering: Layer when some operation is an element or a
 * relationship, Change kind when some carries a plan kind, and Sequence always.
 */
export function groupByOptions(operations: ProposedOperation[]): ListGroupBy[] {
  return [
    operations.some(extracted) && ("layer" as const),
    offersGroupBy(operations) && ("kind" as const),
    "sequence" as const,
  ].filter((g): g is ListGroupBy => !!g);
}

/** Change kind for a change plan with reflections, Layer for an extraction, else Sequence. */
export function defaultListGroupBy(operations: ProposedOperation[]): ListGroupBy {
  if (operations.some((o) => o.reflection) && offersGroupBy(operations)) return "kind";
  if (operations.some(extracted)) return "layer";
  return "sequence";
}

const KIND_GROUP_LABELS: Record<ProposedOperation["kind"], string> = {
  taxonomy: "Taxonomies",
  scheme: "Concept schemes",
  class: "Classes",
  property: "Relationship types",
  attribute: "Attributes",
  individual: "Individuals",
  relationship: "Relationships",
  predicate: "Predicates",
};

function rows(operations: ProposedOperation[]): ListItem[] {
  return operations.map((operation) => ({ type: "row", operation }));
}

function bySeq(operations: ProposedOperation[]): ProposedOperation[] {
  return [...operations].sort((a, b) => a.seq - b.seq);
}

/**
 * The sections the list shows for `shown` (what the filters leave), in order:
 * - Layer: elements by layer in the order the layers first appear, then the
 *   relationships, then the other operations by what they change;
 * - Change kind: mechanical kinds, judgment kinds, a conflict card per cluster
 *   (members the filters show), then the rest;
 * - Sequence: one section in seq order.
 */
export function listSections(
  shown: ProposedOperation[],
  all: ProposedOperation[],
  groupBy: ListGroupBy,
  layerOf: (operation: ProposedOperation) => Layer,
): ListSection[] {
  if (groupBy === "sequence") {
    return shown.length > 0
      ? [{ key: "sequence", label: "Sequence", items: rows(bySeq(shown)) }]
      : [];
  }
  if (groupBy === "kind") {
    const { mechanical, judgment, clusters, other } = tieredSections(shown, all);
    return [
      ...mechanical.map((g) => ({
        key: `kind-${g.kind}`,
        label: `${g.kind} · mechanical`,
        note: `${g.operations.length} · ${pRangeLabel(g.operations)}`,
        items: rows(g.operations),
      })),
      ...judgment.map((g) => ({
        key: `kind-${g.kind}`,
        label: `${g.kind} · judgment`,
        note: "Decided one by one: weigh the plan's pick against the alternatives.",
        items: rows(g.operations),
      })),
      ...(clusters.length > 0
        ? [
            {
              key: "conflicts",
              label: "Conflicts",
              note: "Reflections that disagree about the same types: keep one, or decide each.",
              items: clusters.map((cluster) => ({ type: "conflict" as const, cluster })),
            },
          ]
        : []),
      ...(other.length > 0 ? [{ key: "kind-other", label: "Other", items: rows(other) }] : []),
    ];
  }
  // Layer.
  const sections: ListSection[] = [];
  const section = (key: string, label: string) => {
    let found = sections.find((s) => s.key === key);
    if (!found) {
      found = { key, label, items: [] };
      sections.push(found);
    }
    return found;
  };
  const elements = shown.filter(isElement);
  const relationships = shown.filter(isRelationship);
  const others = shown.filter((o) => !extracted(o));
  for (const operation of elements) {
    const layer = layerOf(operation);
    section(layer.key, layer.label).items.push({ type: "row", operation });
  }
  if (relationships.length > 0) {
    section(RELATIONSHIPS_GROUP, "Relationships").items.push(...rows(relationships));
  }
  for (const operation of bySeq(others)) {
    section(`kind-${operation.kind}`, KIND_GROUP_LABELS[operation.kind]).items.push({
      type: "row",
      operation,
    });
  }
  return sections;
}

/** The operation ids top to bottom, conflict members included as their cards list them. */
export function listOrder(sections: ListSection[], shownIds: ReadonlySet<string>): string[] {
  return sections.flatMap((s) =>
    s.items.flatMap((item) =>
      item.type === "row"
        ? [item.operation.id]
        : item.cluster.operations.filter((o) => shownIds.has(o.id)).map((o) => o.id),
    ),
  );
}

export interface RowStatus {
  /** data-verdict: an element's verdict, else the decision state. */
  state: string;
  label: string;
  variant: ChipVariant;
}

/**
 * A row's status chip: an extraction's element or relationship by its verdict,
 * anything else (and a failed apply) by its decision state; withdrawn by its
 * proposer (#1624) either way.
 */
export function rowStatus(operation: ProposedOperation, reverted = false): RowStatus {
  if (operation.status === "withdrawn") {
    return { state: "withdrawn", label: "withdrawn", variant: "neutral" };
  }
  // A failed apply reads as failed for every kind: it is retried or rejected.
  if (
    extracted(operation) &&
    operation.status !== "failed" &&
    !(reverted && operation.status === "applied")
  ) {
    const verdict = verdictOf(operation);
    return { state: verdict, label: verdictLabel(operation), variant: VERDICT_CHIP[verdict] };
  }
  const state = decisionState(operation, reverted);
  return { state: state.state, label: state.label, variant: state.variant };
}
