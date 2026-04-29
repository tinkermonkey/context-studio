/**
 * DEPRECATED: useNodeLinks Hook
 *
 * @deprecated Migrate to use the new ontology entity hooks instead
 */

import { UseQueryOptions } from "@tanstack/react-query";

/**
 * @deprecated Use useRelationships instead
 */
export const useNodeLinks = (
  _params?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
  _options?: UseQueryOptions<any[], Error>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    data: undefined,
    isLoading: false,
    error: new Error("useNodeLinks has been removed. Use useRelationships instead."),
    isError: true,
  };
};
