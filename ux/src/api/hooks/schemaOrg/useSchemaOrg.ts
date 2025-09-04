/**
 * Schema.org Query Hooks
 * 
 * React Query hooks for Schema.org entity and property operations
 */

import { useQuery, UseQueryOptions } from '@tanstack/react-query';
import { 
  schemaOrgService,
  type SchemaOrgStatus,
  type SchemaOrgEntityOut,
  type SchemaOrgPropertyOut,
  type SearchResult,
  type SchemaOrgEntityListParams,
  type SchemaOrgPropertyListParams,
  type SchemaOrgSearchParams
} from '../../services/schemaOrg';
import { QUERY_KEYS } from '../../config';
import { createQueryKey } from '../../utils/queryClient';

/**
 * Hook to get Schema.org database status
 */
export const useSchemaOrgStatus = (
  options?: UseQueryOptions<SchemaOrgStatus, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.SCHEMA_ORG, 'status'),
    queryFn: () => schemaOrgService.getStatus(),
    ...options,
  });
};

/**
 * Hook to list Schema.org entities
 */
export const useSchemaOrgEntities = (
  params?: SchemaOrgEntityListParams,
  options?: UseQueryOptions<SearchResult, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.SCHEMA_ORG, 'entities', params),
    queryFn: () => schemaOrgService.listEntities(params),
    ...options,
  });
};

/**
 * Hook to list Schema.org properties
 */
export const useSchemaOrgProperties = (
  params?: SchemaOrgPropertyListParams,
  options?: UseQueryOptions<SearchResult, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.SCHEMA_ORG, 'properties', params),
    queryFn: () => schemaOrgService.listProperties(params),
    ...options,
  });
};

/**
 * Hook to get a specific Schema.org entity by identifier
 */
export const useSchemaOrgEntity = (
  identifier: string,
  options?: UseQueryOptions<SchemaOrgEntityOut, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.SCHEMA_ORG, 'entity', { identifier }),
    queryFn: () => schemaOrgService.getEntity(identifier),
    enabled: !!identifier,
    ...options,
  });
};

/**
 * Hook to get a specific Schema.org property by identifier
 */
export const useSchemaOrgProperty = (
  identifier: string,
  options?: UseQueryOptions<SchemaOrgPropertyOut, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.SCHEMA_ORG, 'property', { identifier }),
    queryFn: () => schemaOrgService.getProperty(identifier),
    enabled: !!identifier,
    ...options,
  });
};

/**
 * Hook to search Schema.org entities and properties
 */
export const useSchemaOrgSearch = (
  params: SchemaOrgSearchParams,
  options?: UseQueryOptions<SearchResult, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.SCHEMA_ORG, 'search', params),
    queryFn: () => schemaOrgService.search(params),
    enabled: !!params.query?.trim(),
    ...options,
  });
};
