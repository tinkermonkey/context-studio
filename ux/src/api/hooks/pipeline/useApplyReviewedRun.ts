import { useCallback } from "react";
import { useApplyRun } from "./usePipelineMutations";
import type { ApplyParams, ApplyRunRequest, RecognitionDecision } from "@/api/services/pipeline";
import type { ReviewKind } from "./useExtractionReviewRuns";

export type { ApplyRunResponse, MergedMention } from "@/api/services/pipeline";

/** A review decision. "yes" = accept / merge, "no" = reject / keep separate. */
export type ReviewDecisionValue = "yes" | "no" | "pending";

/** A recognition hit the reviewer can merge into an existing individual or keep separate. */
export interface ReviewedMention {
  mention_label: string;
  /** Existing individual the preview resolved the mention to (the merge target). */
  individual_id: string;
  decision: ReviewDecisionValue;
}

export interface ReviewApplyInput {
  runId: string;
  kind: ReviewKind;
  scope: { taxonomy_id: string; concept_scheme_id?: string };
  /** Decisions keyed by the API's candidate_id. */
  decisions: Record<string, ReviewDecisionValue>;
  /** Per-mention merge / keep-separate choices (individual extraction only). */
  mentions?: ReviewedMention[];
}

export interface ReviewApplyPlan {
  params: ApplyParams;
  body: ApplyRunRequest;
}

/** Recognition threshold for the preview and for mentions the reviewer left undecided. */
export const REVIEW_RECOGNITION_THRESHOLD = 0.9;

/**
 * Translate review decisions into an apply request. This is the only place that
 * knows the apply contract: accepted candidate ids are the full selection
 * (everything else is skipped), and decided mentions are sent as explicit
 * merge / separate decisions. Undecided mentions go through recognition.
 */
export function planReviewApply(input: ReviewApplyInput): ReviewApplyPlan {
  const accepted = Object.entries(input.decisions)
    .filter(([, v]) => v === "yes")
    .map(([id]) => id);
  const params: ApplyParams = { taxonomy_id: input.scope.taxonomy_id };
  const body: ApplyRunRequest = { accepted_candidate_ids: accepted };

  if (input.kind === "schema") {
    params.concept_scheme_id = input.scope.concept_scheme_id;
  } else {
    params.recognition_threshold = REVIEW_RECOGNITION_THRESHOLD;
    // The server matches labels case-insensitively and rejects duplicates: keep the first.
    const seen = new Set<string>();
    const decisions: RecognitionDecision[] = (input.mentions ?? [])
      .filter((m) => {
        const label = m.mention_label.trim().toLowerCase();
        if (m.decision === "pending" || seen.has(label)) return false;
        seen.add(label);
        return true;
      })
      .map((m) =>
        m.decision === "yes"
          ? { mention_label: m.mention_label, decision: "merge", individual_id: m.individual_id }
          : { mention_label: m.mention_label, decision: "separate" },
      );
    if (decisions.length > 0) body.recognition_decisions = decisions;
  }
  return { params, body };
}

export function useApplyReviewedRun() {
  const mutation = useApplyRun();
  const { mutateAsync } = mutation;
  const applyReviewed = useCallback(
    (input: ReviewApplyInput) => {
      const { params, body } = planReviewApply(input);
      return mutateAsync({ runId: input.runId, params, body });
    },
    [mutateAsync],
  );
  return { applyReviewed, isPending: mutation.isPending };
}
