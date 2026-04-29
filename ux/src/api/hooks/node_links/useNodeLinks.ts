/**
 * Node Links Query Hooks (DEPRECATED - For UI Backward Compatibility)
 *
 * These hooks are deprecated and exist only for backward compatibility.
 * Use entity-specific hooks instead: useRelationships, useRelationship, etc.
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type {
  StructureNodeLink,
  StructureNodeLinkListParams,
} from "../../types/structureNodes";

/**
 * DEPRECATED: Fetch all node links
 */
export const useNodeLinks = (
  params?: StructureNodeLinkListParams,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.RELATIONSHIPS, undefined, params),
    queryFn: async () => {
      console.warn(
        "useNodeLinks is deprecated. Use useRelationships() instead.",
      );
      return [];
    },
    ...options,
  });
};

/**
 * DEPRECATED: Fetch a single page of node links
 */
export const useNodeLinksPage = (
  params?: StructureNodeLinkListParams,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.RELATIONSHIPS, "page", params),
    queryFn: async () => {
      console.warn(
        "useNodeLinksPage is deprecated. Use useRelationships() instead.",
      );
      return [];
    },
    ...options,
  });
};

/**
 * DEPRECATED: Fetch a specific node link by ID
 */
export const useNodeLink = (
  id: string,
  options?: UseQueryOptions<StructureNodeLink, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.RELATIONSHIPS, id),
    queryFn: async () => {
      console.warn(
        "useNodeLink is deprecated. Use useRelationship() instead.",
      );
      throw new Error("useNodeLink is deprecated.");
    },
    enabled: !!id,
    ...options,
  });
};

/**
 * DEPRECATED: Fetch node links by source or target node
 */
export const useNodeLinksByNode = (
  nodeId: string,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.RELATIONSHIPS, "byNode", { nodeId }),
    queryFn: async () => {
      console.warn(
        "useNodeLinksByNode is deprecated. Use useRelationships() instead.",
      );
      return [];
    },
    enabled: !!nodeId,
    ...options,
  });
};
