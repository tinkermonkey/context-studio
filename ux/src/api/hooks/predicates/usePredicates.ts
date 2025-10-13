import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  predicateService,
  PredicateListParams,
  PredicateOut,
  PaginatedPredicatesResponse,
  PaginatedExternalPredicatesResponse,
  PredicateDiscoveryStatus,
  FindSimilarResponse,
  ListExternalPredicatesParams,
  FindSimilarParams,
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

/**
 * Hook to fetch external predicates with pagination
 */
export const useExternalPredicates = (
  params?: ListExternalPredicatesParams,
  options?: UseQueryOptions<PaginatedExternalPredicatesResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.PREDICATES,
      "external",
      params as Record<string, unknown>,
    ),
    queryFn: () => predicateService.listExternalPredicates(params),
    staleTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
};

/**
 * Hook to fetch discovery task status
 */
export const useDiscoveryStatus = (
  taskId?: string,
  options?: UseQueryOptions<PredicateDiscoveryStatus, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.PREDICATES, "discover", { taskId }),
    queryFn: () => predicateService.getDiscoveryStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: (data) => {
      // Poll every 2 seconds if task is pending or running
      if (data && (data.status === "pending" || data.status === "running")) {
        return 2000;
      }
      return false;
    },
    ...options,
  });
};

/**
 * Hook to fetch similar predicates for a given predicate
 */
export const useSimilarPredicates = (
  id?: string,
  params?: FindSimilarParams,
  options?: UseQueryOptions<FindSimilarResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.PREDICATES,
      "find-similar",
      { id, ...params } as Record<string, unknown>,
    ),
    queryFn: () => predicateService.findSimilarPredicates(id!, params),
    enabled: !!id,
    staleTime: 60 * 60 * 1000, // 1 hour (results are cached on backend)
    ...options,
  });
};
