/**
 * DEPRECATED: useOntologyClasses Hook
 *
 * @deprecated Migrate to use the new ontology entity hooks instead
 */

import { UseQueryResult } from "@tanstack/react-query";
import type { OntologyClass } from "../../types/ontology";

/**
 * @deprecated Use useTaxonomies, useConceptSchemes, useOntologyClasses instead
 */
export const useOntologyClasses = (
  _params?: any,
): UseQueryResult<OntologyClass[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error(
      "useOntologyClasses has been removed. Use useTaxonomies, useConceptSchemes, or useOntologyClasses instead.",
    ),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined }) as any,
  } as UseQueryResult<OntologyClass[], Error>;
};

/**
 * @deprecated Use useConceptSchemes instead
 */
export const useDomainNodes = (
  ..._args: any[]
): UseQueryResult<OntologyClass[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error(
      "useDomainNodes has been removed. Use useConceptSchemes instead.",
    ),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined }) as any,
  } as UseQueryResult<OntologyClass[], Error>;
};

/**
 * @deprecated Use useTaxonomies instead
 */
export const useLayerNodes = (
  _params?: any,
): UseQueryResult<OntologyClass[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error(
      "useLayerNodes has been removed. Use useTaxonomies instead.",
    ),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined }) as any,
  } as UseQueryResult<OntologyClass[], Error>;
};

/**
 * @deprecated
 */
export const useClass = (
  ..._args: any[]
): UseQueryResult<OntologyClass, Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useClass has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined }) as any,
  } as UseQueryResult<OntologyClass, Error>;
};

/**
 * @deprecated
 */
export const useTermNodes = (
  ..._args: any[]
): UseQueryResult<OntologyClass[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useTermNodes has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined }) as any,
  } as UseQueryResult<OntologyClass[], Error>;
};

/**
 * @deprecated
 */
export const useClassSearch = (
  ..._args: any[]
): UseQueryResult<OntologyClass[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useClassSearch has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined }) as any,
  } as UseQueryResult<OntologyClass[], Error>;
};
