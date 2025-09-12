/**
 * Node Links Query Hooks
 *
 * React Query hooks for structure node links (replaces term relationships)
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import { nodeLinkService } from "../../services/nodeLinks";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type { PaginatedResponse } from "../../services/base";
import {
  StructureNodeLink,
  StructureNodeLinkListParams,
} from "../../types/structureNodes";

// Query keys for node links
export const nodeLinkQueryKeys = {
  all: [QUERY_KEYS.NODE_LINKS] as const,
  lists: () => [...nodeLinkQueryKeys.all, "list"] as const,
  list: (params?: StructureNodeLinkListParams) =>
    [...nodeLinkQueryKeys.lists(), params] as const,
  details: () => [...nodeLinkQueryKeys.all, "detail"] as const,
  detail: (id: string) => [...nodeLinkQueryKeys.details(), id] as const,
  byNode: (nodeId: string) =>
    [...nodeLinkQueryKeys.all, "byNode", nodeId] as const,
  fromNode: (nodeId: string) =>
    [...nodeLinkQueryKeys.all, "fromNode", nodeId] as const,
  toNode: (nodeId: string) =>
    [...nodeLinkQueryKeys.all, "toNode", nodeId] as const,
  byPredicate: (predicate: string) =>
    [...nodeLinkQueryKeys.all, "byPredicate", predicate] as const,
  betweenNodes: (sourceId: string, targetId: string) =>
    [...nodeLinkQueryKeys.all, "between", sourceId, targetId] as const,
};

/**
 * Hook to fetch all structure node links
 * Automatically handles pagination to load all data
 */
export const useNodeLinks = (
  params?: StructureNodeLinkListParams,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useQuery({
    queryKey: nodeLinkQueryKeys.list(params),
    queryFn: () => nodeLinkService.list(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to fetch a single page of structure node links
 */
export const useNodeLinksPage = (
  params?: StructureNodeLinkListParams,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NODE_LINKS, "page", params),
    queryFn: () => nodeLinkService.listPage(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to fetch a single page of structure node links with pagination metadata
 */
export const useNodeLinksPageWithMetadata = (
  params?: StructureNodeLinkListParams,
  options?: UseQueryOptions<PaginatedResponse<StructureNodeLink>, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.NODE_LINKS, "page-metadata", params),
    queryFn: () => nodeLinkService.listPageWithMetadata(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to fetch a specific structure node link by ID
 */
export const useNodeLink = (
  id: string,
  options?: UseQueryOptions<StructureNodeLink, Error>,
) => {
  return useQuery({
    queryKey: nodeLinkQueryKeys.detail(id),
    queryFn: () => nodeLinkService.get(id),
    enabled: !!id,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to get all links for a specific node (as source or target)
 */
export const useNodeLinksByNode = (
  nodeId: string,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useQuery({
    queryKey: nodeLinkQueryKeys.byNode(nodeId),
    queryFn: () => nodeLinkService.getNodeLinks(nodeId),
    enabled: !!nodeId,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to get links where the specified node is the source
 */
export const useNodeLinksFromNode = (
  nodeId: string,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useQuery({
    queryKey: nodeLinkQueryKeys.fromNode(nodeId),
    queryFn: () => nodeLinkService.getLinksFromNode(nodeId),
    enabled: !!nodeId,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to get links where the specified node is the target
 */
export const useNodeLinksToNode = (
  nodeId: string,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useQuery({
    queryKey: nodeLinkQueryKeys.toNode(nodeId),
    queryFn: () => nodeLinkService.getLinksToNode(nodeId),
    enabled: !!nodeId,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to get links by predicate
 */
export const useNodeLinksByPredicate = (
  predicate: string,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useQuery({
    queryKey: nodeLinkQueryKeys.byPredicate(predicate),
    queryFn: () => nodeLinkService.getLinksByPredicate(predicate),
    enabled: !!predicate.trim(),
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

/**
 * Hook to get links between two specific nodes
 */
export const useNodeLinksBetweenNodes = (
  sourceId: string,
  targetId: string,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useQuery({
    queryKey: nodeLinkQueryKeys.betweenNodes(sourceId, targetId),
    queryFn: () => nodeLinkService.getLinksBetweenNodes(sourceId, targetId),
    enabled: !!sourceId && !!targetId,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    ...options,
  });
};

// Legacy compatibility hooks for term relationships

/**
 * Hook to get term relationships (backward compatibility wrapper)
 * @deprecated Use useNodeLinks instead
 */
export const useTermRelationships = (
  params?: {
    skip?: number;
    limit?: number;
    source_term_id?: string;
    target_term_id?: string;
    predicate?: string;
  },
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  const queryParams: StructureNodeLinkListParams = {};

  if (params?.skip !== undefined) queryParams.skip = params.skip;
  if (params?.limit !== undefined) queryParams.limit = params.limit;
  if (params?.source_term_id)
    queryParams.source_node_id = params.source_term_id;
  if (params?.target_term_id)
    queryParams.target_node_id = params.target_term_id;
  if (params?.predicate) queryParams.predicate = params.predicate;

  return useNodeLinks(queryParams, options);
};

/**
 * Hook to get term relationships for a specific term (backward compatibility wrapper)
 * @deprecated Use useNodeLinksByNode instead
 */
export const useTermRelationshipsByTerm = (
  termId: string,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useNodeLinksByNode(termId, options);
};

/**
 * Hook to get term relationships by predicate (backward compatibility wrapper)
 * @deprecated Use useNodeLinksByPredicate instead
 */
export const useTermRelationshipsByPredicate = (
  predicate: string,
  options?: UseQueryOptions<StructureNodeLink[], Error>,
) => {
  return useNodeLinksByPredicate(predicate, options);
};
