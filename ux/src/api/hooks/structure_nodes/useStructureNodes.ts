/**
 * DEPRECATED: useStructureNodes Hook
 *
 * @deprecated Migrate to use the new ontology entity hooks instead
 */

import { UseQueryOptions } from "@tanstack/react-query";
import type { StructureNode } from "../../types/structureNodes";

/**
 * @deprecated Use useTaxonomies, useConceptSchemes, useOntologyClasses instead
 */
export const useStructureNodes = (
  _params?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
  _options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return {
    data: undefined,
    isLoading: false,
    error: new Error(
      "useStructureNodes has been removed. Use useTaxonomies, useConceptSchemes, or useOntologyClasses instead.",
    ),
    isError: true,
    refetch: async () => undefined,
  };
};

/**
 * @deprecated Use useConceptSchemes instead
 */
export const useDomainNodes = (
  _params?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
  _options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return {
    data: undefined,
    isLoading: false,
    error: new Error("useDomainNodes has been removed. Use useConceptSchemes instead."),
    isError: true,
    refetch: async () => undefined,
  };
};

/**
 * @deprecated Use useTaxonomies instead
 */
export const useLayerNodes = (
  _params?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
  _options?: UseQueryOptions<StructureNode[], Error>,
) => {
  return {
    data: undefined,
    isLoading: false,
    error: new Error("useLayerNodes has been removed. Use useTaxonomies instead."),
    isError: true,
    refetch: async () => undefined,
  };
};
