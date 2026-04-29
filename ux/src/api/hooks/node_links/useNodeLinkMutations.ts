/**
 * DEPRECATED: Node Link Mutation Hooks
 *
 * @deprecated Migrate to use the new ontology entity mutation hooks instead
 */

import { UseMutationResult } from "@tanstack/react-query";

/**
 * @deprecated Use useCreateRelationship instead
 */
export const useCreateNodeLink = (
  ..._args: any[]
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {
      throw new Error(
        "useCreateNodeLink has been removed. Use useCreateRelationship instead.",
      );
    },
    mutateAsync: async (_data?: any) => {
      throw new Error(
        "useCreateNodeLink has been removed. Use useCreateRelationship instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useCreateNodeLink has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated Use useUpdateRelationship instead
 */
export const useUpdateNodeLink = (
  _options?: any,
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => {
      throw new Error(
        "useUpdateNodeLink has been removed. Use useUpdateRelationship instead.",
      );
    },
    mutateAsync: async (_data?: any) => {
      throw new Error(
        "useUpdateNodeLink has been removed. Use useUpdateRelationship instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useUpdateNodeLink has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated Use useDeleteRelationship instead
 */
export const useDeleteNodeLink = (
  _options?: any,
): UseMutationResult<void, Error, string, any> => {
  return {
    mutate: (_data?: any) => {
      throw new Error(
        "useDeleteNodeLink has been removed. Use useDeleteRelationship instead.",
      );
    },
    mutateAsync: async (_data?: any) => {
      throw new Error(
        "useDeleteNodeLink has been removed. Use useDeleteRelationship instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useDeleteNodeLink has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<void, Error, string, any>;
};
