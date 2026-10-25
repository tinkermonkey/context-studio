import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";

/** Class, individual and property-definition counts for each scheme in a taxonomy. */
export function useSchemeCounts(taxonomyId: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.schemeCounts(taxonomyId ?? ""),
    queryFn: () => ontologyService.getSchemeCounts(taxonomyId as string),
    enabled: !!taxonomyId,
  });
}

/** Individual, property-definition and relationship counts for each class in a scheme. */
export function useClassCounts(schemeId: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.classCounts(schemeId ?? ""),
    queryFn: () => ontologyService.getClassCounts(schemeId as string),
    enabled: !!schemeId,
  });
}
