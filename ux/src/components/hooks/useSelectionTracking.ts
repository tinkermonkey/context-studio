/**
 * useSelectionTracking Custom Hook
 *
 * Simple interface for any component to track LLM suggestion selections
 * Handles execution_id management, silent failures, and optional success callbacks
 * Following the PRP requirement for non-blocking, graceful tracking
 */

import { useCallback, useRef } from "react";
import {
  useRecordSelectionMutation,
  useOptimisticSelectionRecording,
} from "@/api/hooks/llm/useLLMTraceabilityMutations";
import type { SelectionRecordRequest } from "@/api/types/traceability";

export interface UseSelectionTrackingOptions {
  /**
   * Whether to use optimistic recording (immediate success feedback)
   * @default true
   */
  optimistic?: boolean;

  /**
   * Called when selection is recorded successfully
   */
  onSuccess?: (selectionId?: string) => void;

  /**
   * Called when tracking fails (optional - failures are silent by default)
   */
  onError?: (error: Error) => void;

  /**
   * Whether to log tracking attempts to console
   * @default false
   */
  debug?: boolean;
}

export interface SelectionTrackingResult {
  /**
   * Track a selection with all required parameters
   */
  trackSelection: (
    executionId: string,
    recordId: string,
    suggestionField: string,
    selectedContent: string,
  ) => void;

  /**
   * Track a selection using a pre-built request object
   */
  trackSelectionRequest: (request: SelectionRecordRequest) => void;

  /**
   * Whether a tracking request is currently in progress
   */
  isTracking: boolean;

  /**
   * Get tracking statistics for this hook instance
   */
  getStats: () => {
    totalAttempts: number;
    successfulAttempts: number;
    failedAttempts: number;
  };

  /**
   * Reset tracking statistics
   */
  resetStats: () => void;
}

/**
 * Custom hook for tracking LLM suggestion selections
 * Provides a simple interface that any component can use for tracking
 */
export const useSelectionTracking = (
  options: UseSelectionTrackingOptions = {},
): SelectionTrackingResult => {
  const { optimistic = true, onSuccess, onError, debug = false } = options;

  // Statistics tracking
  const statsRef = useRef({
    totalAttempts: 0,
    successfulAttempts: 0,
    failedAttempts: 0,
  });

  // Optimistic recording hook
  const optimisticRecording = useOptimisticSelectionRecording((request) => {
    if (debug) {
      console.log("Selection tracked optimistically:", {
        executionId: request.execution_id,
        recordId: request.record_id,
        field: request.suggestion_field,
      });
    }

    statsRef.current.successfulAttempts++;
    onSuccess?.();
  });

  // Standard recording hook
  const recordSelection = useRecordSelectionMutation({
    onSuccess: (data, variables) => {
      if (debug) {
        console.log("Selection tracked successfully:", {
          selectionId: data.selection_id,
          executionId: variables.execution_id,
          recordId: variables.record_id,
        });
      }

      statsRef.current.successfulAttempts++;
      onSuccess?.(data.selection_id);
    },
    onError: (error, variables) => {
      if (debug) {
        console.warn("Selection tracking failed:", {
          error: error.message,
          executionId: variables.execution_id,
          recordId: variables.record_id,
        });
      }

      statsRef.current.failedAttempts++;

      // Always log failures silently, even without debug mode
      console.warn("LLM selection tracking failed (this is safe):", {
        error: error.message,
        executionId: variables.execution_id.substring(0, 8),
        recordId: variables.record_id,
      });

      // Call custom error handler if provided
      onError?.(error);
    },
  });

  // Track selection with individual parameters
  const trackSelection = useCallback(
    (
      executionId: string,
      recordId: string,
      suggestionField: string,
      selectedContent: string,
    ) => {
      // Validate required parameters
      if (!executionId || !recordId || !suggestionField || !selectedContent) {
        console.error(
          "Missing required parameters for selection tracking",
        );

        if (debug) {
          console.warn("Selection tracking aborted - missing parameters:", {
            executionId: !!executionId,
            recordId: !!recordId,
            suggestionField: !!suggestionField,
            selectedContent: !!selectedContent,
          });
        }

        statsRef.current.failedAttempts++;
        onError?.(new Error("Missing required parameters for selection tracking"));
        return;
      }

      const request: SelectionRecordRequest = {
        execution_id: executionId,
        record_type: "structure_node",
        record_id: recordId,
        suggestion_field: suggestionField,
        selected_content: selectedContent,
      };

      statsRef.current.totalAttempts++;

      if (optimistic) {
        optimisticRecording.recordSelection(request);
      } else {
        recordSelection.mutate(request);
      }
    },
    [optimistic, optimisticRecording, recordSelection, debug, onError],
  );

  // Track selection with request object
  const trackSelectionRequest = useCallback(
    (request: SelectionRecordRequest) => {
      // Validate request object
      if (
        !request.execution_id ||
        !request.record_id ||
        !request.suggestion_field ||
        !request.selected_content
      ) {

        if (debug) {
          console.warn(
            "Selection tracking aborted - invalid request:",
            request,
          );
        }

        statsRef.current.failedAttempts++;
        onError?.(new Error("Invalid selection tracking request"));
        return;
      }

      statsRef.current.totalAttempts++;

      if (optimistic) {
        optimisticRecording.recordSelection(request);
      } else {
        recordSelection.mutate(request);
      }
    },
    [optimistic, optimisticRecording, recordSelection, debug, onError],
  );

  // Get current statistics
  const getStats = useCallback(() => ({ ...statsRef.current }), []);

  // Reset statistics
  const resetStats = useCallback(() => {
    statsRef.current = {
      totalAttempts: 0,
      successfulAttempts: 0,
      failedAttempts: 0,
    };
  }, []);

  // Determine if tracking is in progress
  const isTracking = optimistic
    ? optimisticRecording.isTracking
    : recordSelection.isPending;

  return {
    trackSelection,
    trackSelectionRequest,
    isTracking,
    getStats,
    resetStats,
  };
};

/**
 * Hook variant that automatically manages execution ID from context
 * Useful when the execution ID is stable within a component tree
 */
export const useSelectionTrackingWithExecutionId = (
  executionId: string,
  options: UseSelectionTrackingOptions = {},
): Omit<SelectionTrackingResult, "trackSelection"> & {
  trackSelection: (
    recordId: string,
    suggestionField: string,
    selectedContent: string,
  ) => void;
} => {
  const { trackSelection: baseTrackSelection, ...otherMethods } =
    useSelectionTracking(options);

  const trackSelection = useCallback(
    (recordId: string, suggestionField: string, selectedContent: string) => {
      baseTrackSelection(
        executionId,
        recordId,
        suggestionField,
        selectedContent,
      );
    },
    [baseTrackSelection, executionId],
  );

  return {
    trackSelection,
    ...otherMethods,
  };
};

/**
 * Hook variant for silent tracking (no success/error callbacks)
 * Use this for completely fire-and-forget tracking
 */
export const useSilentSelectionTracking = (): Pick<
  SelectionTrackingResult,
  "trackSelection" | "trackSelectionRequest" | "isTracking"
> => {
  const { trackSelection, trackSelectionRequest, isTracking } =
    useSelectionTracking({
      optimistic: true, // Always use optimistic for silent tracking
      debug: false, // Never debug for silent tracking
      // No success/error callbacks for truly silent operation
    });

  return {
    trackSelection,
    trackSelectionRequest,
    isTracking,
  };
};

export default useSelectionTracking;
