import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import {
  claimsService,
  type Claim,
  type ClaimFilters,
  type ClaimVerdictRequest,
} from "@/api/services/claims";

/** Show the claim the server returned now, then refresh every list and claim. */
function refreshClaim(queryClient: QueryClient, claim: Claim) {
  queryClient.setQueryData(QUERY_KEYS.claim(claim.id), claim);
  queryClient.invalidateQueries({ queryKey: QUERY_KEYS.claimsRoot });
}

/** Record a person's verdict on a claim (benchmark gold), replacing any earlier one. */
export function useSetClaimVerdict() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ClaimVerdictRequest }) =>
      claimsService.setVerdict(id, data),
    onSuccess: (claim) => refreshClaim(queryClient, claim),
  });
}

export function useClearClaimVerdict() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => claimsService.clearVerdict(id),
    onSuccess: (claim) => refreshClaim(queryClient, claim),
  });
}

/** Fetch a taxonomy's matching claims as JSONL text, to download it. */
export function useExportClaims() {
  return useMutation({
    mutationFn: ({ taxonomyId, filters }: { taxonomyId: string; filters?: ClaimFilters }) =>
      claimsService.exportClaims(taxonomyId, filters),
  });
}
