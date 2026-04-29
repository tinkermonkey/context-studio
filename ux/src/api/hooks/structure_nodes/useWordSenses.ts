/**
 * DEPRECATED: useWordSenses Hook
 *
 * @deprecated
 */

import { UseQueryOptions } from "@tanstack/react-query";

/**
 * @deprecated
 */
export const useWordSenses = (
  _nodeId?: string,
  _options?: UseQueryOptions<any, Error>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    data: undefined,
    isLoading: false,
    error: new Error("useWordSenses has been removed."),
    isError: true,
  };
};

/**
 * @deprecated
 */
export const useUpdateWordSenses = () => {
  return {
    mutate: () => {
      throw new Error("useUpdateWordSenses has been removed.");
    },
    mutateAsync: async () => {
      throw new Error("useUpdateWordSenses has been removed.");
    },
    isPending: false,
  };
};
