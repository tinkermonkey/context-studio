/**
 * DEPRECATED: useNodeAttributes Hook
 *
 * @deprecated
 */

import { UseQueryOptions } from "@tanstack/react-query";

/**
 * @deprecated
 */
export const useNodeAttributes = (
  _nodeId?: string,
  _options?: UseQueryOptions<any, Error>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    data: undefined,
    isLoading: false,
    error: new Error("useNodeAttributes has been removed."),
    isError: true,
  };
};

/**
 * @deprecated
 */
export const useUpdateNodeAttribute = () => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useUpdateNodeAttribute has been removed.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useUpdateNodeAttribute has been removed.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useNodeAttributeMutations = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useNodeAttributeMutations has been removed.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useNodeAttributeMutations has been removed.");
    },
    isPending: false,
  };
};
