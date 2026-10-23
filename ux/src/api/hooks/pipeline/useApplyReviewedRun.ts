import { useCallback } from "react";
import { useApplyRun } from "./usePipelineMutations";
import type { ApplyParams } from "@/api/services/pipeline";
import type { ReviewKind } from "./useExtractionReviewRuns";

/** A review decision. "yes" = accept / merge, "no" = reject / keep separate. */
export type ReviewDecisionValue = "yes" | "no" | "pending";

export interface ReviewedItem {
  key: string;
  confidence: number;
}

export interface ReviewApplyInput {
  runId: string;
  kind: ReviewKind;
  scope: { taxonomy_id: string; concept_scheme_id?: string };
  items: ReviewedItem[];
  decisions: Record<string, ReviewDecisionValue>;
  /** Per-mention merge decisions (individual extraction only). */
  merges?: Record<string, ReviewDecisionValue>;
}

export interface ReviewApplyPlan {
  params: ApplyParams;
  /** Lowest accepted confidence — the effective filter under threshold-based apply. */
  minConfidence: number | null;
  /** Rejected items that the threshold would still apply. */
  leakedKeys: string[];
  /** "Keep separate" choices the threshold contract cannot honour per mention. */
  ignoredSeparateCount: number;
}

/** Recognition threshold used for both the preview and apply, so they agree. */
export const REVIEW_RECOGNITION_THRESHOLD = 0.9;

/**
 * Translate review decisions into an apply request. This is the ONLY place that
 * knows the apply contract: today apply takes a confidence threshold, so the
 * plan uses the lowest accepted confidence and reports rejected items that
 * would leak through. Switch this function when explicit selections land.
 */
export function planReviewApply(input: ReviewApplyInput): ReviewApplyPlan {
  const accepted = input.items.filter((it) => input.decisions[it.key] === "yes");
  const minConfidence = accepted.length ? Math.min(...accepted.map((it) => it.confidence)) : null;
  const leakedKeys =
    minConfidence === null
      ? []
      : input.items
          .filter((it) => input.decisions[it.key] === "no" && it.confidence >= minConfidence)
          .map((it) => it.key);
  const ignoredSeparateCount = Object.values(input.merges ?? {}).filter((v) => v === "no").length;

  const params: ApplyParams = {
    confidence_threshold: minConfidence ?? 1,
    taxonomy_id: input.scope.taxonomy_id,
  };
  if (input.kind === "schema") {
    params.concept_scheme_id = input.scope.concept_scheme_id;
  } else {
    params.recognition_threshold = REVIEW_RECOGNITION_THRESHOLD;
  }
  return { params, minConfidence, leakedKeys, ignoredSeparateCount };
}

export function useApplyReviewedRun() {
  const mutation = useApplyRun();
  const { mutateAsync } = mutation;
  const applyReviewed = useCallback(
    (input: ReviewApplyInput) =>
      mutateAsync({ runId: input.runId, params: planReviewApply(input).params }),
    [mutateAsync],
  );
  return { applyReviewed, isPending: mutation.isPending };
}
