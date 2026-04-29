/**
 * DEPRECATED: useWordSenses Hook
 *
 * @deprecated
 */

import { UseQueryResult, UseMutationResult } from "@tanstack/react-query";

/**
 * @deprecated
 */
export const useWordSenses = (
  _nodeId?: string,
  _options?: any,  
): UseQueryResult<any[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useWordSenses has been removed."),
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
export const useUpdateWordSenses = (
  ..._args: any[]  
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useUpdateWordSenses has been removed.");
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error("useUpdateWordSenses has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useUpdateWordSenses has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};
