/**
 * Custom debounce hook
 *
 * Provides debouncing functionality without external dependencies
 */

import { useCallback, useRef } from "react";

/**
 * Creates a debounced version of a callback function
 * @param callback - The function to debounce
 * @param delay - The delay in milliseconds
 * @returns A debounced version of the callback with a cancel method
 */

export const useDebounce = <T extends (...args: any[]) => any>(
  callback: T,
  delay: number,
): T & { cancel: () => void } => {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const debouncedCallback = useCallback(
    (...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => callback(...args), delay);
    },
    [callback, delay],
  ) as T & { cancel: () => void };

  // Add cancel method to clear pending timeout
  debouncedCallback.cancel = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  }, []);

  return debouncedCallback;
};
