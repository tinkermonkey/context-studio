/**
 * Reference Hooks
 *
 * React Query hooks for reference database operations
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  referenceService,
  FilterStatistics,
  ReferenceNode,
  NodeLinksResponse,
  NodeLinksParams,
  PredicateExamplesResponse,
} from "@/api/services/reference";
import { QUERY_KEYS } from "@/api/config";
import { createQueryKey } from "@/api/utils/queryClient";

/**
 * Hook to fetch reference filter statistics
 */
export const useFilterStatistics = (
  options?: UseQueryOptions<FilterStatistics, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.REFERENCE, "filter", { type: "statistics" }),
    queryFn: () => referenceService.getFilterStatistics(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
};

/**
 * Hook to fetch a reference node by ID
 */
export const useReferenceNode = (
  nodeId?: string,
  options?: UseQueryOptions<ReferenceNode, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.REFERENCE, "nodes", { nodeId }),
    queryFn: () => referenceService.getNode(nodeId!),
    enabled: !!nodeId,
    staleTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
};

/**
 * Hook to fetch node links with optional filtering
 */
export const useNodeLinks = (
  nodeId?: string,
  params?: NodeLinksParams,
  options?: UseQueryOptions<NodeLinksResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.REFERENCE, "node-links", {
      nodeId,
      ...params,
    } as Record<string, unknown>),
    queryFn: () => referenceService.getNodeLinks(nodeId!, params),
    enabled: !!nodeId,
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
};

/**
 * Hook to fetch example uses of a predicate
 */
export const usePredicateExamples = (
  source?: string,
  externalId?: string,
  limit: number = 10,
  options?: UseQueryOptions<PredicateExamplesResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.REFERENCE, "predicate-examples", {
      source,
      externalId,
      limit,
    } as Record<string, unknown>),
    queryFn: () => referenceService.getPredicateExamples(source!, externalId!, limit),
    enabled: !!source && !!externalId,
    staleTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
};
