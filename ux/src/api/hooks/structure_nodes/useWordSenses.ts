/**
 * Word Senses Query and Mutation Hooks
 *
 * React Query hooks for managing word sense selections on structure nodes
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import { structureNodeService } from "@/api/services/structureNodes";
import { QUERY_KEYS } from "@/api/config";
import { createQueryKey } from "@/api/utils/queryClient";
import { WordSense, SelectedWordSensesUpdate } from "@/api/types/structureNodes";
import { handleVersionConflict, isVersionConflict } from "@/api/utils/conflictResolution";
import { toast } from "@/utils/toast";

/**
 * Hook to fetch word senses for a structure node
 */
export const useWordSenses = (
  nodeId: string,
  options?: UseQueryOptions<WordSense[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "word_senses" }),
    queryFn: () => structureNodeService.getWordSenses(nodeId),
    enabled: !!nodeId,
    ...options,
  });
};

// Context type for optimistic updates
interface WordSenseContext {
  previousWordSenses: WordSense[] | undefined;
}

/**
 * Hook to update word senses for a structure node
 * Supports optimistic updates for immediate UI feedback
 */
export const useUpdateWordSenses = (
  nodeId: string,
  options?: UseMutationOptions<
    WordSense[],
    Error,
    SelectedWordSensesUpdate,
    WordSenseContext
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation<WordSense[], Error, SelectedWordSensesUpdate, WordSenseContext>({
    mutationFn: (data: SelectedWordSensesUpdate) =>
      structureNodeService.updateWordSenses(nodeId, data),
    onMutate: async (
      variables: SelectedWordSensesUpdate,
    ): Promise<WordSenseContext> => {
      // Cancel any outgoing refetches to avoid optimistic update being overwritten
      const queryKey = createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "word_senses" });
      await queryClient.cancelQueries({
        queryKey,
      });

      // Snapshot the previous value for rollback
      const previousWordSenses = queryClient.getQueryData<WordSense[]>(queryKey);

      // Optimistically update to the new value
      queryClient.setQueryData(queryKey, variables.selected_senses);

      return { previousWordSenses };
    },
    onError: async (err, variables, context) => {
      // Check if this is a version conflict
      if (isVersionConflict(err)) {
        const queryKey = createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "word_senses" });

        // Handle conflict with automatic refetch
        await handleVersionConflict(
          err,
          async () => {
            const freshData = await structureNodeService.getWordSenses(nodeId);
            queryClient.setQueryData(queryKey, freshData);
            return freshData;
          },
          {
            customMessage: "Word senses were modified elsewhere. Your changes were not saved. Please review the current values and try again.",
            showToast: true,
          }
        );
      } else {
        // Rollback to the previous value on other errors
        if (context?.previousWordSenses) {
          queryClient.setQueryData(
            createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "word_senses" }),
            context.previousWordSenses,
          );
        }

        // Show error toast
        toast.error(`Failed to update word senses: ${err.message}`);
      }
    },
    onSuccess: (data) => {
      // Update the cache with the server response
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "word_senses" }),
        data,
      );

      // Invalidate only the specific node's detail query to refresh the full node data
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId),
      });
    },
    ...options,
  });
};
