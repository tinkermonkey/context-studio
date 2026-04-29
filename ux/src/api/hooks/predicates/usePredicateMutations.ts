/**
 * DEPRECATED: Predicate Mutation Hooks
 *
 * @deprecated Predicates are now modeled as PropertyDefinition entities
 */

import { UseMutationOptions } from "@tanstack/react-query";

/**
 * @deprecated Use useCreatePropertyDefinition instead
 */
export const useCreatePredicate = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useCreatePredicate has been removed. Use useCreatePropertyDefinition instead.",
      );
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useCreatePredicate has been removed. Use useCreatePropertyDefinition instead.",
      );
    },
    isPending: false,
  };
};

/**
 * @deprecated Use useUpdatePropertyDefinition instead
 */
export const useUpdatePredicate = (
  _options?: UseMutationOptions<any, Error, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error(
        "useUpdatePredicate has been removed. Use useUpdatePropertyDefinition instead.",
      );
    },
    mutateAsync: async () => {
      throw new Error(
        "useUpdatePredicate has been removed. Use useUpdatePropertyDefinition instead.",
      );
    },
    isPending: false,
  };
};

/**
 * @deprecated Use useDeletePropertyDefinition instead
 */
export const useDeletePredicate = (
  _options?: UseMutationOptions<void, Error, string>, // eslint-disable-line @typescript-eslint/no-explicit-any
) => {
  return {
    mutate: () => {
      throw new Error(
        "useDeletePredicate has been removed. Use useDeletePropertyDefinition instead.",
      );
    },
    mutateAsync: async () => {
      throw new Error(
        "useDeletePredicate has been removed. Use useDeletePropertyDefinition instead.",
      );
    },
    isPending: false,
  };
};

/**
 * @deprecated
 */
export const useClusterPredicates = (..._args: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useClusterPredicates has been removed.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useClusterPredicates has been removed.");
    },
    isPending: false,
  };
};
