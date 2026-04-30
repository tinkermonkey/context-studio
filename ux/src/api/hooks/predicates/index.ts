/**
 * DEPRECATED: Legacy Predicates Hooks
 *
 * This module has been removed as predicates are now modeled as PropertyDefinition entities.
 *
 * Migration Guide:
 * - Replace usePredicates with usePropertyDefinitions
 * - Replace useCreatePredicate with useCreatePropertyDefinition
 * - Replace useUpdatePredicate with useUpdatePropertyDefinition
 * - Replace useDeletePredicate with useDeletePropertyDefinition
 *
 * Components still using deprecated predicates hooks need to be updated to use
 * the new PropertyDefinition hooks or should be refactored to use a different approach.
 */

export const usePredicates = (..._args: any[]): any => {
  return {
    data: undefined,
    isLoading: false,
    isError: true,
    error: new Error(
      "usePredicates has been removed. Use usePropertyDefinitions instead. " +
        "See ux/src/api/hooks/predicates/index.ts for migration guide.",
    ),
  };
};

export const useCreatePredicate = (..._args: any[]): any => {
  return {
    mutate: () =>
      Promise.reject(
        new Error(
          "useCreatePredicate has been removed. Use useCreatePropertyDefinition instead. " +
            "See ux/src/api/hooks/predicates/index.ts for migration guide.",
        ),
      ),
    isPending: false,
    isError: true,
    error: new Error(
      "useCreatePredicate has been removed. Use useCreatePropertyDefinition instead. " +
        "See ux/src/api/hooks/predicates/index.ts for migration guide.",
    ),
  };
};

export const useUpdatePredicate = (..._args: any[]): any => {
  return {
    mutate: () =>
      Promise.reject(
        new Error(
          "useUpdatePredicate has been removed. Use useUpdatePropertyDefinition instead. " +
            "See ux/src/api/hooks/predicates/index.ts for migration guide.",
        ),
      ),
    isPending: false,
    isError: true,
    error: new Error(
      "useUpdatePredicate has been removed. Use useUpdatePropertyDefinition instead. " +
        "See ux/src/api/hooks/predicates/index.ts for migration guide.",
    ),
  };
};

export const useDeletePredicate = (..._args: any[]): any => {
  return {
    mutate: () =>
      Promise.reject(
        new Error(
          "useDeletePredicate has been removed. Use useDeletePropertyDefinition instead. " +
            "See ux/src/api/hooks/predicates/index.ts for migration guide.",
        ),
      ),
    isPending: false,
    isError: true,
    error: new Error(
      "useDeletePredicate has been removed. Use useDeletePropertyDefinition instead. " +
        "See ux/src/api/hooks/predicates/index.ts for migration guide.",
    ),
  };
};

export const useExternalPredicates = (..._args: any[]): any => {
  return {
    data: undefined,
    isLoading: false,
    isError: true,
    error: new Error("useExternalPredicates has been removed."),
  };
};

export const useSimilarPredicates = (..._args: any[]): any => {
  return {
    data: undefined,
    isLoading: false,
    isError: true,
    error: new Error("useSimilarPredicates has been removed."),
  };
};

export const useSearchExternalPredicates = (..._args: any[]): any => {
  return {
    mutate: () =>
      Promise.reject(
        new Error("useSearchExternalPredicates has been removed."),
      ),
    isPending: false,
    isError: true,
    error: new Error("useSearchExternalPredicates has been removed."),
  };
};

export const useDiscoverPredicates = (..._args: any[]): any => {
  return {
    mutate: () =>
      Promise.reject(new Error("useDiscoverPredicates has been removed.")),
    isPending: false,
    isError: true,
    error: new Error("useDiscoverPredicates has been removed."),
  };
};

export const useClusterPredicates = (..._args: any[]): any => {
  return {
    mutate: () =>
      Promise.reject(new Error("useClusterPredicates has been removed.")),
    isPending: false,
    isError: true,
    error: new Error("useClusterPredicates has been removed."),
  };
};
