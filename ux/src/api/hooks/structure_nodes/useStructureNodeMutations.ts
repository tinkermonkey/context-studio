/**
 * DEPRECATED: Structure Node Mutation Hooks
 *
 * @deprecated Migrate to use the new ontology entity mutation hooks instead
 */

import { UseMutationOptions } from "@tanstack/react-query";
import type { StructureNode } from "../../types/structureNodes";

/**
 * @deprecated Use the new ontology entity mutation hooks instead
 */
export const useCreateStructureNode = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
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
  };
};

/**
 * @deprecated Use the new ontology entity mutation hooks instead
 */
export const useUpdateStructureNode = (
  _options?: UseMutationOptions<StructureNode, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error(
        "useUpdateStructureNode has been removed. Use useUpdateTaxonomy, useUpdateConceptScheme, or useUpdateOntologyClass instead.",
      );
    },
    mutateAsync: async () => {
      throw new Error(
        "useUpdateStructureNode has been removed. Use useUpdateTaxonomy, useUpdateConceptScheme, or useUpdateOntologyClass instead.",
      );
    },
    isPending: false,
  };
};

/**
 * @deprecated Use the new ontology entity mutation hooks instead
 */
export const useDeleteStructureNode = (
  _options?: UseMutationOptions<void, Error, string>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error(
        "useDeleteStructureNode has been removed. Use useDeleteTaxonomy, useDeleteConceptScheme, or useDeleteOntologyClass instead.",
      );
    },
    mutateAsync: async () => {
      throw new Error(
        "useDeleteStructureNode has been removed. Use useDeleteTaxonomy, useDeleteConceptScheme, or useDeleteOntologyClass instead.",
      );
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useBulkUpdateStructureNodes = (
  _options?: UseMutationOptions<any, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useBulkUpdateStructureNodes has been removed.");
    },
    mutateAsync: async () => {
      throw new Error("useBulkUpdateStructureNodes has been removed.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useMoveStructureNode = (
  _options?: UseMutationOptions<StructureNode, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useMoveStructureNode has been removed.");
    },
    mutateAsync: async () => {
      throw new Error("useMoveStructureNode has been removed.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useCreateDomain = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    mutate: () => {
      throw new Error("useCreateDomain has been removed. Use useCreateConceptScheme instead.");
    },
    mutateAsync: async () => {
      throw new Error("useCreateDomain has been removed. Use useCreateConceptScheme instead.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useCreateLayer = (
  _options?: UseMutationOptions<any, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useCreateLayer has been removed. Use useCreateTaxonomy instead.");
    },
    mutateAsync: async () => {
      throw new Error("useCreateLayer has been removed. Use useCreateTaxonomy instead.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useCreateTerm = (
  _options?: UseMutationOptions<any, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useCreateTerm has been removed. Use useCreateOntologyClass instead.");
    },
    mutateAsync: async () => {
      throw new Error("useCreateTerm has been removed. Use useCreateOntologyClass instead.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useMoveStructureNodes = (
  _options?: UseMutationOptions<any, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useMoveStructureNodes has been removed.");
    },
    mutateAsync: async () => {
      throw new Error("useMoveStructureNodes has been removed.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useUpdateTerm = (
  _options?: UseMutationOptions<any, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useUpdateTerm has been removed. Use useUpdateOntologyClass instead.");
    },
    mutateAsync: async () => {
      throw new Error("useUpdateTerm has been removed. Use useUpdateOntologyClass instead.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useUpdateDomain = (
  _options?: UseMutationOptions<any, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useUpdateDomain has been removed. Use useUpdateConceptScheme instead.");
    },
    mutateAsync: async () => {
      throw new Error("useUpdateDomain has been removed. Use useUpdateConceptScheme instead.");
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useUpdateLayer = (
  _options?: UseMutationOptions<any, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useUpdateLayer has been removed. Use useUpdateTaxonomy instead.");
    },
    mutateAsync: async () => {
      throw new Error("useUpdateLayer has been removed. Use useUpdateTaxonomy instead.");
    },
    isPending: false,
  };
};
