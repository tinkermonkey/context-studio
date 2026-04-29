/**
 * DEPRECATED: Structure Node Mutation Hooks
 *
 * @deprecated Migrate to use the new ontology entity mutation hooks instead
 */

import { UseMutationResult } from "@tanstack/react-query";
import type { OntologyClass } from "../../types/ontologyClass";

/**
 * @deprecated Use the new ontology entity mutation hooks instead
 */
export const useCreateOntologyClass = (..._args: any[]): UseMutationResult<OntologyClass, Error, any, any> => {  
  return {
    mutate: (_data?: any) => {  
      throw new Error(
        "useCreateOntologyClass has been removed. Use useCreateTaxonomy, useCreateConceptScheme, or useCreateOntologyClass instead.",
      );
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error(
        "useCreateOntologyClass has been removed. Use useCreateTaxonomy, useCreateConceptScheme, or useCreateOntologyClass instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useCreateOntologyClass has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<OntologyClass, Error, any, any>;
};

/**
 * @deprecated Use the new ontology entity mutation hooks instead
 */
export const useUpdateOntologyClass = (
  _options?: any,  
): UseMutationResult<OntologyClass, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error(
        "useUpdateOntologyClass has been removed. Use useUpdateTaxonomy, useUpdateConceptScheme, or useUpdateOntologyClass instead.",
      );
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error(
        "useUpdateOntologyClass has been removed. Use useUpdateTaxonomy, useUpdateConceptScheme, or useUpdateOntologyClass instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useUpdateOntologyClass has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<OntologyClass, Error, any, any>;
};

/**
 * @deprecated Use the new ontology entity mutation hooks instead
 */
export const useDeleteOntologyClass = (
  _options?: any,  
): UseMutationResult<void, Error, string, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error(
        "useDeleteOntologyClass has been removed. Use useDeleteTaxonomy, useDeleteConceptScheme, or useDeleteOntologyClass instead.",
      );
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error(
        "useDeleteOntologyClass has been removed. Use useDeleteTaxonomy, useDeleteConceptScheme, or useDeleteOntologyClass instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useDeleteOntologyClass has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<void, Error, string, any>;
};

/**
 * @deprecated
 */
export const useBulkUpdateOntologyClasss = (
  _options?: any,  
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useBulkUpdateOntologyClasss has been removed.");
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error("useBulkUpdateOntologyClasss has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useBulkUpdateOntologyClasss has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useMoveOntologyClass = (
  _options?: any,  
): UseMutationResult<OntologyClass, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useMoveOntologyClass has been removed.");
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error("useMoveOntologyClass has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useMoveOntologyClass has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<OntologyClass, Error, any, any>;
};

/**
 * @deprecated
 */
export const useCreateDomain = (..._args: any[]): UseMutationResult<any, Error, any, any> => {  
  return {
    mutate: (_data?: any) => {  
      throw new Error("useCreateDomain has been removed. Use useCreateConceptScheme instead.");
    },
    mutateAsync: async (_data?: any) => {  
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
  _options?: any,  
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useCreateLayer has been removed. Use useCreateTaxonomy instead.");
    },
    mutateAsync: async (_data?: any) => {  
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
  _options?: any,  
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useCreateTerm has been removed. Use useCreateOntologyClass instead.");
    },
    mutateAsync: async (_data?: any) => {  
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
export const useMoveOntologyClasss = (
  _options?: any,  
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useMoveOntologyClasss has been removed.");
    },
    mutateAsync: async (_data?: any) => {  
      throw new Error("useMoveOntologyClasss has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useMoveOntologyClasss has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated
 */
export const useUpdateTerm = (
  _options?: any,  
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useUpdateTerm has been removed. Use useUpdateOntologyClass instead.");
    },
    mutateAsync: async (_data?: any) => {  
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
  _options?: any,  
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useUpdateDomain has been removed. Use useUpdateConceptScheme instead.");
    },
    mutateAsync: async (_data?: any) => {  
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
  _options?: any,  
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {  
      throw new Error("useUpdateLayer has been removed. Use useUpdateTaxonomy instead.");
    },
    mutateAsync: async (_data?: any) => {  
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
