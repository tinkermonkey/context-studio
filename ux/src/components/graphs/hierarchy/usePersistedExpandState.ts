import { useState, useEffect, useCallback } from "react";
import { ExpandState, toggleExpandState } from "./tree_chart_layout";

const EXPAND_STATE_STORAGE_KEY = "tree-chart-expand-state";
const SCROLL_STATE_STORAGE_KEY = "tree-chart-scroll-state";

interface ScrollState {
  scrollTop: number;
  scrollLeft: number;
}

/**
 * Custom hook to manage expand state and scroll position with session storage persistence
 * Listens to window scroll events instead of a local container
 * @returns Object containing expandState, handleNodeToggle, clearPersistedState, and scroll management functions
 */
export const usePersistedExpandState = () => {
  // Initialize expand state from session storage or with empty Map
  const [expandState, setExpandState] = useState<ExpandState>(() => {
    try {
      const stored = sessionStorage.getItem(EXPAND_STATE_STORAGE_KEY);
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

  // Save expand state to session storage whenever it changes
  useEffect(() => {
    try {
      // Convert Map to plain object for JSON serialization
      const stateObject = Object.fromEntries(expandState);
      sessionStorage.setItem(
        EXPAND_STATE_STORAGE_KEY,
        JSON.stringify(stateObject),
      );
    } catch (error) {
      console.warn("Failed to save expand state to session storage:", error);
    }
  }, [expandState]);

  // Save scroll position to session storage
  const saveScrollPosition = useCallback(() => {
    const scrollState: ScrollState = {
      scrollTop: window.scrollY || document.documentElement.scrollTop,
      scrollLeft: window.scrollX || document.documentElement.scrollLeft,
    };
    try {
      sessionStorage.setItem(
        SCROLL_STATE_STORAGE_KEY,
        JSON.stringify(scrollState),
      );
    } catch (error) {
      console.warn("Failed to save scroll state to session storage:", error);
    }
  }, []);

  // Restore scroll position from session storage
  const restoreScrollPosition = useCallback(() => {
    try {
      const stored = sessionStorage.getItem(SCROLL_STATE_STORAGE_KEY);
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
  }, []);

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
    try {
      sessionStorage.removeItem(EXPAND_STATE_STORAGE_KEY);
      sessionStorage.removeItem(SCROLL_STATE_STORAGE_KEY);
    } catch (error) {
      console.warn(
        "Failed to clear persisted state from session storage:",
        error,
      );
    }
  }, []);

  return {
    expandState,
    handleNodeToggle,
    clearPersistedState,
    saveScrollPosition,
    restoreScrollPosition,
    setInitialExpandState,
  };
};
