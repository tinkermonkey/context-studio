/**
 * Unified Reference Query Hooks
 *
 * React Query hooks for unified reference search across multiple sources
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import { unifiedReferenceService } from "../../services/unifiedReference";
import {
  UnifiedSearchRequest,
  UnifiedSearchResponse,
  UnifiedNode,
  UnifiedLink,
  UnifiedReferenceError,
  SourceType,
} from "../../types/unified";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

// Add unified reference to query keys
const UNIFIED_QUERY_KEYS = {
  ...QUERY_KEYS,
  UNIFIED_REFERENCE: "unified-reference",
} as const;

/**
 * Hook for unified search across all reference sources
 * Uses mutation pattern for immediate search execution
 */
export const useUnifiedSearch = (
  options?: UseMutationOptions<
    UnifiedSearchResponse,
    Error,
    UnifiedSearchRequest
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: UnifiedSearchRequest) =>
      unifiedReferenceService.search(request),
    onSuccess: (data, variables) => {
      // Cache the search results
      queryClient.setQueryData(
        createQueryKey(
          UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE,
          "search",
          variables as unknown as Record<string, unknown>,
        ),
        data,
      );

      // Cache individual nodes for faster access
      data.results.forEach((node) => {
        queryClient.setQueryData(
          createQueryKey(UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE, "node", {
            nodeId: node.id,
          }),
          node,
        );
      });
    },
    onError: (error: Error) => {
      console.error("Unified search failed:", error);
    },
    ...options,
  });
};

/**
 * Hook to get cached search results
 */
export const useUnifiedSearchResults = (
  request: UnifiedSearchRequest | null,
  options?: UseQueryOptions<UnifiedSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE,
      "search",
      request as unknown as Record<string, unknown>,
    ),
    queryFn: () => {
      if (!request) throw new Error("Request is required");
      return unifiedReferenceService.search(request);
    },
    enabled: !!request && !!request.query?.trim(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
};

/**
 * Hook to get detailed information about a specific node
 */
export const useNodeDetails = (
  nodeId: string | null,
  options?: UseQueryOptions<UnifiedNode, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE, "node", {
      nodeId,
    }),
    queryFn: () => {
      if (!nodeId) throw new Error("Node ID is required");
      return unifiedReferenceService.getNode(nodeId);
    },
    enabled: !!nodeId,
    staleTime: 10 * 60 * 1000, // 10 minutes - node details change less frequently
    ...options,
  });
};

/**
 * Hook to get links for a specific node
 */
export const useNodeLinks = (
  nodeId: string | null,
  direction: "from" | "to" | "both" = "both",
  options?: UseQueryOptions<UnifiedLink[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE, "links", {
      nodeId,
      direction,
    }),
    queryFn: () =>
      nodeId ? unifiedReferenceService.getLinks(nodeId, direction) : [],
    enabled: !!nodeId,
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
};



/**
 * Hook for paginated search with load more functionality
 */
export const usePaginatedSearch = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      request,
      cursor,
    }: {
      request: UnifiedSearchRequest;
      cursor?: string;
    }) => unifiedReferenceService.searchPaginated(request, cursor),
    onSuccess: (data, variables) => {
      // Update the search results in cache
      const queryKey = createQueryKey(
        UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE,
        "search",
        variables.request as unknown as Record<string, unknown>,
      );

      queryClient.setQueryData(
        queryKey,
        (oldData: UnifiedSearchResponse | undefined) => {
          if (!oldData || !variables.cursor) {
            // First page or reset
            return data;
          }

          // Append new results to existing ones
          return {
            ...data,
            results: [...oldData.results, ...data.results],
          };
        },
      );
    },
  });
};


/**
 * Hook to invalidate unified reference cache
 */
export const useInvalidateUnifiedReference = () => {
  const queryClient = useQueryClient();

  return {
    invalidateAll: () => {
      queryClient.invalidateQueries({
        queryKey: [UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE],
      });
    },
    invalidateSearch: (request?: UnifiedSearchRequest) => {
      if (request) {
        queryClient.invalidateQueries({
          queryKey: createQueryKey(
            UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE,
            "search",
            request as unknown as Record<string, unknown>,
          ),
        });
      } else {
        queryClient.invalidateQueries({
          queryKey: createQueryKey(
            UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE,
            "search",
          ),
        });
      }
    },
    invalidateNode: (nodeId: string) => {
      queryClient.invalidateQueries({
        queryKey: createQueryKey(UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE, "node", {
          nodeId,
        }),
      });
    },
  };
};


/**
 * Hook for searching a specific reference source
 */
export const useSourceSearch = (
  source: SourceType,
  request: UnifiedSearchRequest | null,
  options?: UseQueryOptions<UnifiedSearchResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE,
      "source-search",
      { source, ...request } as unknown as Record<string, unknown>,
    ),
    queryFn: () => {
      if (!request) throw new Error("Request is required");
      return unifiedReferenceService.searchSource(source, request);
    },
    enabled: !!request && !!request.query?.trim(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
};

/**
 * Hook for source search mutation (immediate execution)
 */
export const useSourceSearchMutation = (
  source: SourceType,
  options?: UseMutationOptions<
    UnifiedSearchResponse,
    Error,
    UnifiedSearchRequest
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: UnifiedSearchRequest) =>
      unifiedReferenceService.searchSource(source, request),
    onSuccess: (data, variables) => {
      // Cache the search results
      queryClient.setQueryData(
        createQueryKey(
          UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE,
          "source-search",
          { source, ...variables } as unknown as Record<string, unknown>,
        ),
        data,
      );

      // Cache individual nodes
      data.results.forEach((node) => {
        queryClient.setQueryData(
          createQueryKey(UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE, "node", {
            nodeId: node.id,
          }),
          node,
        );
      });
    },
    onError: (error: Error) => {
      console.error(`${source} search failed:`, error);
    },
    ...options,
  });
};

/**
 * Hook to get available sources and their status
 */
export const useAvailableSources = (
  options?: UseQueryOptions<Record<SourceType, { enabled: boolean; endpoint: string }>, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE, "sources"),
    queryFn: () => unifiedReferenceService.getAvailableSources(),
    staleTime: 10 * 60 * 1000, // 10 minutes - sources don't change frequently
    ...options,
  });
};

/**
 * Hook to test connectivity to a specific source
 */
export const useSourceConnectivity = (
  source: SourceType,
  options?: UseQueryOptions<{
    available: boolean;
    responseTime?: number;
    error?: string;
  }, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE, "connectivity", { source }),
    queryFn: () => unifiedReferenceService.testSourceConnectivity(source),
    staleTime: 2 * 60 * 1000, // 2 minutes - connectivity can change
    retry: 2, // Retry failed connectivity tests
    ...options,
  });
};

