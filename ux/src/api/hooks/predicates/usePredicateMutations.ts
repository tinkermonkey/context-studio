import {
  useMutation,
  useQueryClient,
  UseMutationOptions,
} from "@tanstack/react-query";
import {
  predicateService,
  PredicateOut,
  PredicateCreate,
  PredicateUpdate,
  PredicateDiscoveryResponse,
  ClusterPredicatesResponse,
  ClusterPredicatesParams,
  DiscoverPredicatesParams,
} from "@/api/services/predicates";
import { QUERY_KEYS } from "@/api/config";
import { createQueryKey } from "@/api/utils/queryClient";

/**
 * Hook to create a new predicate
 */
export const useCreatePredicate = (
  options?: UseMutationOptions<PredicateOut, Error, PredicateCreate>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: PredicateCreate) => predicateService.create(data),
    onSuccess: (newPredicate) => {
      // Invalidate predicates list
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES),
      });

      // Set the new predicate in cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.PREDICATES, newPredicate.id),
        newPredicate,
      );
    },
    onError: (error) => {
      console.error("Error creating predicate:", error);
    },
    ...options,
  });
};

/**
 * Hook to update a predicate
 */
export const useUpdatePredicate = (
  options?: UseMutationOptions<
    PredicateOut,
    Error,
    { id: string; data: PredicateUpdate }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PredicateUpdate }) =>
      predicateService.update(id, data),
    onSuccess: (updatedPredicate) => {
      // Invalidate predicates list
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES),
      });

      // Update the predicate in cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.PREDICATES, updatedPredicate.id),
        updatedPredicate,
      );
    },
    onError: (error) => {
      console.error("Error updating predicate:", error);
    },
    ...options,
  });
};

/**
 * Hook to delete a predicate
 */
export const useDeletePredicate = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => predicateService.delete(id),
    onSuccess: (_, deletedId) => {
      // Invalidate predicates list
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES),
      });

      // Remove from cache
      queryClient.removeQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES, deletedId),
      });
    },
    onError: (error) => {
      console.error("Error deleting predicate:", error);
    },
    ...options,
  });
};

/**
 * Hook to import predicates from ConceptNet
 */
export const useImportFromConceptNet = (
  options?: UseMutationOptions<PredicateOut[], Error, string[] | undefined>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (relations?: string[]) =>
      predicateService.importFromConceptNet(relations),
    onSuccess: () => {
      // Invalidate predicates list and related queries
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES),
      });
    },
    onError: (error) => {
      console.error("Error importing predicates from ConceptNet:", error);
    },
    ...options,
  });
};

/**
 * Hook to discover predicates from external sources
 */
export const useDiscoverPredicates = (
  options?: UseMutationOptions<
    PredicateDiscoveryResponse,
    Error,
    DiscoverPredicatesParams | undefined
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params?: DiscoverPredicatesParams) =>
      predicateService.discoverPredicates(params),
    onSuccess: () => {
      // Invalidate external predicates queries
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES, "external"),
      });
    },
    onError: (error) => {
      console.error("Error discovering predicates:", error);
    },
    ...options,
  });
};

/**
 * Hook to cluster predicates
 */
export const useClusterPredicates = (
  options?: UseMutationOptions<
    ClusterPredicatesResponse,
    Error,
    ClusterPredicatesParams | undefined
  >,
) => {
  return useMutation({
    mutationFn: (params?: ClusterPredicatesParams) =>
      predicateService.clusterPredicates(params),
    onError: (error) => {
      console.error("Error clustering predicates:", error);
    },
    ...options,
  });
};

/**
 * Hook to invalidate similarity cache
 */
export const useInvalidateSimilarityCache = (
  options?: UseMutationOptions<
    { success: boolean; message: string; cache_entries_cleared: number },
    Error,
    void
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => predicateService.invalidateSimilarityCache(),
    onSuccess: () => {
      // Invalidate all find-similar queries
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES, "find-similar"),
      });
    },
    onError: (error) => {
      console.error("Error invalidating similarity cache:", error);
    },
    ...options,
  });
};
