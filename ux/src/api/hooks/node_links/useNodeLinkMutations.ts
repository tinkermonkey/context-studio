/**
 * Node Link Mutation Hooks (DEPRECATED - For UI Backward Compatibility)
 */

import { UseMutationOptions, useMutation } from "@tanstack/react-query";
import type {
  StructureNodeLink,
  StructureNodeLinkCreate,
} from "../../types/structureNodes";

/**
 * DEPRECATED: Hook to create a node link
 */
export const useCreateNodeLink = (
  options?: UseMutationOptions<StructureNodeLink, Error, StructureNodeLinkCreate>,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn("useCreateNodeLink is deprecated. Use useCreateRelationship() instead.");
      throw new Error("useCreateNodeLink is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Hook to delete a node link
 */
export const useDeleteNodeLink = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  return useMutation({
    mutationFn: async () => {
      console.warn("useDeleteNodeLink is deprecated. Use useDeleteRelationship() instead.");
      throw new Error("useDeleteNodeLink is deprecated.");
    },
    ...options,
  });
};
