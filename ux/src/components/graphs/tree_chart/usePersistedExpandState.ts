import { useState, useEffect, useCallback } from "react";
import { ExpandState, toggleExpandState } from "./tree_chart_layout";

const EXPAND_STATE_STORAGE_KEY_PREFIX = "tree-chart-expand-state";
const SCROLL_STATE_STORAGE_KEY_PREFIX = "tree-chart-scroll-state";

interface ScrollState {
  scrollTop: number;
  scrollLeft: number;
}

/**
 * Custom hook to manage expand state and scroll position with optional session storage persistence
 * Listens to window scroll events instead of a local container
 * @param viewId - Optional view identifier for persisting state. If not provided, state will not be persisted.
 * @returns Object containing expandState, handleNodeToggle, clearPersistedState, and scroll management functions
 */
export const usePersistedExpandState = (viewId?: string) => {
  // Generate view-specific storage keys if viewId is provided
  const expandStateKey = viewId ? `${EXPAND_STATE_STORAGE_KEY_PREFIX}-${viewId}` : null;
  const scrollStateKey = viewId ? `${SCROLL_STATE_STORAGE_KEY_PREFIX}-${viewId}` : null;
  // Initialize expand state from session storage or with empty Map
  const [expandState, setExpandState] = useState<ExpandState>(() => {
    // Only load from session storage if we have a viewId
    if (!expandStateKey) {
      return new Map();
    }

    try {
      const stored = sessionStorage.getItem(expandStateKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Convert the stored object back to a Map
        return new Map(Object.entries(parsed));
      }
    } catch (error) {
      console.warn("Failed to parse expand state from session storage:", error);
    }
    return new Map();
  });

  // Function to set initial expand state - useful for overriding persisted state
  const setInitialExpandState = useCallback((initialState: ExpandState) => {
    setExpandState(initialState);
  }, []);

  // Save expand state to session storage whenever it changes (only if viewId is provided)
  useEffect(() => {
    // Only save to session storage if we have a viewId
    if (!expandStateKey) {
      return;
    }

    try {
      // Convert Map to plain object for JSON serialization
      const stateObject = Object.fromEntries(expandState);
      sessionStorage.setItem(
        expandStateKey,
        JSON.stringify(stateObject),
      );
    } catch (error) {
      console.warn("Failed to save expand state to session storage:", error);
    }
  }, [expandState, expandStateKey]);

  // Save scroll position to session storage (only if viewId is provided)
  const saveScrollPosition = useCallback(() => {
    // Only save to session storage if we have a viewId
    if (!scrollStateKey) {
      return;
    }

    const scrollState: ScrollState = {
      scrollTop: window.scrollY || document.documentElement.scrollTop,
      scrollLeft: window.scrollX || document.documentElement.scrollLeft,
    };
    try {
      sessionStorage.setItem(
        scrollStateKey,
        JSON.stringify(scrollState),
      );
    } catch (error) {
      console.warn("Failed to save scroll state to session storage:", error);
    }
  }, [scrollStateKey]);

  // Restore scroll position from session storage (only if viewId is provided)
  const restoreScrollPosition = useCallback(() => {
    // Only restore from session storage if we have a viewId
    if (!scrollStateKey) {
      return;
    }

    try {
      const stored = sessionStorage.getItem(scrollStateKey);
      if (stored) {
        const scrollState: ScrollState = JSON.parse(stored);
        // Use requestAnimationFrame to ensure the DOM is ready
        requestAnimationFrame(() => {
          window.scrollTo({
            top: scrollState.scrollTop,
            left: scrollState.scrollLeft,
            behavior: "auto", // Use 'auto' to avoid animation when restoring
          });
        });
      }
    } catch (error) {
      console.warn(
        "Failed to restore scroll state from session storage:",
        error,
      );
    }
  }, [scrollStateKey]);

  // Set up window scroll listener
  useEffect(() => {
    const handleScroll = () => {
      saveScrollPosition();
    };

    // Add scroll listener to window
    window.addEventListener("scroll", handleScroll, { passive: true });

    // Cleanup listener on unmount
    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, [saveScrollPosition]);

  // Handler for toggling node expansion
  const handleNodeToggle = useCallback(
    (nodeId: string) => {
      // Save scroll position before expanding/collapsing
      saveScrollPosition();
      setExpandState((prev) => toggleExpandState(prev, nodeId));
    },
    [saveScrollPosition],
  );

  // Function to clear all expand state and scroll state (useful for reset functionality)
  const clearPersistedState = useCallback(() => {
    setExpandState(new Map());

    // Only clear session storage if we have keys (i.e., if viewId is provided)
    if (!expandStateKey || !scrollStateKey) {
      return;
    }

    try {
      sessionStorage.removeItem(expandStateKey);
      sessionStorage.removeItem(scrollStateKey);
    } catch (error) {
      console.warn(
        "Failed to clear persisted state from session storage:",
        error,
      );
    }
  }, [expandStateKey, scrollStateKey]);

  return {
    expandState,
    handleNodeToggle,
    clearPersistedState,
    saveScrollPosition,
    restoreScrollPosition,
    setInitialExpandState,
  };
};
