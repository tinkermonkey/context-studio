/**
 * Schema Mutation Hooks
 * 
 * React Query mutation hooks for schema and migration operations
 */

import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query';
import { schemaService } from '../../services/schema';
import { QUERY_KEYS } from '../../config';
import { createQueryKey } from '../../utils/queryClient';

/**
 * Hook to apply pending migrations
 */
export const useMigrateSchema = (
  options?: UseMutationOptions<{ success: boolean; message: string }, Error, { skipOnError?: boolean }>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ skipOnError = false }: { skipOnError?: boolean } = {}) => 
      schemaService.migrate(skipOnError),
    onSuccess: () => {
      // Invalidate schema status and history after migration
      queryClient.invalidateQueries({ queryKey: createQueryKey(QUERY_KEYS.SCHEMA, 'status') });
      queryClient.invalidateQueries({ queryKey: createQueryKey(QUERY_KEYS.SCHEMA, 'history') });
      
      // Also invalidate datasets as schema changes might affect dataset metrics
      queryClient.invalidateQueries({ queryKey: createQueryKey(QUERY_KEYS.DATASETS) });
    },
    ...options,
  });
};

/**
 * Hook to rollback schema to a specific version
 */
export const useRollbackSchema = (
  options?: UseMutationOptions<{ success: boolean; message: string }, Error, number>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (targetVersion: number) => schemaService.rollback(targetVersion),
    onSuccess: () => {
      // Invalidate schema status and history after rollback
      queryClient.invalidateQueries({ queryKey: createQueryKey(QUERY_KEYS.SCHEMA, 'status') });
      queryClient.invalidateQueries({ queryKey: createQueryKey(QUERY_KEYS.SCHEMA, 'history') });
      
      // Also invalidate datasets as schema changes might affect dataset metrics
      queryClient.invalidateQueries({ queryKey: createQueryKey(QUERY_KEYS.DATASETS) });
    },
    ...options,
  });
};

/**
 * Hook to generate a new migration file
 */
export const useGenerateMigration = (
  options?: UseMutationOptions<{ filepath: string; content: string }, Error, string>
) => {
  return useMutation({
    mutationFn: (description: string) => schemaService.generateMigration(description),
    ...options,
  });
};
