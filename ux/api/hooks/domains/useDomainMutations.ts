/**
 * Domains Mutation Hooks
 * 
 * React Query mutation hooks for domain entities
 */

import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query';
import { domainService } from '../../services/domains';
import { QUERY_KEYS } from '../../config';
import { createQueryKey } from '../../utils/queryClient';
import type { components } from '../../client/types';

type DomainOut = components['schemas']['DomainOut'];
type DomainCreate = components['schemas']['DomainCreate'];
type DomainUpdate = components['schemas']['DomainUpdate'];

/**
 * Hook to create a new domain
 */
export const useCreateDomain = (
  options?: UseMutationOptions<DomainOut, Error, DomainCreate>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DomainCreate) => domainService.create(data),
    onSuccess: (data) => {
      // Update the domains list cache
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.DOMAINS],
      });
      
      // Add the new domain to the cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.DOMAINS, data.id),
        data
      );
    },
    ...options,
  });
};

/**
 * Hook to update an existing domain
 */
export const useUpdateDomain = (
  options?: UseMutationOptions<DomainOut, Error, { id: string; data: DomainUpdate }>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: DomainUpdate }) => 
      domainService.update(id, data),
    onSuccess: (data, variables) => {
      // Update the specific domain in cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.DOMAINS, variables.id),
        data
      );
      
      // Invalidate the domains list to refresh it
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.DOMAINS],
      });
    },
    ...options,
  });
};

/**
 * Hook to delete a domain
 */
export const useDeleteDomain = (
  options?: UseMutationOptions<void, Error, string>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => domainService.delete(id),
    onSuccess: (_, id) => {
      // Remove the domain from cache
      queryClient.removeQueries({
        queryKey: createQueryKey(QUERY_KEYS.DOMAINS, id),
      });
      
      // Invalidate the domains list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.DOMAINS],
      });
      
      // Also invalidate related terms
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.TERMS],
      });
    },
    ...options,
  });
};
