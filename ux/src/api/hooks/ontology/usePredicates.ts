import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ontologyService } from "@/api/services/ontology";
import { listQueryOptions } from "./listQueryOptions";
import { uniqueIds } from "./idChunks";

/** The predicates with these ids (any taxonomy); skipped when there are none. */
export function usePredicatesByIds(ids: Array<string | null | undefined>) {
  const unique = uniqueIds(ids);
  return useQuery({
    queryKey: [...QUERY_KEYS.predicates, unique],
    queryFn: () => ontologyService.listPredicatesByIds(unique),
    ...listQueryOptions({ enabled: unique.length > 0, keepPrevious: true }),
  });
}

/** A taxonomy's predicate catalog; skipped without a taxonomy id. */
export function useTaxonomyPredicates(taxonomyId: string | null | undefined) {
  return useQuery({
    queryKey: [...QUERY_KEYS.predicates, "taxonomy", taxonomyId],
    queryFn: () => ontologyService.listTaxonomyPredicates(taxonomyId!),
    ...listQueryOptions({ enabled: !!taxonomyId }),
  });
}
