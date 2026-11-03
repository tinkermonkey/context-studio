import { useRef, useState } from "react";
import {
  useApplyChangeProposal,
  useExportProposalDecisions,
  useRejectChangeProposal,
  useRevertChangeProposal,
} from "@/api/hooks/proposals";
import { ApiError } from "@/api/client/interceptors";
import type {
  ChangeProposal,
  ChangeProposalRevertConflict,
  ProposedOperation,
} from "@/api/services/proposals";
import { useToasts } from "@/components/ui/Toast";
import { downloadJson } from "@/lib/download";
import { revertConflictOf, splitStale } from "./decisionModel";

export type Edits = Record<string, Record<string, unknown>>;

/** How an apply ended: the server's error, or the reviewer cancelled the Apply anyway. */
export interface ApplyOutcome {
  error?: unknown;
  cancelled?: boolean;
}

interface ApplyOptions {
  edits?: Edits;
  /** Add these outcomes to the results view instead of replacing it (a retry from it). */
  merge?: boolean;
}

/** An apply that includes stale operations, waiting for the reviewer to confirm Apply anyway. */
export interface ForceRequest extends ApplyOptions {
  operationIds: string[];
  settle: (outcome: ApplyOutcome) => void;
}

/** Reasons an edited apply leaves on the operation: the edit, not the proposal, failed. */
const EDIT_FAILURE = /^(invalid_edit|refused): /;

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
  // The waiting request, claimed once: by Apply anyway or by Cancel, whichever comes first.
  const pendingForce = useRef<ForceRequest | null>(null);
  const [revertConflict, setRevertConflict] = useState<ChangeProposalRevertConflict | null>(null);
  // The edit each operation's last apply sent: the server keeps none for a failed one.
  const [lastEdits, setLastEdits] = useState<Edits>({});
  const id = proposal?.id ?? "";

  const send = async (
    operationIds: string[],
    forceStale: string[],
    { edits = {}, merge = false }: ApplyOptions = {},
  ): Promise<ApplyOutcome> => {
    setLastEdits((previous) => {
      const next = { ...previous };
      for (const opId of operationIds) {
        if (edits[opId]) next[opId] = edits[opId];
        else delete next[opId];
      }
      return next;
    });
    try {
      await apply.mutateAsync({
        id,
        data: { operation_ids: operationIds, force_stale: forceStale, edits },
      });
      setLastApplied((previous) =>
        merge && previous ? [...new Set([...previous, ...operationIds])] : operationIds,
      );
      setRevertConflict(null);
      return {};
    } catch (error) {
      return { error };
    }
  };

  /**
   * Apply operations as they are (or with `edits`). Stale ones among them
   * wait for the Apply anyway confirmation instead; the rest apply then.
   * Settles once the apply does, or when the confirmation is cancelled.
   */
  const accept = async (
    operationIds: string[],
    options: ApplyOptions = {},
  ): Promise<ApplyOutcome> => {
    if (!proposal) return {};
    const { fresh, stale } = splitStale(proposal.operations, operationIds);
    if (stale.length > 0) {
      return new Promise((settle) => {
        const request = { ...options, operationIds: [...fresh, ...stale], settle };
        pendingForce.current = request;
        setForceRequest(request);
      });
    }
    if (fresh.length === 0) return {};
    return send(fresh, [], options);
  };

  /** The edit this operation's last apply sent, if any. */
  const lastEditOf = (opId: string) => lastEdits[opId];

  /** True when the operation's last apply was an edit, or its failure is the edit's. */
  const editFailed = (operation: ProposedOperation) =>
    operation.status === "failed" &&
    (!!lastEdits[operation.id] || EDIT_FAILURE.test(operation.reason ?? ""));

  /** Apply a failed operation again from the results: with its last edit, if it had one. */
  const retry = (opId: string, { asProposed = false } = {}) => {
    const edit = asProposed ? undefined : lastEdits[opId];
    return accept([opId], { edits: edit ? { [opId]: edit } : undefined, merge: true });
  };

  /** Accept the operations that need no confirmation; stale ones are left for Apply anyway. */
  const acceptFresh = async (operationIds: string[]) => {
    if (!proposal) return;
    const { fresh } = splitStale(proposal.operations, operationIds);
    if (fresh.length > 0) await send(fresh, []);
  };

  const confirmForce = async () => {
    const request = pendingForce.current;
    pendingForce.current = null;
    setForceRequest(null);
    if (!request || !proposal) return;
    const { stale } = splitStale(proposal.operations, request.operationIds);
    request.settle(await send(request.operationIds, stale, request));
  };

  const cancelForce = () => {
    const request = pendingForce.current;
    pendingForce.current = null;
    request?.settle({ cancelled: true });
    setForceRequest(null);
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
    cancelForce,
    retry,
    lastEditOf,
    editFailed,
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
