/**
 * Schema Query Hooks
 * 
 * React Query hooks for schema and migration operations
 */

import { useQuery, UseQueryOptions } from '@tanstack/react-query';
import { schemaService, type MigrationHistoryEntry } from '../../services/schema';
import { QUERY_KEYS } from '../../config';
import { createQueryKey } from '../../utils/queryClient';
import type { components } from '../../client/types';

type MigrationStatus = components['schemas']['MigrationStatus'];

/**
 * Hook to fetch current schema status and migration information
 */
export const useSchemaStatus = (
  options?: UseQueryOptions<MigrationStatus, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.SCHEMA, 'status'),
    queryFn: () => schemaService.getStatus(),
    ...options,
  });
};

/**
 * Hook to fetch migration history
 */
export const useMigrationHistory = (
  options?: UseQueryOptions<MigrationHistoryEntry[], Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.SCHEMA, 'history'),
    queryFn: () => schemaService.getHistory(),
    ...options,
  });
};
