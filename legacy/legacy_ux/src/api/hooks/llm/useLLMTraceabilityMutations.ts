/**
 * LLM Traceability Mutation Hooks
 *
 * React Query mutation hooks for LLM traceability operations
 * Following patterns from existing LLM mutation hooks with emphasis on non-blocking tracking
 */

import {
  useMutation,
  UseMutationOptions,
  useQueryClient,
} from "@tanstack/react-query";
import {
  llmTraceabilityService,
  type SelectionRecordRequest,
  type SelectionRecordResponse,
} from "../../services/llmTraceability";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to record selection with error tolerance for non-blocking tracking
 * This is the core mutation for tracking user selections of AI suggestions
 */
export const useRecordSelectionMutation = (
  options?: UseMutationOptions<
    SelectionRecordResponse,
    Error,
    SelectionRecordRequest
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SelectionRecordRequest) =>
      llmTraceabilityService.recordSelection(request),
    onSuccess: (data, variables) => {
      // Invalidate analytics queries to refresh dashboard data
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.LLM_TRACEABILITY, "analytics"),
      });

      // Invalidate execution history queries for this execution
      queryClient.invalidateQueries({
        queryKey: createQueryKey(
          QUERY_KEYS.LLM_TRACEABILITY,
          "execution-history",
          {
            executionId: variables.execution_id,
          },
        ),
      });

      // Optional success callback
      options?.onSuccess?.(data, variables, undefined);
    },
    onError: (error, variables, context) => {
      // CRITICAL: Silent failure - log but don't disrupt user workflow
      console.warn("Selection tracking failed:", {
        error: error.message,
        executionId: variables.execution_id,
        recordId: variables.record_id,
        field: variables.suggestion_field,
      });

      // Optional error callback
      options?.onError?.(error, variables, context);
    },
    // Don't retry selection recording - it's fire-and-forget
    retry: false,
    ...options,
  });
};

/**
 * Hook to record selection with simplified parameters (convenience method)
 */
export const useRecordSuggestionSelectionMutation = (
  options?: UseMutationOptions<
    SelectionRecordResponse,
    Error,
    {
      executionId: string;
      recordId: string;
      field: string;
      content: string;
    }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ executionId, recordId, field, content }) =>
      llmTraceabilityService.recordSuggestionSelection(
        executionId,
        recordId,
        field,
        content,
      ),
    onSuccess: (data, variables) => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.LLM_TRACEABILITY, "analytics"),
      });

      queryClient.invalidateQueries({
        queryKey: createQueryKey(
          QUERY_KEYS.LLM_TRACEABILITY,
          "execution-history",
          {
            executionId: variables.executionId,
          },
        ),
      });

      options?.onSuccess?.(data, variables, undefined);
    },
    onError: (error, variables, context) => {
      // Silent failure with detailed logging
      console.warn("Suggestion selection tracking failed:", {
        error: error.message,
        executionId: variables.executionId,
        recordId: variables.recordId,
        field: variables.field,
        contentLength: variables.content?.length || 0,
      });

      options?.onError?.(error, variables, context);
    },
    retry: false,
    ...options,
  });
};

/**
 * Hook for silent selection recording (fire-and-forget with minimal error handling)
 * Use this when you want completely non-blocking tracking
 */
export const useSilentSelectionRecording = () => {
  const recordSelection = useRecordSelectionMutation({
    onError: (error, variables) => {
      // Ultra-silent - only log to console, never throw or show errors
      console.warn(
        "Silent selection tracking failed (this is expected and safe):",
        {
          error: error.message,
          executionId: variables.execution_id,
          recordId: variables.record_id,
        },
      );
    },
  });

  return {
    recordSelection: recordSelection.mutate,
    isTracking: recordSelection.isPending,
    // Don't expose error state for silent tracking
  };
};

/**
 * Hook for batch selection recording (if multiple selections need to be tracked)
 * Note: This makes multiple API calls - use sparingly
 */
export const useBatchSelectionRecording = (
  options?: UseMutationOptions<
    SelectionRecordResponse[],
    Error,
    SelectionRecordRequest[]
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (requests: SelectionRecordRequest[]) => {
      // Execute all selections in parallel
      const promises = requests.map((request) =>
        llmTraceabilityService.recordSelection(request),
      );

      // Wait for all to complete (some may fail, that's ok)
      const results = await Promise.allSettled(promises);

      // Return successful results, log failures
      const successfulResults: SelectionRecordResponse[] = [];
      results.forEach((result, index) => {
        if (result.status === "fulfilled") {
          successfulResults.push(result.value);
        } else {
          console.warn("Batch selection tracking failed for item:", {
            index,
            error: result.reason?.message,
            request: requests[index],
          });
        }
      });

      return successfulResults;
    },
    onSuccess: (data, variables) => {
      // Invalidate analytics for all execution IDs
      const executionIds = [
        ...new Set(variables.map((req) => req.execution_id)),
      ];

      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.LLM_TRACEABILITY, "analytics"),
      });

      executionIds.forEach((executionId) => {
        queryClient.invalidateQueries({
          queryKey: createQueryKey(
            QUERY_KEYS.LLM_TRACEABILITY,
            "execution-history",
            {
              executionId,
            },
          ),
        });
      });

      options?.onSuccess?.(data, variables, undefined);
    },
    onError: (error, variables, context) => {
      console.warn("Batch selection tracking failed:", {
        error: error.message,
        requestCount: variables.length,
      });

      options?.onError?.(error, variables, context);
    },
    retry: false,
    ...options,
  });
};

/**
 * Hook for optimistic selection recording (shows success immediately, handles failures silently)
 * This provides the best UX by never blocking the user
 */
export const useOptimisticSelectionRecording = (
  onOptimisticSuccess?: (request: SelectionRecordRequest) => void,
) => {
  const recordSelection = useRecordSelectionMutation({
    onError: (error, variables) => {
      // Silent failure - the optimistic success already happened
      console.warn("Optimistic selection tracking failed (post-success):", {
        error: error.message,
        executionId: variables.execution_id,
        recordId: variables.record_id,
      });
    },
  });

  const recordOptimistically = (request: SelectionRecordRequest) => {
    // Immediately call success callback
    onOptimisticSuccess?.(request);

    // Then fire the actual request in the background
    recordSelection.mutate(request);
  };

  return {
    recordSelection: recordOptimistically,
    isTracking: recordSelection.isPending,
  };
};
