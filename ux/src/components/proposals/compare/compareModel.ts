/**
 * Two pipelines' proposals for one source compared (#1615), worked out in the
 * browser: what each group means, which pairs a filter shows, the decision a
 * button sends, how a decided pair reads, and which open proposals a proposal
 * can be compared with.
 */
import type {
  ChangeProposal,
  ComparedOperation,
  ComparisonGroup,
  ComparisonPair,
  PairDecisionRequest,
  PairVerdict,
  RejectionReason,
} from "@/api/services/proposals";
import { proposalSourceId } from "../review/addFromText";
import { reasonLabel } from "../review/reviewModel";
import type { ChipVariant } from "../proposalModel";

export interface GroupMeta {
  label: string;
  /** What the row's kind line says. */
  kind: string;
  color: ChipVariant;
  /** What the reviewer does with it, under its count. */
  meta: string;
}

export const GROUPS: ComparisonGroup[] = ["same_class", "class_differs", "only_a", "only_b"];

export const GROUP_META: Record<ComparisonGroup, GroupMeta> = {
  same_class: {
    label: "Both, same class",
    kind: "same class",
    color: "emerald",
    meta: "decide together",
  },
  class_differs: {
    label: "Both, class differs",
    kind: "class differs",
    color: "violet",
    meta: "pick one class",
  },
  only_a: { label: "Only in A", kind: "only in A", color: "amber", meta: "keep or reject" },
  only_b: { label: "Only in B", kind: "only in B", color: "cyan", meta: "keep or reject" },
};

export type PairFilter = "differences" | "agreements" | "sample" | "all";

/** The pairs a filter shows: differences, agreements, the agreements' sample, or all. */
export function filterPairs(pairs: ComparisonPair[], filter: PairFilter): ComparisonPair[] {
  switch (filter) {
    case "differences":
      return pairs.filter((p) => p.group !== "same_class");
    case "agreements":
      return pairs.filter((p) => p.group === "same_class");
    case "sample":
      return pairs.filter((p) => p.in_sample);
    default:
      return pairs;
  }
}

/** A pair's element title: A's copy's, else B's. */
export function pairTitle(pair: ComparisonPair): string {
  return pair.a?.title || pair.b?.title || "";
}

/** A copy's class (the first it applies). */
export function classOf(copy: ComparedOperation | null | undefined): string | undefined {
  return copy?.classes[0]?.id;
}

/** A copy's first quoted passage, for the element's hover card. */
export function quoteOf(pair: ComparisonPair): string | undefined {
  for (const copy of [pair.a, pair.b]) {
    for (const item of copy?.evidence ?? []) {
      if (typeof item.quote === "string" && item.quote) return item.quote;
    }
  }
  return undefined;
}

function awaiting(copy: ComparedOperation | null | undefined): copy is ComparedOperation {
  return !!copy && (copy.status === "pending" || copy.status === "failed");
}

/** A pair still takes a decision: one of its copies awaits one. */
export function takesDecision(pair: ComparisonPair): boolean {
  return awaiting(pair.a) || awaiting(pair.b);
}

/**
 * The request a verdict on a pair sends: every copy still awaiting a decision
 * (both for an open pair; the server refuses one alone then), the reason for
 * not_element, and the time spent on the row.
 */
export function decisionRequest(
  pair: ComparisonPair,
  verdict: PairVerdict,
  { reasonCode, reviewMs }: { reasonCode?: RejectionReason; reviewMs?: number } = {},
): PairDecisionRequest {
  return {
    ...(awaiting(pair.a) ? { a_operation_id: pair.a.operation_id } : {}),
    ...(awaiting(pair.b) ? { b_operation_id: pair.b.operation_id } : {}),
    verdict,
    ...(verdict === "not_element" && reasonCode ? { reason_code: reasonCode } : {}),
    ...(reviewMs !== undefined ? { review_ms: reviewMs } : {}),
  };
}

/** The decision buttons a pair offers. */
export interface Choice {
  verdict: PairVerdict;
  label: string;
}

export function choicesFor(pair: ComparisonPair): Choice[] {
  if (pair.group === "class_differs") {
    return [
      { verdict: "a_class", label: "A class" },
      { verdict: "b_class", label: "B class" },
      { verdict: "not_element", label: "Neither" },
    ];
  }
  return [
    { verdict: "keep", label: "Keep" },
    { verdict: "not_element", label: "Not an element" },
  ];
}

/** How a decided pair reads: which copy landed with which class, or why neither is an element. */
export function outcomeText(pair: ComparisonPair, classLabel: (id?: string) => string): string {
  const landed = [pair.a, pair.b].find((c) => c?.status === "applied");
  if (landed) {
    const side = landed === pair.a ? "A" : "B";
    const label = classLabel(classOf(landed));
    if (pair.group === "class_differs") return `${side} class: ${label}`;
    return `Kept as ${label}`;
  }
  const rejected = [pair.a, pair.b].find((c) => c?.status === "rejected");
  const reason = reasonLabel(rejected?.reason_code);
  return `Not an element${reason ? `: ${reason}` : ""}`;
}

/** Why a pair's landing failed: its failed copy's reason. */
export function failureOf(pair: ComparisonPair): string | undefined {
  const failed = [pair.a, pair.b].find((c) => c?.status === "failed");
  return failed ? (failed.reason ?? "The apply failed; no reason was given.") : undefined;
}

// ==================== What a proposal can be compared with ====================

/** The model a proposal's run used, when its metadata records one. */
export function originModel(proposal: ChangeProposal | undefined): string | undefined {
  const meta = proposal?.client_metadata ?? {};
  const origin = meta.origin as Record<string, unknown> | undefined;
  const model = meta.model ?? origin?.model;
  return typeof model === "string" && model ? model : undefined;
}

/** How many individuals and relationships a proposal creates. */
export function proposalSize(proposal: ChangeProposal | undefined) {
  const operations = proposal?.operations ?? [];
  const creates = (kind: string) =>
    operations.filter((o) => o.op === "create" && o.kind === kind).length;
  return { individuals: creates("individual"), relationships: creates("relationship") };
}

/**
 * The open proposals `proposal` can be compared with: other open individual
 * extractions of the same source into the same dataset, made by another
 * pipeline implementation. (The list API can't filter by source yet: #1626.)
 */
export function comparableProposals(
  proposal: ChangeProposal | undefined,
  candidates: ChangeProposal[],
): ChangeProposal[] {
  const sourceId = proposalSourceId(proposal);
  const implementation = proposal?.origin?.implementation_id;
  if (!proposal || proposal.status !== "open" || !sourceId || !implementation) return [];
  return candidates.filter(
    (c) =>
      c.id !== proposal.id &&
      c.status === "open" &&
      proposalSourceId(c) === sourceId &&
      c.dataset_id === proposal.dataset_id &&
      c.taxonomy_id === proposal.taxonomy_id &&
      !!c.origin &&
      c.origin.pipeline_type === proposal.origin?.pipeline_type &&
      c.origin.implementation_id !== implementation,
  );
}
