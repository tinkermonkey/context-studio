/**
 * Structure Nodes Mutation Hooks
 *
 * React Query mutation hooks for structure node entities (layers, domains, terms)
 */

import {
  useMutation,
  useQueryClient,
  UseMutationOptions,
} from "@tanstack/react-query";
import { structureNodeService } from "@/api/services/structureNodes";
import { QUERY_KEYS } from "@/api/config";
import { createQueryKey } from "@/api/utils/queryClient";
import {
  StructureNode,
  StructureNodeCreate,
  StructureNodeUpdate,
  NodeType,
  MoveNodesRequest,
  MoveNodesResponse,
} from "@/api/types/structureNodes";

/**
 * Hook to create a new structure node
 */
export const useCreateStructureNode = (
  options?: UseMutationOptions<StructureNode, Error, StructureNodeCreate>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: StructureNodeCreate) =>
      structureNodeService.create(data),
    onSuccess: (data) => {
      // Update the structure nodes list cache
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES],
      });

      // Add the new node to the cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, data.id),
        data,
      );

      // Invalidate type-specific and parent-specific queries
      if (data.parent_node_id) {
        queryClient.invalidateQueries({
          queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "parent", {
            parentId: data.parent_node_id,
          }),
        });
      }

      // Invalidate type-specific queries
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "type", {
          nodeType: data.node_type,
        }),
      });
    },
    ...options,
  });
};

/**
 * Hook to update an existing structure node
 */
export const useUpdateStructureNode = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { id: string; data: StructureNodeUpdate }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: StructureNodeUpdate }) =>
      structureNodeService.update(id, data),
    onSuccess: (data, variables) => {
      // Update the specific node in cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, variables.id),
        data,
      );

      // Invalidate the structure nodes list to refresh it
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES],
      });

      // If parent changed, invalidate old and new parent queries
      const oldNode = queryClient.getQueryData<StructureNode>(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, variables.id),
      );

      if (oldNode?.parent_node_id !== data.parent_node_id) {
        // Invalidate old parent queries
        if (oldNode?.parent_node_id) {
          queryClient.invalidateQueries({
            queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "parent", {
              parentId: oldNode.parent_node_id,
            }),
          });
        }

        // Invalidate new parent queries
        if (data.parent_node_id) {
          queryClient.invalidateQueries({
            queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "parent", {
              parentId: data.parent_node_id,
            }),
          });
        }
      }

      // Invalidate type-specific queries
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "type", {
          nodeType: data.node_type,
        }),
      });
    },
    ...options,
  });
};

/**
 * Hook to delete a structure node
 */
export const useDeleteStructureNode = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => structureNodeService.delete(id),
    onMutate: async (id: string) => {
      // Get the node being deleted for cache invalidation
      const nodeToDelete = queryClient.getQueryData<StructureNode>(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, id),
      );

      return { nodeToDelete };
    },
    onSuccess: (_, id, context) => {
      // Remove the node from cache
      queryClient.removeQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, id),
      });

      // Invalidate the structure nodes list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES],
      });

      const contextData = context as { nodeToDelete?: StructureNode };

      // Invalidate parent-specific queries if the deleted node had a parent
      if (contextData?.nodeToDelete?.parent_node_id) {
        queryClient.invalidateQueries({
          queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "parent", {
            parentId: contextData.nodeToDelete.parent_node_id,
          }),
        });
      }

      // Invalidate type-specific queries
      if (contextData?.nodeToDelete?.node_type) {
        queryClient.invalidateQueries({
          queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "type", {
            nodeType: contextData.nodeToDelete.node_type,
          }),
        });
      }

      // Cascade invalidation - invalidate queries for child nodes
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "parent", {
          parentId: id,
        }),
      });

      // Invalidate node links that might reference this node
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.NODE_LINKS],
      });
    },
    ...options,
  });
};

// Convenience mutation hooks for specific node types

/**
 * Hook to create a layer
 */
