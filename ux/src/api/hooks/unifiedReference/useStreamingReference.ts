/**
 * Streaming Reference Search Hooks
 *
 * React hooks for real-time unified reference search with streaming results
 */

import { useState, useCallback, useRef} from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import { streamingReferenceService } from "../../services/streamingReference";
import { UnifiedSearchRequest, SourceType } from "../../types/unified";
import {
  StreamingSearchState,
  StreamingSearchControl,
  StreamingSearchOptions,
  SourceSearchUpdate,
  createInitialStreamingState,
} from "../../types/streamingReference";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Enhanced query keys for streaming reference
 */
const STREAMING_QUERY_KEYS = {
  ...QUERY_KEYS,
  STREAMING_REFERENCE: "streaming-reference",
} as const;

/**
 * Hook for streaming unified reference search
 * Provides real-time updates as each source responds
 */
export const useStreamingUnifiedSearch = (options?: {
  onComplete?: (state: StreamingSearchState) => void;
  onSourceUpdate?: (update: SourceSearchUpdate) => void;
  includePartialResults?: boolean;
  timeout?: number;
}) => {
  const queryClient = useQueryClient();
  const [searchState, setSearchState] = useState<StreamingSearchState | null>(
    null,
  );
  const [isSearching, setIsSearching] = useState(false);
  const controlRef = useRef<StreamingSearchControl | null>(null);

  const search = useCallback(
    async (request: UnifiedSearchRequest) => {
      // Cancel any existing search
      if (controlRef.current) {
        controlRef.current.cancel();
      }

      setIsSearching(true);
      setSearchState(createInitialStreamingState(request));

      try {
        const control = await streamingReferenceService.searchStreaming(
          request,
          {
            timeout: options?.timeout,
            includePartialResults: options?.includePartialResults,
            onSourceUpdate: (update) => {
              options?.onSourceUpdate?.(update);
            },
            onStateChange: (state) => {
              setSearchState(state);

              // Cache results as they come in
              if (state.aggregatedResults.length > 0) {
                queryClient.setQueryData(
                  createQueryKey(
                    STREAMING_QUERY_KEYS.STREAMING_REFERENCE,
                    "search",
                    request as unknown as Record<string, unknown>,
                  ),
                  state,
                );

                // Cache individual nodes
                state.aggregatedResults.forEach((node) => {
                  queryClient.setQueryData(
                    createQueryKey(
                      STREAMING_QUERY_KEYS.STREAMING_REFERENCE,
                      "node",
                      {
                        nodeId: node.id,
                      },
                    ),
                    node,
                  );
                });
              }

              // Notify completion
              if (state.isComplete) {
                setIsSearching(false);
                options?.onComplete?.(state);
              }
            },
          },
        );

        controlRef.current = control;
        return control;
      } catch (error) {
        setIsSearching(false);
        throw error;
      }
    },
    [queryClient, options],
  );

  const cancelSearch = useCallback(() => {
    if (controlRef.current) {
      controlRef.current.cancel();
      controlRef.current = null;
    }
    setIsSearching(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (controlRef.current) {
        controlRef.current.cancel();
      }
    };
  }, []);

  return {
    search,
    cancelSearch,
    searchState,
    isSearching,
    hasResults: searchState?.hasAnyResults || false,
    isComplete: searchState?.isComplete || false,
    completedSources: searchState?.completedSources || [],
    errorSources: searchState?.errorSources || [],
    totalResults: searchState?.totalResults || 0,
    results: searchState?.aggregatedResults || [],
    links: searchState?.aggregatedLinks || [],
    deduplicationStats: searchState?.deduplicationStats,
  };
};

/**
 * Hook for tracking source-specific loading states
 * Useful for showing individual source progress indicators
 */
export const useSourceLoadingStates = (
  searchState: StreamingSearchState | null,
) => {
  const sourceStates: Record<SourceType, SourceSearchUpdate> =
    searchState?.sources || ({} as Record<SourceType, SourceSearchUpdate>);

  return {
    sourceStates,
    getSourceStatus: (source: SourceType) =>
      sourceStates[source]?.status || "pending",
    getSourceResults: (source: SourceType) =>
      sourceStates[source]?.results || [],
    getSourceError: (source: SourceType) => sourceStates[source]?.error,
    getSourceExecutionTime: (source: SourceType) =>
      sourceStates[source]?.execution_time_ms,
    isSourceLoading: (source: SourceType) =>
      sourceStates[source]?.status === "loading",
    isSourceComplete: (source: SourceType) =>
      sourceStates[source]?.status === "completed",
    isSourceError: (source: SourceType) =>
      sourceStates[source]?.status === "error",
  };
};

/**
 * Hook for optimized streaming search with mutation pattern
 * Integrates with React Query mutations for consistent error handling
 */
export const useStreamingSearchMutation = (
  options?: StreamingSearchOptions,
) => {
  const queryClient = useQueryClient();
  const [streamingState, setStreamingState] =
    useState<StreamingSearchState | null>(null);
  const controlRef = useRef<StreamingSearchControl | null>(null);

  const mutation = useMutation({
    mutationFn: async (
      request: UnifiedSearchRequest,
    ): Promise<StreamingSearchState> => {
      // Cancel any existing search
      if (controlRef.current) {
        controlRef.current.cancel();
      }

      return new Promise((resolve, reject) => {
        streamingReferenceService
          .searchStreaming(request, {
            ...options,
            onStateChange: (state) => {
              setStreamingState(state);
              options?.onStateChange?.(state);

              if (state.isComplete) {
                resolve(state);
              }
            },
            onSourceUpdate: options?.onSourceUpdate,
          })
          .then((control) => {
            controlRef.current = control;
          })
          .catch(reject);
      });
    },
    onSuccess: (data, variables) => {
      // Cache the final results
      queryClient.setQueryData(
        createQueryKey(
          STREAMING_QUERY_KEYS.STREAMING_REFERENCE,
          "search",
          variables as unknown as Record<string, unknown>,
        ),
        data,
      );

      // Cache individual nodes
      data.aggregatedResults.forEach((node) => {
        queryClient.setQueryData(
          createQueryKey(STREAMING_QUERY_KEYS.STREAMING_REFERENCE, "node", {
            nodeId: node.id,
          }),
          node,
        );
      });
    },
  });

  const cancel = useCallback(() => {
    if (controlRef.current) {
      controlRef.current.cancel();
      controlRef.current = null;
    }
    mutation.reset();
  }, [mutation]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (controlRef.current) {
        controlRef.current.cancel();
      }
    };
  }, []);

  return {
    ...mutation,
    streamingState,
    cancel,
    isStreaming: mutation.isPending,
  };
};

/**
 * Hook to get cached streaming search results
 */
export const useCachedStreamingResults = (
  request: UnifiedSearchRequest | null,
) => {
  const queryClient = useQueryClient();

  if (!request) return null;

  const cacheKey = createQueryKey(
    STREAMING_QUERY_KEYS.STREAMING_REFERENCE,
    "search",
    request as unknown as Record<string, unknown>,
  );

  return queryClient.getQueryData<StreamingSearchState>(cacheKey);
};
