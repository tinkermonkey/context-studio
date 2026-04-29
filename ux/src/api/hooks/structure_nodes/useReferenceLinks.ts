/**
 * DEPRECATED: useReferenceLinks Hook
 *
 * @deprecated
 */

import { UseQueryOptions } from "@tanstack/react-query";

/**
 * @deprecated
 */
export const useReferenceLinks = (
  _nodeId?: string,
  _options?: UseQueryOptions<any, Error>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    data: undefined,
    isLoading: false,
    error: new Error("useReferenceLinks has been removed."),
    isError: true,
  };
};

/**
 * @deprecated
 */
export const useAddReferenceLinks = () => {
  return {
    mutate: () => {
      throw new Error("useAddReferenceLinks has been removed.");
    },
    mutateAsync: async () => {
      throw new Error("useAddReferenceLinks has been removed.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useDeleteReferenceLink = () => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useDeleteReferenceLink has been removed.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useDeleteReferenceLink has been removed.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useRemoveReferenceLink = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useRemoveReferenceLink has been removed.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useRemoveReferenceLink has been removed.");
    },
    isPending: false,
  };
};
