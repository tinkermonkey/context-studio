import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query';
import { predicateService, PredicateOut, PredicateCreate, PredicateUpdate } from '@/api/services/predicates';
import { QUERY_KEYS } from '@/api/config';
import { createQueryKey } from '@/api/utils/queryClient';

/**
 * Hook to create a new predicate
 */
export const useCreatePredicate = (
  options?: UseMutationOptions<PredicateOut, Error, PredicateCreate>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: PredicateCreate) => predicateService.create(data),
    onSuccess: (newPredicate) => {
      // Invalidate predicates list
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES)
      });
      
      // Set the new predicate in cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.PREDICATES, newPredicate.id),
        newPredicate
      );
    },
    onError: (error) => {
      console.error('Error creating predicate:', error);
    },
    ...options,
  });
};

/**
 * Hook to update a predicate
 */
export const useUpdatePredicate = (
  options?: UseMutationOptions<PredicateOut, Error, { id: string; data: PredicateUpdate }>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PredicateUpdate }) => 
      predicateService.update(id, data),
    onSuccess: (updatedPredicate) => {
      // Invalidate predicates list
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES)
      });
      
      // Update the predicate in cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.PREDICATES, updatedPredicate.id),
        updatedPredicate
      );
    },
    onError: (error) => {
      console.error('Error updating predicate:', error);
    },
    ...options,
  });
};

/**
 * Hook to delete a predicate
 */
export const useDeletePredicate = (
  options?: UseMutationOptions<void, Error, string>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => predicateService.delete(id),
    onSuccess: (_, deletedId) => {
      // Invalidate predicates list
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES)
      });
      
      // Remove from cache
      queryClient.removeQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES, deletedId)
      });
    },
    onError: (error) => {
      console.error('Error deleting predicate:', error);
    },
    ...options,
  });
};

/**
 * Hook to import predicates from ConceptNet
 */
export const useImportFromConceptNet = (
  options?: UseMutationOptions<PredicateOut[], Error, string[] | undefined>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (relations?: string[]) => predicateService.importFromConceptNet(relations),
    onSuccess: () => {
      // Invalidate predicates list and related queries
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PREDICATES)
      });
    },
    onError: (error) => {
      console.error('Error importing predicates from ConceptNet:', error);
    },
    ...options,
  });
};
