import { useQueries, useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import type { components } from "@/api/types";

type SchemeCountsResponse = components["schemas"]["SchemeCountsResponse"];

/** Class, individual and property-definition counts for each scheme in a taxonomy. */
export function useSchemeCounts(taxonomyId: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.schemeCounts(taxonomyId ?? ""),
    queryFn: () => ontologyService.getSchemeCounts(taxonomyId as string),
    enabled: !!taxonomyId,
  });
}

/**
 * Scheme counts for several taxonomies (one request per taxonomy), as a map of
 * scheme id → counts. Pass an empty list to skip.
 */
export function useSchemeCountsForTaxonomies(
  taxonomyIds: string[],
): Map<string, SchemeCountsResponse> {
  const results = useQueries({
    queries: taxonomyIds.map((taxonomyId) => ({
      queryKey: QUERY_KEYS.schemeCounts(taxonomyId),
      queryFn: () => ontologyService.getSchemeCounts(taxonomyId),
    })),
  });
  const byScheme = new Map<string, SchemeCountsResponse>();
  for (const result of results) {
    for (const counts of result.data ?? []) byScheme.set(counts.scheme_id, counts);
  }
  return byScheme;
}

/** Individual, property-definition and relationship counts for each class in a scheme. */
export function useClassCounts(schemeId: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.classCounts(schemeId ?? ""),
    queryFn: () => ontologyService.getClassCounts(schemeId as string),
    enabled: !!schemeId,
  });
}
