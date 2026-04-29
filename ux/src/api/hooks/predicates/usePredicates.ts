/**
 * DEPRECATED: usePredicates Hook
 *
 * @deprecated Predicates are now modeled as PropertyDefinition entities
 */

import { UseQueryOptions } from "@tanstack/react-query";

/**
 * @deprecated Use usePropertyDefinitions instead
 */
export const usePredicates = (
  _params?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
  _options?: UseQueryOptions<any[], Error>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    data: undefined,
    isLoading: false,
    error: new Error(
      "usePredicates has been removed. Use usePropertyDefinitions instead.",
    ),
    isError: true,
  };
};
