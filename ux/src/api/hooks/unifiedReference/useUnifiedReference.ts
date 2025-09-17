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
 * Hook to prefetch node details for better UX
 */
export const usePrefetchNodeDetails = () => {
  const queryClient = useQueryClient();

  return (nodeIds: string[]) => {
    nodeIds.forEach((nodeId) => {
      queryClient.prefetchQuery({
        queryKey: createQueryKey(UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE, "node", {
          nodeId,
        }),
        queryFn: () => unifiedReferenceService.getNode(nodeId),
        staleTime: 10 * 60 * 1000, // 10 minutes
      });
    });
  };
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
 * Hook to get optimistic search suggestions
 */
export const useSearchSuggestions = (
  query: string,
  options?: UseQueryOptions<string[], Error>,
) => {
  const queryClient = useQueryClient();

  return useQuery({
    queryKey: createQueryKey(
      UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE,
      "suggestions",
      { query },
    ),
    queryFn: async () => {
      // For now, return empty array since suggestions endpoint doesn't exist
      // This could be implemented to use cached search results for suggestions
      const cachedQueries = queryClient.getQueriesData({
        queryKey: [UNIFIED_QUERY_KEYS.UNIFIED_REFERENCE, "search"],
      });

      const suggestions: string[] = [];
      cachedQueries.forEach(([, data]) => {
        if (data && typeof data === "object" && "results" in data) {
          const searchData = data as UnifiedSearchResponse;
          searchData.results.forEach((result) => {
            if (result.title.toLowerCase().includes(query.toLowerCase())) {
              suggestions.push(result.title);
            }
          });
        }
      });

      return [...new Set(suggestions)].slice(0, 5); // Unique suggestions, max 5
    },
    enabled: !!query && query.length >= 2,
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
};
