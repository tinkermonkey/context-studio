/**
 * DEPRECATED: useStructureNodes Hook
 *
 * @deprecated Migrate to use the new ontology entity hooks instead
 */

import { UseQueryResult } from "@tanstack/react-query";
import type { StructureNode } from "../../types/structureNodes";

/**
 * @deprecated Use useTaxonomies, useConceptSchemes, useOntologyClasses instead
 */
export const useStructureNodes = (
  _params?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseQueryResult<StructureNode[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error(
      "useStructureNodes has been removed. Use useTaxonomies, useConceptSchemes, or useOntologyClasses instead.",
    ),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<StructureNode[], Error>;
};

/**
 * @deprecated Use useConceptSchemes instead
 */
export const useDomainNodes = (
  _params?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseQueryResult<StructureNode[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useDomainNodes has been removed. Use useConceptSchemes instead."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<StructureNode[], Error>;
};

/**
 * @deprecated Use useTaxonomies instead
 */
export const useLayerNodes = (
  _params?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseQueryResult<StructureNode[], Error> => {
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useLayerNodes has been removed. Use useTaxonomies instead."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<StructureNode[], Error>;
};

/**
 * @deprecated
 */
export const useStructureNode = (..._args: any[]): UseQueryResult<StructureNode, Error> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useStructureNode has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<StructureNode, Error>;
};

/**
 * @deprecated
 */
export const useTermNodes = (..._args: any[]): UseQueryResult<StructureNode[], Error> => { // eslint-disable-line @typescript-eslint/no-explicit-any
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
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<StructureNode[], Error>;
};

/**
 * @deprecated
 */
export const useStructureNodeSearch = (..._args: any[]): UseQueryResult<StructureNode[], Error> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    data: undefined,
    isLoading: false,
    isFetching: false,
    isPlaceholderData: false,
    error: new Error("useStructureNodeSearch has been removed."),
    isError: true,
    status: "error",
    dataUpdatedAt: 0,
    errorUpdatedAt: Date.now(),
    refetch: async () => ({ data: undefined } as any), // eslint-disable-line @typescript-eslint/no-explicit-any
  } as UseQueryResult<StructureNode[], Error>;
};