export const useCreateLayer = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    Omit<StructureNodeCreate, "node_type" | "parent_node_id">
  >,
) => {
  const createStructureNode = useCreateStructureNode();

  return useMutation({
    mutationFn: (
      data: Omit<StructureNodeCreate, "node_type" | "parent_node_id">,
    ) =>
      createStructureNode.mutateAsync({
        ...data,
        node_type: NodeType.LAYER,
        // parent_node_id is omitted for layers
      }),
    ...options,
  });
};

/**
 * Hook to create a domain
 */
export const useCreateDomain = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    {
      layerId: string;
      data: Omit<StructureNodeCreate, "node_type" | "parent_node_id">;
    }
  >,
) => {
  const createStructureNode = useCreateStructureNode();

  return useMutation({
    mutationFn: ({
      layerId,
      data,
    }: {
      layerId: string;
      data: Omit<StructureNodeCreate, "node_type" | "parent_node_id">;
    }) =>
      createStructureNode.mutateAsync({
        ...data,
        node_type: NodeType.DOMAIN,
        parent_node_id: layerId,
      }),
    ...options,
  });
};

/**
 * Hook to create a term
 */
export const useCreateTerm = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    {
      parentId: string;
      data: Omit<StructureNodeCreate, "node_type" | "parent_node_id">;
    }
  >,
) => {
  const createStructureNode = useCreateStructureNode();

  return useMutation({
    mutationFn: ({
      parentId,
      data,
    }: {
      parentId: string;
      data: Omit<StructureNodeCreate, "node_type" | "parent_node_id">;
    }) =>
      createStructureNode.mutateAsync({
        ...data,
        node_type: NodeType.TERM,
        parent_node_id: parentId,
      }),
    ...options,
  });
};

/**
 * Hook to update a layer
 */
export const useUpdateLayer = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { id: string; data: Omit<StructureNodeUpdate, "parent_node_id"> }
  >,
) => {
  const updateStructureNode = useUpdateStructureNode();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: Omit<StructureNodeUpdate, "parent_node_id">;
    }) => updateStructureNode.mutateAsync({ id, data }),
    ...options,
  });
};

/**
 * Hook to update a domain
 */
export const useUpdateDomain = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { id: string; data: StructureNodeUpdate }
  >,
) => {
  const updateStructureNode = useUpdateStructureNode();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: StructureNodeUpdate }) =>
      updateStructureNode.mutateAsync({ id, data }),
    ...options,
  });
};

/**
 * Hook to update a term
 */
export const useUpdateTerm = (
  options?: UseMutationOptions<
    StructureNode,
    Error,
    { id: string; data: StructureNodeUpdate }
  >,
) => {
  const updateStructureNode = useUpdateStructureNode();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: StructureNodeUpdate }) =>
      updateStructureNode.mutateAsync({ id, data }),
    ...options,
  });
};

/**
 * Hook to move structure nodes with automatic type conversion
 */
export const useMoveStructureNodes = (
  options?: UseMutationOptions<MoveNodesResponse, Error, MoveNodesRequest>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: MoveNodesRequest) =>
      structureNodeService.move(request),
    onSuccess: (data) => {
      // Invalidate all structure node queries to refresh the UI
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES],
      });

      // Invalidate type-specific queries for all affected types
      [NodeType.LAYER, NodeType.DOMAIN, NodeType.TERM].forEach((nodeType) => {
        queryClient.invalidateQueries({
          queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "type", {
            nodeType,
          }),
        });
      });

      // Collect all unique parent IDs from moved, updated, and converted nodes
      const allNodes = [
        ...data.moved_nodes,
        ...data.updated_children,
        ...data.converted_nodes,
      ];
      const parentIds = new Set<string>();

      allNodes.forEach((node) => {
        if (node.parent_node_id) {
          parentIds.add(node.parent_node_id);
        }
      });

      // Invalidate parent-specific queries
      parentIds.forEach((parentId) => {
        queryClient.invalidateQueries({
          queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "parent", {
            parentId,
          }),
        });
      });
    },
    ...options,
  });
};
