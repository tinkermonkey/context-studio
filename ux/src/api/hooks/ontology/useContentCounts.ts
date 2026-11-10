import { useQueries, useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import type { components } from "@/api/types";

type SchemeCountsResponse = components["schemas"]["SchemeCountsResponse"];

/**
 * Class, individual and property-definition counts for each scheme in a
 * taxonomy; individual counts cover one dataset when `datasetId` is given.
 */
export function useSchemeCounts(taxonomyId: string | undefined, datasetId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.schemeCounts(taxonomyId ?? "", datasetId),
    queryFn: () => ontologyService.getSchemeCounts(taxonomyId as string, datasetId),
    enabled: !!taxonomyId,
  });
}

/**
 * Scheme counts for several taxonomies (one request per taxonomy), as a map of
 * scheme id → counts. Pass an empty list to skip. `datasetFor` names the
 * dataset to count a taxonomy's individuals in (all of them when it returns none).
 */
export function useSchemeCountsForTaxonomies(
  taxonomyIds: string[],
  datasetFor?: (taxonomyId: string) => string | undefined,
): Map<string, SchemeCountsResponse> {
  const results = useQueries({
    queries: taxonomyIds.map((taxonomyId) => {
      const datasetId = datasetFor?.(taxonomyId);
      return {
        queryKey: QUERY_KEYS.schemeCounts(taxonomyId, datasetId),
        queryFn: () => ontologyService.getSchemeCounts(taxonomyId, datasetId),
      };
    }),
  });
  const byScheme = new Map<string, SchemeCountsResponse>();
  for (const result of results) {
    for (const counts of result.data ?? []) byScheme.set(counts.scheme_id, counts);
  }
  return byScheme;
}

/**
 * Individual, property-definition and relationship counts for each class in a
 * scheme; individual counts cover one dataset when `datasetId` is given.
 */
export function useClassCounts(schemeId: string | undefined, datasetId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.classCounts(schemeId ?? "", datasetId),
    queryFn: () => ontologyService.getClassCounts(schemeId as string, datasetId),
    enabled: !!schemeId,
  });
}
