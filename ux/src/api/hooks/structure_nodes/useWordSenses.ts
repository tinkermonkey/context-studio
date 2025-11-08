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

/**
 * Hook to update word senses for a structure node
 * Supports optimistic updates for immediate UI feedback
 */
export const useUpdateWordSenses = (
  nodeId: string,
  options?: UseMutationOptions<
    WordSense[],
    Error,
    SelectedWordSensesUpdate
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SelectedWordSensesUpdate) =>
      structureNodeService.updateWordSenses(nodeId, data),
    onMutate: async (
      variables: SelectedWordSensesUpdate,
    ): Promise<{ previousWordSenses: WordSense[] | undefined }> => {
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
    onError: (err, variables, context) => {
      // Rollback to the previous value on error
      const ctx = context as { previousWordSenses?: WordSense[] };
      if (ctx?.previousWordSenses) {
        queryClient.setQueryData(
          createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "word_senses" }),
          ctx.previousWordSenses,
        );
      }
    },
    onSuccess: (data) => {
      // Update the cache with the server response
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId, { type: "word_senses" }),
        data,
      );

      // Invalidate the structure node detail query to refresh the full node data
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId),
      });
    },
    ...options,
  });
};
