/**
 * DEPRECATED: usePredicates Hook
 *
 * @deprecated Predicates are now modeled as PropertyDefinition entities
 */

import { UseQueryOptions } from "@tanstack/react-query";

/**
 * @deprecated Use usePropertyDefinitions instead
 */
export const usePredicates = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    error: new Error(
      "usePredicates has been removed. Use usePropertyDefinitions instead.",
    ),
    isError: true,
    refetch: async () => undefined,
  };
};

/**
 * @deprecated
 */
export const useExternalPredicates = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    error: new Error("useExternalPredicates has been removed."),
    isError: true,
    refetch: async () => undefined,
  };
};

/**
 * @deprecated
 */
export const useSimilarPredicates = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    error: new Error("useSimilarPredicates has been removed."),
    isError: true,
    refetch: async () => undefined,
  };
};

/**
 * @deprecated
 */
export const useSearchExternalPredicates = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    error: new Error("useSearchExternalPredicates has been removed."),
    isError: true,
    refetch: async () => undefined,
  };
};

/**
 * @deprecated
 */
export const useDiscoverPredicates = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    error: new Error("useDiscoverPredicates has been removed."),
    isError: true,
    refetch: async () => undefined,
  };
};
