/**
 * DEPRECATED: useNodeLinks Hook
 *
 * @deprecated Migrate to use the new ontology entity hooks instead
 */

import { UseQueryResult } from "@tanstack/react-query";

/**
 * @deprecated Use useRelationships instead
 */
export const useNodeLinks = (
  _params?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseQueryResult<any[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useNodeLinks has been removed. Use useRelationships instead."),
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
export const useNodeLinksByNode = (..._args: any[]): UseQueryResult<any[], Error> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useNodeLinksByNode has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<any[], Error>;
};
