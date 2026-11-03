import { useState } from "react";
import {
  useApplyChangeProposal,
  useExportProposalDecisions,
  useRejectChangeProposal,
  useRevertChangeProposal,
} from "@/api/hooks/proposals";
import { ApiError } from "@/api/client/interceptors";
import type { ChangeProposal, ChangeProposalRevertConflict } from "@/api/services/proposals";
import { useToasts } from "@/components/ui/Toast";
import { downloadJson } from "@/lib/download";
import { revertConflictOf, splitStale } from "./decisionModel";

export type Edits = Record<string, Record<string, unknown>>;

/** An apply that includes stale operations, waiting for the reviewer to confirm Apply anyway. */
export interface ForceRequest {
  operationIds: string[];
  edits?: Edits;
}

function message(error: unknown): string {
  if (error instanceof ApiError) return error.detail;
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred.";
}

/**
 * Apply, reject, revert and export one proposal. Applies return the server's
 * error instead of throwing (the global mutation toast reports it too), so an
 * editor can show a 422 next to its fields. The last apply's operation ids
 * drive the results view; a refused (409) revert is kept for the page to explain.
 */
export function useProposalActions(proposal: ChangeProposal | undefined) {
  const { toast } = useToasts();
  const apply = useApplyChangeProposal();
  const reject = useRejectChangeProposal();
  const revert = useRevertChangeProposal();
  const exportDecisions = useExportProposalDecisions();
  const [lastApplied, setLastApplied] = useState<string[] | null>(null);
  const [forceRequest, setForceRequest] = useState<ForceRequest | null>(null);
  const [revertConflict, setRevertConflict] = useState<ChangeProposalRevertConflict | null>(null);
  const id = proposal?.id ?? "";

  const send = async (
    operationIds: string[],
    forceStale: string[],
    edits: Edits = {},
  ): Promise<{ error?: unknown }> => {
    try {
      await apply.mutateAsync({
        id,
        data: { operation_ids: operationIds, force_stale: forceStale, edits },
      });
      setLastApplied(operationIds);
      setRevertConflict(null);
      return {};
    } catch (error) {
      return { error };
    }
  };

  /**
   * Apply operations as they are (or with `edits`). Stale ones among them
   * wait for the Apply anyway confirmation instead; the rest apply now.
   */
  const accept = async (operationIds: string[], edits?: Edits): Promise<{ error?: unknown }> => {
    if (!proposal) return {};
    const { fresh, stale } = splitStale(proposal.operations, operationIds);
    if (stale.length > 0) {
      setForceRequest({ operationIds: [...fresh, ...stale], edits });
      return {};
    }
    if (fresh.length === 0) return {};
    return send(fresh, [], edits);
  };

  /** Accept the operations that need no confirmation; stale ones are left for Apply anyway. */
  const acceptFresh = async (operationIds: string[]) => {
    if (!proposal) return;
    const { fresh } = splitStale(proposal.operations, operationIds);
    if (fresh.length > 0) await send(fresh, []);
  };

  const confirmForce = async (): Promise<{ error?: unknown }> => {
    const request = forceRequest;
    setForceRequest(null);
    if (!request || !proposal) return {};
    const { stale } = splitStale(proposal.operations, request.operationIds);
    return send(request.operationIds, stale, request.edits);
  };

  const rejectOperations = async (operationIds: string[], note?: string) => {
    if (operationIds.length === 0) return false;
    try {
      await reject.mutateAsync({
        id,
        data: { operation_ids: operationIds, note: note?.trim() || null },
      });
      toast(
        "info",
        operationIds.length === 1
          ? "Operation rejected"
          : `${operationIds.length} operations rejected`,
      );
      return true;
    } catch {
      return false; // the global mutation toast reports it
    }
  };

  const revertProposal = async () => {
    try {
      const result = await revert.mutateAsync(id);
      setLastApplied(null);
      setRevertConflict(null);
      toast(
        "success",
        "Proposal reverted",
        `${result.events_reverted} change${result.events_reverted === 1 ? "" : "s"} undone`,
      );
    } catch (error) {
      const conflict = revertConflictOf(error);
      if (conflict) setRevertConflict(conflict);
      else toast("error", "Revert failed", message(error));
    }
  };

  const downloadDecisions = async () => {
    try {
      const decisions = await exportDecisions.mutateAsync(id);
      downloadJson(`dr-decisions-${id.slice(0, 8)}.json`, decisions);
    } catch {
      // the global mutation toast reports it
    }
  };

  return {
    accept,
    acceptFresh,
    rejectOperations,
    revertProposal,
    downloadDecisions,
    forceRequest,
    confirmForce,
    cancelForce: () => setForceRequest(null),
    /** Operation ids the last apply sent; null until one ran (or after a revert). */
    lastApplied,
    closeResults: () => setLastApplied(null),
    revertConflict,
    dismissRevertConflict: () => setRevertConflict(null),
    busy: apply.isPending || reject.isPending || revert.isPending,
    exporting: exportDecisions.isPending,
  };
}

export type ProposalActions = ReturnType<typeof useProposalActions>;
