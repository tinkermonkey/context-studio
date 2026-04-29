/**
 * DEPRECATED: useReferenceLinks Hook
 *
 * @deprecated
 */

import { UseQueryResult, UseMutationResult } from "@tanstack/react-query";

/**
 * @deprecated
 */
export const useReferenceLinks = (
  _nodeId?: string,
  _options?: any,  
): UseQueryResult<any[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useReferenceLinks has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any),  
  } as UseQueryResult<any[], Error>;
};

/**
 * @deprecated
 */
export const useAddReferenceLinks = (
  ..._args: any[]  
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useAddReferenceLinks has been removed.");
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error("useAddReferenceLinks has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useAddReferenceLinks has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useDeleteReferenceLink = (): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useDeleteReferenceLink has been removed.");
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error("useDeleteReferenceLink has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useDeleteReferenceLink has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useRemoveReferenceLink = (..._args: any[]): UseMutationResult<any, Error, any, any> => {  
  return {
    mutate: (_data?: any) => {  
      throw new Error("useRemoveReferenceLink has been removed.");
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error("useRemoveReferenceLink has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useRemoveReferenceLink has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};
