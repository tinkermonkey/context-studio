/**
 * DEPRECATED: usePredicates Hook
 *
 * @deprecated Predicates are now modeled as PropertyDefinition entities
 */

import { UseQueryResult, UseMutationResult } from "@tanstack/react-query";

/**
 * @deprecated Use usePropertyDefinitions instead
 */
export const usePredicates = (..._args: any[]): UseQueryResult<{ data: any[]; total: number }, Error> => {  
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
    refetch: async () => ({ data: undefined } as any),  
  } as UseQueryResult<{ data: any[]; total: number }, Error>;
};

/**
 * @deprecated
 */
export const useExternalPredicates = (..._args: any[]): UseQueryResult<{ data: any[]; total: number }, Error> => {  
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
    refetch: async () => ({ data: undefined } as any),  
  } as UseQueryResult<{ data: any[]; total: number }, Error>;
};

/**
 * @deprecated
 */
export const useSimilarPredicates = (..._args: any[]): UseQueryResult<{ results: any[]; total: number }, Error> => {  
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
    refetch: async () => ({ data: undefined } as any),  
  } as UseQueryResult<{ results: any[]; total: number }, Error>;
};

/**
 * @deprecated
 */
export const useSearchExternalPredicates = (..._args: any[]): UseQueryResult<{ data: any[]; total: number }, Error> => {  
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
    refetch: async () => ({ data: undefined } as any),  
  } as UseQueryResult<{ data: any[]; total: number }, Error>;
};

/**
 * @deprecated
 */
export const useDiscoverPredicates = (..._args: any[]): UseMutationResult<any, Error, any, any> => {  
  return {
    mutate: (_data?: any) => {  
      throw new Error("useDiscoverPredicates has been removed.");
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error("useDiscoverPredicates has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useDiscoverPredicates has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};
