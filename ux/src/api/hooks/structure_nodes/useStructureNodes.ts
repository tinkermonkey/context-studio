/**
 * Structure Nodes Query Hooks
 *
 * React Query hooks for unified structure node entities (layers, domains, terms)
 */

import { useQuery, useQueryClient, UseQueryOptions } from "@tanstack/react-query";
import { structureNodeService } from "../../services/structureNodes";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type { PaginatedResponse } from "../../services/base";
import {
  StructureNode,
  StructureNodeListParams,
  StructureNodeFindParams,
  FindStructureNodeResult,
  NodeType,
} from "../../types/structureNodes";

/**
 * Hook to fetch all structure nodes
 * Automatically handles pagination to load all data
 */
export const useStructureNodes = (
  params?: StructureNodeListParams,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, undefined, params),
    queryFn: () => structureNodeService.list(params),
    ...options,
  });
};

/**
 * Hook to fetch a single page of structure nodes
 */
export const useStructureNodesPage = (
  params?: StructureNodeListParams,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "page", params),
    queryFn: () => structureNodeService.listPage(params),
    ...options,
  });
};

/**
 * Hook to fetch a single page of structure nodes with pagination metadata
 */
export const useStructureNodesPageWithMetadata = (
  params?: StructureNodeListParams,
  options?: UseQueryOptions<PaginatedResponse<StructureNode>, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.STRUCTURE_NODES,
      "page-metadata",
      params,
    ),
    queryFn: () => structureNodeService.listPageWithMetadata(params),
    ...options,
  });
};

/**
 * Hook to fetch a specific structure node by ID
 */
export const useStructureNode = (
  id: string,
  options?: UseQueryOptions<StructureNode, Error>,
) => {
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, id),
    queryFn: () => structureNodeService.get(id),
    enabled: !!id,
    // Try to find this node in any of the list caches before fetching
    initialData: () => {
      // Check all type-based list queries
      const nodeTypes = [NodeType.LAYER, NodeType.DOMAIN, NodeType.TERM];
      for (const nodeType of nodeTypes) {
        const listData = queryClient.getQueryData<StructureNode[]>(
          createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "type", { nodeType })
        );
        if (listData) {
          const node = listData.find(n => n.id === id);
          if (node) {
            return node;
          }
        }
      }
      return undefined;
    },
    ...options,
  });
};

/**
 * Hook to fetch structure nodes by type
 */
export const useStructureNodesByType = (
  nodeType: NodeType,
  params?: Omit<StructureNodeListParams, "node_type">,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "type", {
      nodeType,
      ...params,
    }),
    queryFn: () =>
      structureNodeService.list({ ...params, node_type: nodeType }),
    ...options,
  });
};

/**
 * Hook to fetch structure nodes by parent
 */
export const useStructureNodesByParent = (
  parentId: string,
  nodeType?: NodeType,
  params?: Omit<StructureNodeListParams, "parent_node_id" | "node_type">,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, "parent", {
      parentId,
      nodeType,
      ...params,
    }),
    queryFn: () =>
      structureNodeService.list({
        ...params,
        parent_node_id: parentId,
        node_type: nodeType,
      }),
    enabled: !!parentId,
    ...options,
  });
};

/**
 * Hook to search structure nodes
 */
export const useStructureNodeSearch = (
  params: StructureNodeFindParams,
  options?: UseQueryOptions<FindStructureNodeResult[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.FIND,
      QUERY_KEYS.STRUCTURE_NODES,
      params,
    ),
    queryFn: () => structureNodeService.find(params),
    enabled: !!params.query,
    ...options,
  });
};

// Convenience hooks for specific node types

/**
 * Hook to fetch all layers
 */
export const useLayerNodes = (
  params?: Omit<StructureNodeListParams, "node_type">,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useStructureNodesByType(NodeType.LAYER, params, options);
};

/**
 * Hook to fetch domains, optionally filtered by parent layer
 */
export const useDomainNodes = (
  layerId?: string,
  params?: Omit<StructureNodeListParams, "node_type" | "parent_node_id">,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  if (layerId) {
    return useStructureNodesByParent(layerId, NodeType.DOMAIN, params, options);
  }
  return useStructureNodesByType(NodeType.DOMAIN, params, options);
};

/**
 * Hook to fetch terms, optionally filtered by parent (domain or term)
 */
export const useTermNodes = (
  parentId?: string,
  params?: Omit<StructureNodeListParams, "node_type" | "parent_node_id">,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  if (parentId) {
    return useStructureNodesByParent(parentId, NodeType.TERM, params, options);
  }
  return useStructureNodesByType(NodeType.TERM, params, options);
};

/**
 * Hook to get child nodes of a specific parent
 */
export const useChildNodes = (
  parentId: string,
  nodeType?: NodeType,
  params?: Omit<StructureNodeListParams, "parent_node_id" | "node_type">,
  options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return useStructureNodesByParent(parentId, nodeType, params, options);
};

// Type-specific search hooks

/**
 * Hook to search layers
 */
export const useLayerSearch = (
  params: Omit<StructureNodeFindParams, "node_type"> & { query: string },
  options?: UseQueryOptions<FindStructureNodeResult[], Error>,
) => {
  return useStructureNodeSearch(
    { ...params, node_type: NodeType.LAYER },
    options,
  );
};

/**
 * Hook to search domains
 */
export const useDomainSearch = (
  params: Omit<StructureNodeFindParams, "node_type"> & { query: string },
  options?: UseQueryOptions<FindStructureNodeResult[], Error>,
) => {
  return useStructureNodeSearch(
    { ...params, node_type: NodeType.DOMAIN },
    options,
  );
};

/**
 * Hook to search terms
 */
export const useTermSearch = (
  params: Omit<StructureNodeFindParams, "node_type"> & { query: string },
  options?: UseQueryOptions<FindStructureNodeResult[], Error>,
) => {
  return useStructureNodeSearch(
    { ...params, node_type: NodeType.TERM },
    options,
  );
};
