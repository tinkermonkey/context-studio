/**
 * DEPRECATED: usePredicates Hook
 *
 * @deprecated Predicates are now modeled as PropertyDefinition entities
 */

import { UseQueryResult } from "@tanstack/react-query";

/**
 * @deprecated Use usePropertyDefinitions instead
 */
export const usePredicates = (..._args: any[]): UseQueryResult<any[], Error> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error(
      "usePredicates has been removed. Use usePropertyDefinitions instead.",
    ),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<any[], Error>;
};

/**
 * @deprecated
 */
export const useExternalPredicates = (..._args: any[]): UseQueryResult<any, Error> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useExternalPredicates has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<any, Error>;
};

/**
 * @deprecated
 */
export const useSimilarPredicates = (..._args: any[]): UseQueryResult<any[], Error> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useSimilarPredicates has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<any[], Error>;
};

/**
 * @deprecated
 */
export const useSearchExternalPredicates = (..._args: any[]): UseQueryResult<any[], Error> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useSearchExternalPredicates has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<any[], Error>;
};

/**
 * @deprecated
 */
export const useDiscoverPredicates = (..._args: any[]): UseQueryResult<any[], Error> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useDiscoverPredicates has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<any[], Error>;
};
