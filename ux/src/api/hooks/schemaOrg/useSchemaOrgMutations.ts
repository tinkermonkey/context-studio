/**
 * Schema.org Mutation Hooks
 * 
 * React Query mutation hooks for Schema.org operations
 */

import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query';
import { schemaOrgService, type RefreshParams } from '../../services/schemaOrg';
import { QUERY_KEYS } from '../../config';
import { createQueryKey } from '../../utils/queryClient';

/**
 * Hook to refresh Schema.org database
 */
export const useRefreshSchemaOrg = (
  options?: UseMutationOptions<unknown, Error, RefreshParams | undefined>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params?: RefreshParams) => schemaOrgService.refresh(params),
    onSuccess: () => {
      // Invalidate all Schema.org related queries
      queryClient.invalidateQueries({ queryKey: createQueryKey(QUERY_KEYS.SCHEMA_ORG) });
    },
    ...options,
  });
};
