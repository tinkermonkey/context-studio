/**
 * DEPRECATED: Structure Node Mutation Hooks
 *
 * @deprecated Migrate to use the new ontology entity mutation hooks instead
 */

import { UseMutationResult } from "@tanstack/react-query";
import type { StructureNode } from "../../types/structureNodes";

/**
 * @deprecated Use the new ontology entity mutation hooks instead
 */
export const useCreateStructureNode = (..._args: any[]): UseMutationResult<StructureNode, Error, any, any> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useCreateStructureNode has been removed. Use useCreateTaxonomy, useCreateConceptScheme, or useCreateOntologyClass instead.",
      );
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useCreateStructureNode has been removed. Use useCreateTaxonomy, useCreateConceptScheme, or useCreateOntologyClass instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useCreateStructureNode has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<StructureNode, Error, any, any>;
};

/**
 * @deprecated Use the new ontology entity mutation hooks instead
 */
export const useUpdateStructureNode = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<StructureNode, Error, any, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useUpdateStructureNode has been removed. Use useUpdateTaxonomy, useUpdateConceptScheme, or useUpdateOntologyClass instead.",
      );
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useUpdateStructureNode has been removed. Use useUpdateTaxonomy, useUpdateConceptScheme, or useUpdateOntologyClass instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useUpdateStructureNode has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<StructureNode, Error, any, any>;
};

/**
 * @deprecated Use the new ontology entity mutation hooks instead
 */
export const useDeleteStructureNode = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<void, Error, string, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useDeleteStructureNode has been removed. Use useDeleteTaxonomy, useDeleteConceptScheme, or useDeleteOntologyClass instead.",
      );
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useDeleteStructureNode has been removed. Use useDeleteTaxonomy, useDeleteConceptScheme, or useDeleteOntologyClass instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useDeleteStructureNode has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<void, Error, string, any>;
};

/**
 * @deprecated
 */
export const useBulkUpdateStructureNodes = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useBulkUpdateStructureNodes has been removed.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useBulkUpdateStructureNodes has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useBulkUpdateStructureNodes has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useMoveStructureNode = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<StructureNode, Error, any, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useMoveStructureNode has been removed.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useMoveStructureNode has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useMoveStructureNode has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<StructureNode, Error, any, any>;
};

/**
 * @deprecated
 */
export const useCreateDomain = (..._args: any[]): UseMutationResult<any, Error, any, any> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useCreateDomain has been removed. Use useCreateConceptScheme instead.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useCreateDomain has been removed. Use useCreateConceptScheme instead.");
    },
    isPending: false,
    isError: true,
    error: new Error("useCreateDomain has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useCreateLayer = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useCreateLayer has been removed. Use useCreateTaxonomy instead.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useCreateLayer has been removed. Use useCreateTaxonomy instead.");
    },
    isPending: false,
    isError: true,
    error: new Error("useCreateLayer has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useCreateTerm = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useCreateTerm has been removed. Use useCreateOntologyClass instead.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useCreateTerm has been removed. Use useCreateOntologyClass instead.");
    },
    isPending: false,
    isError: true,
    error: new Error("useCreateTerm has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useMoveStructureNodes = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useMoveStructureNodes has been removed.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useMoveStructureNodes has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useMoveStructureNodes has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useUpdateTerm = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useUpdateTerm has been removed. Use useUpdateOntologyClass instead.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useUpdateTerm has been removed. Use useUpdateOntologyClass instead.");
    },
    isPending: false,
    isError: true,
    error: new Error("useUpdateTerm has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useUpdateDomain = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useUpdateDomain has been removed. Use useUpdateConceptScheme instead.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useUpdateDomain has been removed. Use useUpdateConceptScheme instead.");
    },
    isPending: false,
    isError: true,
    error: new Error("useUpdateDomain has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useUpdateLayer = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useUpdateLayer has been removed. Use useUpdateTaxonomy instead.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useUpdateLayer has been removed. Use useUpdateTaxonomy instead.");
    },
    isPending: false,
    isError: true,
    error: new Error("useUpdateLayer has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};
