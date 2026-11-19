import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import {
  DEFAULT_SAMPLE_SIZE,
  proposalsService,
  type PairDecisionRequest,
} from "@/api/services/proposals";
import { invalidateOntology } from "./useProposalMutations";

/** Two proposals for one source compared: their pairs, counts and the agreements' sample. */
export function useProposalComparison(a: string, b: string, sampleSize = DEFAULT_SAMPLE_SIZE) {
  return useQuery({
    queryKey: QUERY_KEYS.proposalComparison(a, b, sampleSize),
    queryFn: () => proposalsService.compareProposals(a, b, sampleSize),
    enabled: !!a && !!b,
    // A refusal (not_comparable) is an answer, not a blip.
    retry: false,
  });
}

/**
 * Decide one pair once for both proposals. The page shows a refusal (422,
 * 409) beside the pair, so the global toast is skipped. What lands changes
 * the ontology and both proposals (the comparison is under their root).
 */
export function useDecidePair(a: string, b: string, sampleSize = DEFAULT_SAMPLE_SIZE) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PairDecisionRequest) => proposalsService.decidePair(a, b, data, sampleSize),
    meta: { skipGlobalErrorToast: true },
    // Wait for the comparison to refetch, so a decided row never shows its buttons again.
    onSettled: () => {
      invalidateOntology(queryClient);
      return queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.proposalComparison(a, b, sampleSize),
      });
    },
  });
}

/** Accept the agreements outside the checked sample; refusals are shown by the page. */
export function useAcceptRest(a: string, b: string, sampleSize = DEFAULT_SAMPLE_SIZE) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => proposalsService.acceptRest(a, b, sampleSize),
    meta: { skipGlobalErrorToast: true },
    // Wait for the comparison to refetch, so a decided row never shows its buttons again.
    onSettled: () => {
      invalidateOntology(queryClient);
      return queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.proposalComparison(a, b, sampleSize),
      });
    },
  });
}
