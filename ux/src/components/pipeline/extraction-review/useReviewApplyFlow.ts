import { useState } from "react";
import { useToasts } from "@/components/ui/Toast";
import { useRevertRun } from "@/api/hooks/pipeline/usePipelineMutations";
import {
  useApplyReviewedRun,
  type ApplyRunResponse,
  type ReviewApplyInput,
} from "@/api/hooks/pipeline/useApplyReviewedRun";
import { ApiError } from "@/api/client/interceptors";
import { failedSkips } from "./reviewUtils";

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
  const [result, setResult] = useState<ApplyRunResponse | null>(null);

  const confirm = async (input: ReviewApplyInput) => {
    setConfirmOpen(false);
    try {
      const response = await applyReviewed(input);
      setResult(response);
      const acceptedSkipped = failedSkips(response).length;
      toast(
        acceptedSkipped > 0 ? "warning" : "success",
        labels.applied,
        `${response.applied_candidate_ids?.length ?? 0} applied · ${acceptedSkipped} accepted skipped`,
      );
    } catch (err) {
      toast("error", "Apply failed", reason(err));
    }
  };

  const revertRun = async (runId: string) => {
    try {
      const response = await revert.mutateAsync(runId);
      setResult(null);
      if (response.events_reverted === 0) {
        toast("warning", "Nothing to revert", `${runId} recorded no changes to undo`);
      } else {
        toast("info", "Run reverted", `${runId} · ${labels.reverted}`);
      }
    } catch (err) {
      toast("error", "Revert failed", reason(err));
    }
  };

  return {
    confirmOpen,
    openConfirm: () => setConfirmOpen(true),
    closeConfirm: () => setConfirmOpen(false),
    applied: result !== null,
    /** What the server applied, skipped and merged; null until applied. */
    result,
    busy: applying || revert.isPending,
    confirm,
    revertRun,
  };
}
