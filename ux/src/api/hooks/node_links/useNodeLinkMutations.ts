/**
 * DEPRECATED: Node Link Mutation Hooks
 *
 * @deprecated Migrate to use the new ontology entity mutation hooks instead
 */

import { UseMutationOptions } from "@tanstack/react-query";

/**
 * @deprecated Use useCreateRelationship instead
 */
export const useCreateNodeLink = (
  _options?: UseMutationOptions<any, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useCreateNodeLink has been removed. Use useCreateRelationship instead.");
    },
    mutateAsync: async () => {
      throw new Error("useCreateNodeLink has been removed. Use useCreateRelationship instead.");
    },
    isPending: false,
  };
};

/**
 * @deprecated Use useUpdateRelationship instead
 */
export const useUpdateNodeLink = (
  _options?: UseMutationOptions<any, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useUpdateNodeLink has been removed. Use useUpdateRelationship instead.");
    },
    mutateAsync: async () => {
      throw new Error("useUpdateNodeLink has been removed. Use useUpdateRelationship instead.");
    },
    isPending: false,
  };
};

/**
 * @deprecated Use useDeleteRelationship instead
 */
export const useDeleteNodeLink = (
  _options?: UseMutationOptions<void, Error, string>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error("useDeleteNodeLink has been removed. Use useDeleteRelationship instead.");
    },
    mutateAsync: async () => {
      throw new Error("useDeleteNodeLink has been removed. Use useDeleteRelationship instead.");
    },
    isPending: false,
  };
};
