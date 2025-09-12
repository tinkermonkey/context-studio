import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  predicateService,
  PredicateListParams,
  PredicateOut,
  PaginatedPredicatesResponse,
} from "@/api/services/predicates";
import { QUERY_KEYS } from "@/api/config";
import { createQueryKey } from "@/api/utils/queryClient";

/**
 * Hook to fetch paginated predicates
 */
export const usePredicates = (
  params?: PredicateListParams,
  options?: UseQueryOptions<PaginatedPredicatesResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.PREDICATES,
      undefined,
      params as Record<string, unknown>,
    ),
    queryFn: () => predicateService.list(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
};

/**
 * Hook to fetch a single predicate by ID
 */
export const usePredicate = (
  id?: string,
  options?: UseQueryOptions<PredicateOut, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.PREDICATES, id),
    queryFn: () => predicateService.get(id!),
    enabled: !!id,
    ...options,
  });
};

/**
 * Hook to fetch predicate by identifier
 */
export const usePredicateByIdentifier = (
  identifier?: string,
  options?: UseQueryOptions<PredicateOut, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.PREDICATES, "by-identifier", {
      identifier,
    }),
    queryFn: () => predicateService.getByIdentifier(identifier!),
    enabled: !!identifier,
    ...options,
  });
};

/**
 * Hook to fetch ConceptNet relations
 */
export const useConceptNetRelations = (
  options?: UseQueryOptions<string[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.PREDICATES, "conceptnet-relations"),
    queryFn: () => predicateService.getConceptNetRelations(),
    staleTime: 30 * 60 * 1000, // 30 minutes
    ...options,
  });
};

/**
 * Hook to fetch ConceptNet mapping
 */
export const useConceptNetMapping = (
  options?: UseQueryOptions<Record<string, string>, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.PREDICATES, "conceptnet-mapping"),
    queryFn: () => predicateService.getConceptNetMapping(),
    staleTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
};

/**
 * Hook to fetch ConceptNet relation for a predicate
 */
export const usePredicateConceptNetRelation = (
  id?: string,
  options?: UseQueryOptions<string | null, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.PREDICATES, "conceptnet-relation", {
      id,
    }),
    queryFn: () => predicateService.getConceptNetRelation(id!),
    enabled: !!id,
    ...options,
  });
};
