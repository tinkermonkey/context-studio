/**
 * Schema Mutation Hooks
 *
 * React Query mutation hooks for schema and migration operations
 */

import {
  useMutation,
  useQueryClient,
  UseMutationOptions,
} from "@tanstack/react-query";
import {
  schemaService,
  type MigrateParams,
  type GenerateMigrationParams,
} from "../../services/schema";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to apply pending migrations
 */
export const useMigrateSchema = (
  options?: UseMutationOptions<unknown, Error, MigrateParams | undefined>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params?: MigrateParams) => schemaService.migrate(params),
    onSuccess: () => {
      // Invalidate schema status and history after migration
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.SCHEMA, "status"),
      });
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.SCHEMA, "history"),
      });

      // Also invalidate datasets as schema changes might affect dataset metrics
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS),
      });
    },
    ...options,
  });
};

/**
 * Hook to rollback schema to a specific version
 */
export const useRollbackSchema = (
  options?: UseMutationOptions<unknown, Error, number>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (targetVersion: number) =>
      schemaService.rollback(targetVersion),
    onSuccess: () => {
      // Invalidate schema status and history after rollback
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.SCHEMA, "status"),
      });
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.SCHEMA, "history"),
      });

      // Also invalidate datasets as schema changes might affect dataset metrics
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS),
      });
    },
    ...options,
  });
};

/**
 * Hook to generate a new migration file
 */
export const useGenerateMigration = (
  options?: UseMutationOptions<unknown, Error, GenerateMigrationParams>,
) => {
  return useMutation({
    mutationFn: (params: GenerateMigrationParams) =>
      schemaService.generateMigration(params),
    ...options,
  });
};
