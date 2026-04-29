/**
 * Word Senses Hooks (DEPRECATED - For UI Backward Compatibility)
 */

import {
  useQuery,
  useMutation,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import type {
  WordSense,
  SelectedWordSensesUpdate,
} from "../../types/structureNodes";

/**
 * DEPRECATED: Get word senses for a node
 */
export const useWordSenses = (
  nodeId: string,
  options?: UseQueryOptions<WordSense[], Error>,
) => {
  return useQuery({
    queryKey: ["word_senses", nodeId],
    queryFn: async () => {
      console.warn("useWordSenses is deprecated.");
      return [];
    },
    enabled: !!nodeId,
    ...options,
  });
};

/**
 * DEPRECATED: Update word senses
 */
export const useUpdateWordSenses = (
  options?: UseMutationOptions<
    WordSense[],
    Error,
    { nodeId: string; data: SelectedWordSensesUpdate }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      throw new Error("useUpdateWordSenses is deprecated.");
    },
    ...options,
  });
};
