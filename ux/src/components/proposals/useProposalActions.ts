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
import {
  plural,
  revertConflictOf,
  splitBlocked,
  splitStale,
  type Resolutions,
} from "./decisionModel";
import { keptNote } from "./tieredModel";

export type Edits = Record<string, Record<string, unknown>>;
/** Operation id -> the alternative the reviewer chose over the plan's (recorded in gold). */
export type ChosenAlternatives = Record<string, Record<string, unknown>>;

/** How an apply ended: the server's error, or the reviewer cancelled the Apply anyway. */
export interface ApplyOutcome {
  error?: unknown;
  cancelled?: boolean;
  /** The proposal as the apply returned it. */
  proposal?: ChangeProposal;
}

interface ApplyOptions {
  edits?: Edits;
  chosenAlternatives?: ChosenAlternatives;
  /** How blocked relationship-type deletes resolve the relationships still using the type. */
  resolutions?: Resolutions;
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
  // Likewise the alternative each edited operation's last apply chose.
  const [lastAlternatives, setLastAlternatives] = useState<ChosenAlternatives>({});
  // Likewise the resolution each blocked delete's last apply sent.
  const [lastResolutions, setLastResolutions] = useState<Resolutions>({});
  const id = proposal?.id ?? "";

  const send = async (
    operationIds: string[],
    forceStale: string[],
    { edits = {}, chosenAlternatives = {}, resolutions = {}, merge = false }: ApplyOptions = {},
  ): Promise<ApplyOutcome> => {
    const remember = <T>(previous: Record<string, T>, sent: Record<string, T>) => {
      const next = { ...previous };
      for (const opId of operationIds) {
        if (sent[opId]) next[opId] = sent[opId];
        else delete next[opId];
      }
      return next;
    };
    setLastEdits((previous) => remember(previous, edits));
    setLastAlternatives((previous) => remember(previous, chosenAlternatives));
    setLastResolutions((previous) => remember(previous, resolutions));
    try {
      const proposal = await apply.mutateAsync({
        id,
        data: {
          operation_ids: operationIds,
          force_stale: forceStale,
          edits,
          ...(Object.keys(chosenAlternatives).length > 0
            ? { chosen_alternatives: chosenAlternatives }
            : {}),
          ...(Object.keys(resolutions).length > 0 ? { resolutions } : {}),
        },
      });
      setLastApplied((previous) =>
        merge && previous ? [...new Set([...previous, ...operationIds])] : operationIds,
      );
      setRevertConflict(null);
      return { proposal };
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

  /** The resolution this blocked delete's last apply sent, if any. */
  const lastResolutionOf = (opId: string) => lastResolutions[opId];

  /** Apply a failed operation again from the results: with its last edit or resolution. */
  const retry = (opId: string, { asProposed = false } = {}) => {
    const edit = asProposed ? undefined : lastEdits[opId];
    const alternative = edit ? lastAlternatives[opId] : undefined;
    const resolution = asProposed ? undefined : lastResolutions[opId];
    return accept([opId], {
      edits: edit ? { [opId]: edit } : undefined,
      chosenAlternatives: alternative ? { [opId]: alternative } : undefined,
      resolutions: resolution ? { [opId]: resolution } : undefined,
      merge: true,
    });
  };

  /**
   * Accept the operations that need no confirmation or choice: stale ones are
   * left for Apply anyway, and blocked deletes (relationships still use the
   * type) for a resolution in the inspector, which a toast says.
   */
  const acceptFresh = async (operationIds: string[]) => {
    if (!proposal) return;
    const { unblocked, blocked } = splitBlocked(proposal.operations, operationIds);
    const { fresh } = splitStale(proposal.operations, unblocked);
    if (blocked.length > 0) {
      toast(
        "info",
        `${plural(blocked.length, "blocked delete")} skipped`,
        "Relationships still use those types. Resolve each in the inspector: move them, delete them too, or keep the type.",
      );
    }
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

  /**
   * Keep one operation of a conflict: apply it, then reject the others with
   * "conflict: kept seq N". Nothing is rejected unless it applied.
   */
  const keepConflict = async (keep: ProposedOperation, others: string[]) => {
    const outcome = await accept([keep.id]);
    if (outcome.error || outcome.cancelled) return;
    const kept = outcome.proposal?.operations.find((o) => o.id === keep.id);
    if (kept?.status !== "applied") return;
    await rejectOperations(others, keptNote(keep.seq));
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
    keepConflict,
    revertProposal,
    downloadDecisions,
    forceRequest,
    confirmForce,
    cancelForce,
    retry,
    lastEditOf,
    lastResolutionOf,
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
