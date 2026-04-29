/**
 * Node Attributes Hooks (DEPRECATED - For UI Backward Compatibility)
 */

import {
  useQuery,
  useMutation,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import type {
  ResolvedAttribute,
  StructureNodeAttribute,
  StructureNode,
} from "../../types/structureNodes";

/**
 * DEPRECATED: Get resolved attributes for a node
 */
export const useNodeAttributes = (
  nodeId: string,
  options?: UseQueryOptions<ResolvedAttribute[], Error>,
) => {
  return useQuery({
    queryKey: ["node_attributes", nodeId],
    queryFn: async () => {
      console.warn("useNodeAttributes is deprecated.");
      return [];
    },
    enabled: !!nodeId,
    ...options,
  });
};

/**
 * DEPRECATED: Set node attributes
 */
export const useSetNodeAttributes = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { nodeId: string; attributes: StructureNodeAttribute[] }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      throw new Error("useSetNodeAttributes is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Remove node attribute
 */
export const useRemoveNodeAttribute = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { nodeId: string; key: string }
  >,
) => {
  return useMutation({
    mutationFn: async () => {
      throw new Error("useRemoveNodeAttribute is deprecated.");
    },
    ...options,
  });
};

/**
 * DEPRECATED: Batch mutations for node attributes
 */
export const useNodeAttributeMutations = (nodeId: string) => {
  return {
    setAttributes: useSetNodeAttributes(),
    removeAttribute: useRemoveNodeAttribute(),
  };
};
