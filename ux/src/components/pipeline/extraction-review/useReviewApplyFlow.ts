import { useState } from "react";
import { useToasts } from "@/components/ui/Toast";
import { useRevertRun } from "@/api/hooks/pipeline/usePipelineMutations";
import {
  useApplyReviewedRun,
  type ReviewApplyInput,
} from "@/api/hooks/pipeline/useApplyReviewedRun";
import { ApiError } from "@/api/client/interceptors";

function reason(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "An unexpected error occurred.";
}

/** Confirm → apply → (optionally) revert, shared by both review tabs. */
export function useReviewApplyFlow(labels: { applied: string; reverted: string }) {
  const { toast } = useToasts();
  const { applyReviewed, isPending: applying } = useApplyReviewedRun();
  const revert = useRevertRun();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [applied, setApplied] = useState(false);

  const confirm = async (input: ReviewApplyInput) => {
    setConfirmOpen(false);
    try {
      await applyReviewed(input);
      setApplied(true);
      toast("success", labels.applied, input.runId);
    } catch (err) {
      toast("error", "Apply failed", reason(err));
    }
  };

  const revertRun = async (runId: string) => {
    try {
      await revert.mutateAsync(runId);
      setApplied(false);
      toast("info", "Run reverted", `${runId} · ${labels.reverted}`);
    } catch (err) {
      toast("error", "Revert failed", reason(err));
    }
  };

  return {
    confirmOpen,
    openConfirm: () => setConfirmOpen(true),
    closeConfirm: () => setConfirmOpen(false),
    applied,
    busy: applying || revert.isPending,
    confirm,
    revertRun,
  };
}
