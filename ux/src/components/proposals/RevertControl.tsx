import { useNavigate } from "@tanstack/react-router";
import { Button, Icon } from "@tinkermonkey/heimdall-ui";
import { ApiError } from "@/api/client/interceptors";
import { useProposeReversal } from "@/api/hooks/proposals";
import type { ChangeProposal } from "@/api/services/proposals";
import { useToasts } from "@/components/ui/Toast";
import { revertSummary, type RevertSummary } from "./decisionModel";
import { ProposeReversalDialog } from "./ProposeReversalDialog";
import { RevertProposalDialog } from "./RevertProposalDialog";
import { revertOffer } from "./reversalModel";

/** What an in-place revert undoes, in a sentence. */
export function revertMessage(summary: RevertSummary): string {
  const parts = [
    summary.created > 0 && `${summary.created} created removed`,
    summary.updated > 0 &&
      `${summary.updated} updated changed back${summary.edited > 0 ? ` (${summary.edited} edited)` : ""}`,
    summary.deleted > 0 && `${summary.deleted} deleted restored`,
    summary.relationships > 0 &&
      `the ${summary.relationships} relationship${summary.relationships === 1 ? "" : "s"} moved or deleted with a type restored on it`,
  ].filter(Boolean);
  const open =
    summary.open > 0
      ? ` The ${summary.open} operation${summary.open === 1 ? "" : "s"} still awaiting a decision ${summary.open === 1 ? "is" : "are"} rejected.`
      : "";
  return (
    `Undoes the ${summary.applied} operation${summary.applied === 1 ? "" : "s"} this proposal applied, in one transaction: ${parts.join(", ")}.` +
    `${open} The proposal becomes reverted and read-only, and its decisions can no longer be exported.`
  );
}

interface RevertControlProps {
  proposal: ChangeProposal;
  /** Another action is running on the proposal. */
  busy: boolean;
  /** Its dialog is open (the page pauses its review keys meanwhile). */
  confirming: boolean;
  onConfirmingChange: (confirming: boolean) => void;
  /** Revert it in place, once confirmed. */
  onRevert: () => void;
}

/**
 * The header's one revert control (#1668), by landing state: "Revert proposal"
 * while unlanded (undone in place, after the edits it would overwrite), and
 * "Propose the reversal…" once landed (a new proposal that undoes it, opened
 * once made). Nothing while a reversal is under way or there's nothing to undo.
 */
export function RevertControl({
  proposal,
  busy,
  confirming,
  onConfirmingChange: setConfirming,
  onRevert,
}: RevertControlProps) {
  const propose = useProposeReversal();
  const navigate = useNavigate();
  const { toast } = useToasts();
  const offer = revertOffer(proposal);
  if (!offer) return null;

  const proposeReversal = async () => {
    setConfirming(false);
    try {
      const reversal = await propose.mutateAsync(proposal.id);
      toast("success", "Reversal proposed", "Review it to undo the changes.");
      navigate({ to: "/app/proposals/$proposalId", params: { proposalId: reversal.id } });
    } catch (error) {
      toast(
        "error",
        "Couldn't propose the reversal",
        error instanceof ApiError ? error.detail : "An unexpected error occurred.",
      );
    }
  };

  const summary = revertSummary(proposal);
  return (
    <>
      {offer === "revert" ? (
        <Button
          variant="ghost"
          size="sm"
          disabled={busy}
          onClick={() => setConfirming(true)}
          data-testid="proposal-revert"
        >
          <Icon name="reload" size={13} /> Revert proposal
        </Button>
      ) : (
        <Button
          variant="ghost"
          size="sm"
          disabled={busy || propose.isPending}
          onClick={() => setConfirming(true)}
          data-testid="proposal-propose-reversal"
        >
          <Icon name="reload" size={13} /> Propose the reversal…
        </Button>
      )}
      {offer === "revert" ? (
        <RevertProposalDialog
          proposalId={proposal.id}
          isOpen={confirming}
          summary={revertMessage(summary)}
          onClose={() => setConfirming(false)}
          onConfirm={() => {
            setConfirming(false);
            onRevert();
          }}
        />
      ) : (
        <ProposeReversalDialog
          isOpen={confirming}
          applied={summary.applied}
          onClose={() => setConfirming(false)}
          onConfirm={() => void proposeReversal()}
        />
      )}
    </>
  );
}
