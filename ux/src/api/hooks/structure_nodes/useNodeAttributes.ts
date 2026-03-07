/**
 * Node Attributes Query and Mutation Hooks
 *
 * React Query hooks for fetching and mutating structure node attributes
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import { structureNodeService } from "../../services/structureNodes";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type {
  StructureNodeAttribute,
  ResolvedAttribute,
  StructureNode,
} from "../../types/structureNodes";

/**
 * Hook to fetch resolved attributes (local + inherited) for a structure node
 */
export const useNodeAttributes = (
  nodeId: string | undefined,
  options?: UseQueryOptions<ResolvedAttribute[], Error>,
) => {
  return useQuery({
    queryKey: [
      ...(createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "attributes") as string[]),
      nodeId,
    ] as const,
    queryFn: () => {
      if (!nodeId) {
        return Promise.resolve([]);
      }
      return structureNodeService.getNodeAttributes(nodeId);
    },
    enabled: !!nodeId,
    ...options,
  });
};

/**
 * Hook to get mutation functions for managing node attributes
 */
export const useNodeAttributeMutations = (
  nodeId: string,
  options?: {
    setAttributesOptions?: UseMutationOptions<
      StructureNode,
      Error,
      StructureNodeAttribute[]
    >;
    removeAttributeOptions?: UseMutationOptions<StructureNode, Error, string>;
  },
) => {
  const queryClient = useQueryClient();

  const setAttributesMutation = useMutation({
    mutationFn: (attributes: StructureNodeAttribute[]) =>
      structureNodeService.setNodeAttributes(nodeId, attributes),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          ...(createQueryKey(
            QUERY_KEYS.STRUCTURE_NODES,
            "attributes",
          ) as string[]),
          nodeId,
        ],
      });
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId),
      });
    },
    ...options?.setAttributesOptions,
  });

  const removeAttributeMutation = useMutation({
    mutationFn: (key: string) =>
      structureNodeService.removeNodeAttribute(nodeId, key),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          ...(createQueryKey(
            QUERY_KEYS.STRUCTURE_NODES,
            "attributes",
          ) as string[]),
          nodeId,
        ],
      });
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, nodeId),
      });
    },
    ...options?.removeAttributeOptions,
  });

  return {
    setAttributesMutation,
    removeAttributeMutation,
  };
};
