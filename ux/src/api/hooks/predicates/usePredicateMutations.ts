/**
 * DEPRECATED: Predicate Mutation Hooks
 *
 * @deprecated Predicates are now modeled as PropertyDefinition entities
 */

import { UseMutationResult } from "@tanstack/react-query";

/**
 * @deprecated Use useCreatePropertyDefinition instead
 */
export const useCreatePredicate = (..._args: any[]): UseMutationResult<any, Error, any, any> => { // eslint-disable-line @typescript-eslint/no-explicit-any
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
    isError: true,
    error: new Error("useCreatePredicate has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated Use useUpdatePropertyDefinition instead
 */
export const useUpdatePredicate = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<any, Error, any, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useUpdatePredicate has been removed. Use useUpdatePropertyDefinition instead.",
      );
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useUpdatePredicate has been removed. Use useUpdatePropertyDefinition instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useUpdatePredicate has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};

/**
 * @deprecated Use useDeletePropertyDefinition instead
 */
export const useDeletePredicate = (
  _options?: any, // eslint-disable-line @typescript-eslint/no-explicit-any
): UseMutationResult<void, Error, string, any> => {
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useDeletePredicate has been removed. Use useDeletePropertyDefinition instead.",
      );
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error(
        "useDeletePredicate has been removed. Use useDeletePropertyDefinition instead.",
      );
    },
    isPending: false,
    isError: true,
    error: new Error("useDeletePredicate has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<void, Error, string, any>;
};

/**
 * @deprecated
 */
export const useClusterPredicates = (..._args: any[]): UseMutationResult<any, Error, any, any> => { // eslint-disable-line @typescript-eslint/no-explicit-any
  return {
    mutate: (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useClusterPredicates has been removed.");
    },
    mutateAsync: async (_data?: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any
      throw new Error("useClusterPredicates has been removed.");
    },
    isPending: false,
    isError: true,
    error: new Error("useClusterPredicates has been removed."),
    status: "idle",
    reset: () => {},
    variables: undefined,
  } as unknown as UseMutationResult<any, Error, any, any>;
};
