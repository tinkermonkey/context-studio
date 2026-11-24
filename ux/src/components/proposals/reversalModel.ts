/**
 * Reverting a proposal, by its landing state (#1668): in place while unlanded,
 * by a reversal proposal once landed. A reversal and the proposal it undoes
 * link each other (`reverses` / `reversed_by`, #1667).
 */
import type { ChangeProposal } from "@/api/services/proposals";
import { takesDecisions } from "./decisionModel";
import type { ChipVariant } from "./proposalModel";

export type ProposalLinkInfo = NonNullable<ChangeProposal["links"]>[number];

/** The proposal this one is the reversal of, if it is one. */
export function reversalOf(proposal: ChangeProposal): ProposalLinkInfo | undefined {
  return proposal.links?.find((link) => link.kind === "reverses");
}

/**
 * Its reversal still under way: open, or decided but not yet landed (only
 * landing it marks this proposal reversed).
 */
export function pendingReversal(proposal: ChangeProposal): ProposalLinkInfo | undefined {
  if (proposal.status === "reversed") return undefined;
  return proposal.links?.find(
    (link) => link.kind === "reversed_by" && (link.status === "open" || link.status === "done"),
  );
}

/**
 * What the header's revert control offers: the in-place revert while the
 * proposal is unlanded, the reversal proposal once landed, or nothing (nothing
 * applied, no more decisions, a reversal under way, or a reversal itself, whose
 * changes are proposed again instead).
 */
export function revertOffer(proposal: ChangeProposal): "revert" | "reversal" | undefined {
  if (!takesDecisions(proposal)) return undefined;
  if (!proposal.operations.some((o) => o.status === "applied")) return undefined;
  if (!proposal.landed) return "revert";
  if (reversalOf(proposal) || pendingReversal(proposal)) return undefined;
  return "reversal";
}

export interface ReversalChip {
  link: ProposalLinkInfo;
  label: string;
  variant: ChipVariant;
  /** On the proposal a landed reversal undid: "3 of 4 changes reversed". */
  count?: string;
}

/** How many of the reversal's changes were applied, as the original's strip says it. */
function reversedCount(link: ProposalLinkInfo): string | undefined {
  const applied = link.operations_applied;
  const total = link.operations_total;
  if (applied == null || total == null) return undefined;
  return `${applied} of ${total} change${total === 1 ? "" : "s"} reversed`;
}

/** One chip per reversal link, for the status strip and the Proposals list. */
export function reversalChips(proposal: ChangeProposal): ReversalChip[] {
  return (proposal.links ?? []).flatMap((link): ReversalChip[] => {
    if (link.kind === "reverses") return [{ link, label: "reverses", variant: "cyan" }];
    if (link.kind !== "reversed_by") return [];
    if (link.status === "open") return [{ link, label: "reversal open", variant: "amber" }];
    if (link.status === "done" && proposal.status === "reversed") {
      return [{ link, label: "reversed by", variant: "neutral", count: reversedCount(link) }];
    }
    if (link.status === "done") return [{ link, label: "reversal not landed", variant: "amber" }];
    return [{ link, label: `reversal ${link.status ?? "missing"}`, variant: "neutral" }];
  });
}
