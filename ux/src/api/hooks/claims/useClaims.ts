import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { claimsService, type ClaimListParams } from "@/api/services/claims";

/** One page of a taxonomy's claims, oldest first; skipped without a taxonomy. */
export function useClaims(taxonomyId: string | undefined, params?: ClaimListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.claims(taxonomyId ?? "", params),
    queryFn: () => claimsService.listClaims(taxonomyId!, params),
    enabled: !!taxonomyId,
    // Keep the current page on screen while the next page or filter loads.
    placeholderData: keepPreviousData,
  });
}

/** One claim, with its triage and verdict; skipped without an id. */
export function useClaim(id: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.claim(id ?? ""),
    queryFn: () => claimsService.getClaim(id!),
    enabled: !!id,
  });
}
