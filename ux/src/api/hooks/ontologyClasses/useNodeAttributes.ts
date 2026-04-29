/**
 * DEPRECATED: useNodeAttributes Hook
 *
 * @deprecated
 */

import { UseQueryResult, UseMutationResult } from "@tanstack/react-query";

/**
 * @deprecated
 */
export const useNodeAttributes = (
  _nodeId?: string,
  _options?: any,  
): UseQueryResult<any[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useNodeAttributes has been removed."),
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
export const useUpdateNodeAttribute = (): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useUpdateNodeAttribute has been removed.");
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error("useUpdateNodeAttribute has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useUpdateNodeAttribute has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useNodeAttributeMutations = (
  _nodeId?: string,
  _options?: any,  
): {
  setAttributesMutation: UseMutationResult<any, Error, any, any>;
  removeAttributeMutation: UseMutationResult<any, Error, any, any>;
} => {
  const createErrorMutation = (): UseMutationResult<any, Error, any, any> => ({
    mutate: (_data?: any) => {  
      throw new Error("useNodeAttributeMutations has been removed.");
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error("useNodeAttributeMutations has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useNodeAttributeMutations has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>);

  return {
    setAttributesMutation: createErrorMutation(),
    removeAttributeMutation: createErrorMutation(),
  };
};
