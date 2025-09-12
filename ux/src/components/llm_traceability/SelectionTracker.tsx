/**
 * SelectionTracker Component
 *
 * A wrapper component for tracking user selections of AI suggestions
 * Follows the PRP requirement for async, non-blocking tracking with graceful error handling
 */

import React, {
  useCallback,
  ReactElement,
  cloneElement,
  isValidElement,
} from "react";
import {
  useRecordSelectionMutation,
  useOptimisticSelectionRecording,
} from "@/api/hooks/llm/useLLMTraceabilityMutations";
import type { SelectionRecordRequest } from "@/api/types/traceability";

export interface SelectionTrackerProps {
  /**
   * The execution ID from the LLM response
   */
  executionId: string;

  /**
   * The record ID (e.g., structure node ID)
   */
  recordId: string;

  /**
   * The field that contains the suggestion (e.g., 'definition', 'title')
   */
  suggestionField: string;

  /**
   * Children components to wrap with selection tracking
   */
  children: ReactElement | ReactElement[];

  /**
   * Called when selection is recorded (optimistically)
   */
  onSelectionRecorded?: (selectionId?: string) => void;

  /**
   * Called when tracking fails (optional - failures are silent by default)
   */
  onTrackingError?: (error: Error) => void;

  /**
   * Whether to use optimistic recording (immediate feedback)
   * @default true
   */
  optimistic?: boolean;

  /**
   * Whether to show visual feedback for tracking state
   * @default false
   */
  showFeedback?: boolean;

  /**
   * Custom class name for the wrapper
   */
  className?: string;
}

/**
 * SelectionTracker wraps child components and automatically tracks when users select/apply suggestions
 */
export const SelectionTracker: React.FC<SelectionTrackerProps> = ({
  executionId,
  recordId,
  suggestionField,
  children,
  onSelectionRecorded,
  onTrackingError,
  optimistic = true,
  showFeedback = false,
  className = "",
}) => {
  // Use optimistic recording by default for best UX
  const optimisticRecording = useOptimisticSelectionRecording((request) => {
    // Immediate success feedback
    onSelectionRecorded?.();
  });

  // Fallback to regular recording if optimistic is disabled
  const recordSelection = useRecordSelectionMutation({
    onSuccess: (data) => {
      onSelectionRecorded?.(data.selection_id);
    },
    onError: (error) => {
      // Silent by default, but allow custom error handling
      onTrackingError?.(error);
    },
  });

  const handleSelection = useCallback(
    (selectedContent: string) => {
      if (!executionId || !recordId || !suggestionField || !selectedContent) {
        console.warn(
          "SelectionTracker: Missing required parameters for tracking",
          {
            executionId: !!executionId,
            recordId: !!recordId,
            suggestionField: !!suggestionField,
            selectedContent: !!selectedContent,
          },
        );
        return;
      }

      const request: SelectionRecordRequest = {
        execution_id: executionId,
        record_type: "structure_node",
        record_id: recordId,
        suggestion_field: suggestionField,
        selected_content: selectedContent,
      };

      if (optimistic) {
        optimisticRecording.recordSelection(request);
      } else {
        recordSelection.mutate(request);
      }
    },
    [
      executionId,
      recordId,
      suggestionField,
      optimistic,
      optimisticRecording,
      recordSelection,
    ],
  );

  // Clone children and inject selection handler
  const enhancedChildren = React.Children.map(children, (child) => {
    if (!isValidElement(child)) {
      return child;
    }

    // Look for common selection props and enhance them
    const props: any = {};

    // Common patterns for selection callbacks
    if ((child.props as any).onSelect) {
      props.onSelect = (content: string) => {
        handleSelection(content);
        (child.props as any).onSelect?.(content);
      };
    }

    if ((child.props as any).onAccept) {
      props.onAccept = (content: string) => {
        handleSelection(content);
        (child.props as any).onAccept?.(content);
      };
    }

    if ((child.props as any).onApply) {
      props.onApply = (content: string) => {
        handleSelection(content);
        (child.props as any).onApply?.(content);
      };
    }

    if (
      (child.props as any).onClick &&
      typeof (child.props as any)["data-content"] === "string"
    ) {
      // Handle buttons/elements with data-content attribute
      props.onClick = (event: React.MouseEvent) => {
        handleSelection((child.props as any)["data-content"]);
        (child.props as any).onClick?.(event);
      };
    }

    return cloneElement(child, props);
  });

  const isTracking = optimistic
    ? optimisticRecording.isTracking
    : recordSelection.isPending;

  return (
    <div
      className={`selection-tracker ${className}`.trim()}
      data-tracking={isTracking}
      data-execution-id={executionId}
      data-record-id={recordId}
      data-field={suggestionField}
    >
      {enhancedChildren}

      {/* Optional visual feedback */}
      {showFeedback && isTracking && (
        <div className="selection-tracking-indicator">
          <span className="text-xs text-gray-500">Recording selection...</span>
        </div>
      )}
    </div>
  );
};

/**
 * Higher-order component version of SelectionTracker for easier integration
 */
export function withSelectionTracking<P extends object>(
  Component: React.ComponentType<P>,
  trackerProps: Omit<SelectionTrackerProps, "children">,
) {
  return React.forwardRef<any, P>((props, ref) => (
    <SelectionTracker {...trackerProps}>
      {React.createElement(Component as any, { ...props, ref })}
    </SelectionTracker>
  ));
}

/**
 * Hook version for manual selection tracking within components
 */
export const useManualSelectionTracking = (
  executionId: string,
  recordId: string,
  suggestionField: string,
  options?: {
    onSelectionRecorded?: (selectionId?: string) => void;
    onTrackingError?: (error: Error) => void;
    optimistic?: boolean;
  },
) => {
  const { optimistic = true } = options || {};

  const optimisticRecording = useOptimisticSelectionRecording((request) => {
    options?.onSelectionRecorded?.();
  });

  const recordSelection = useRecordSelectionMutation({
    onSuccess: (data) => {
      options?.onSelectionRecorded?.(data.selection_id);
    },
    onError: (error) => {
      options?.onTrackingError?.(error);
    },
  });

  const trackSelection = useCallback(
    (selectedContent: string) => {
      const request: SelectionRecordRequest = {
        execution_id: executionId,
        record_type: "structure_node",
        record_id: recordId,
        suggestion_field: suggestionField,
        selected_content: selectedContent,
      };

      if (optimistic) {
        optimisticRecording.recordSelection(request);
      } else {
        recordSelection.mutate(request);
      }
    },
    [
      executionId,
      recordId,
      suggestionField,
      optimistic,
      optimisticRecording,
      recordSelection,
    ],
  );

  return {
    trackSelection,
    isTracking: optimistic
      ? optimisticRecording.isTracking
      : recordSelection.isPending,
  };
};

export default SelectionTracker;
