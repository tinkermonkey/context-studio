/**
 * Domains Query Hooks
 * 
 * React Query hooks for domain entities
 */

import { useQuery, UseQueryOptions } from '@tanstack/react-query';
import { domainService, type DomainListParams, type DomainFindParams } from '../../services/domains';
import { QUERY_KEYS } from '../../config';
import { createQueryKey } from '../../utils/queryClient';
import type { PaginatedResponse } from '../../services/base';
import type { components } from '../../client/types';

type DomainOut = components['schemas']['DomainOut'];
type FindDomainResult = components['schemas']['FindDomainResult'];

/**
 * Hook to fetch all domains
 * Automatically handles pagination to load all data
 */
export const useDomains = (
  params?: DomainListParams,
  options?: UseQueryOptions<DomainOut[], Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.DOMAINS, undefined, params),
    queryFn: () => domainService.list(params),
    ...options,
  });
};

/**
 * Hook to fetch a single page of domains
 */
export const useDomainsPage = (
  params?: DomainListParams,
  options?: UseQueryOptions<DomainOut[], Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.DOMAINS, 'page', params),
    queryFn: () => domainService.listPage(params),
    ...options,
  });
};

/**
 * Hook to fetch a single page of domains with pagination metadata
 */
export const useDomainsPageWithMetadata = (
  params?: DomainListParams,
  options?: UseQueryOptions<PaginatedResponse<DomainOut>, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.DOMAINS, 'page-metadata', params),
    queryFn: () => domainService.listPageWithMetadata(params),
    ...options,
  });
};

/**
 * Hook to fetch domains by layer ID
 */
export const useDomainsByLayer = (
  layerId: string,
  options?: UseQueryOptions<DomainOut[], Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.DOMAINS, undefined, { layer_id: layerId }),
    queryFn: () => domainService.list({ layer_id: layerId }),
    enabled: !!layerId,
    ...options,
  });
};

/**
 * Hook to fetch a specific domain by ID
 */
export const useDomain = (
  id: string,
  options?: UseQueryOptions<DomainOut, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.DOMAINS, id),
    queryFn: () => domainService.get(id),
    enabled: !!id,
    ...options,
  });
};

/**
 * Hook to search domains
 */
export const useDomainSearch = (
  params: DomainFindParams,
  options?: UseQueryOptions<FindDomainResult[], Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.FIND, QUERY_KEYS.DOMAINS, params),
    queryFn: () => domainService.find(params),
    enabled: !!params.query,
    ...options,
  });
};
