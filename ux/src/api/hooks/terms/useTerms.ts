import { useQuery } from '@tanstack/react-query';
import { termService } from '../../services/terms';
import { apiLogger } from '../../utils/logger';
import type { PaginatedResponse } from '../../services/base';
import type { components } from '../../client/types';

// Type definitions for terms
type TermOut = components['schemas']['TermOut'];
type FindTermResult = components['schemas']['FindTermResult'];

// Query keys
export const termsQueryKeys = {
  all: ['terms'] as const,
  lists: () => [...termsQueryKeys.all, 'list'] as const,
  list: (params?: any) => [...termsQueryKeys.lists(), params] as const,
  details: () => [...termsQueryKeys.all, 'detail'] as const,
  detail: (id: string) => [...termsQueryKeys.details(), id] as const,
  search: (query: string) => [...termsQueryKeys.all, 'search', query] as const,
};

// List terms hook - automatically handles pagination to load all data
export function useTerms(params?: { 
  skip?: number; 
  limit?: number; 
  domain_id?: string; 
  layer_id?: string; 
}) {
  return useQuery({
    queryKey: termsQueryKeys.list(params),
    queryFn: async (): Promise<TermOut[]> => {
      apiLogger.info('Fetching terms', { params });
      const response = await termService.list(params);
      apiLogger.info('Terms fetched successfully', { count: response.length });
      return response;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

// List single page of terms hook
export function useTermsPage(params?: { 
  skip?: number; 
  limit?: number; 
  domain_id?: string; 
  layer_id?: string; 
}) {
  return useQuery({
    queryKey: [...termsQueryKeys.lists(), 'page', params],
    queryFn: async (): Promise<TermOut[]> => {
      apiLogger.info('Fetching terms page', { params });
      const response = await termService.listPage(params);
      apiLogger.info('Terms page fetched successfully', { count: response.length });
      return response;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

// List single page of terms with metadata hook
export function useTermsPageWithMetadata(params?: { 
  skip?: number; 
  limit?: number; 
  domain_id?: string; 
  layer_id?: string; 
}) {
  return useQuery({
    queryKey: [...termsQueryKeys.lists(), 'page-metadata', params],
    queryFn: async (): Promise<PaginatedResponse<TermOut>> => {
      apiLogger.info('Fetching terms page with metadata', { params });
      const response = await termService.listPageWithMetadata(params);
      apiLogger.info('Terms page with metadata fetched successfully', { 
        count: response.data.length, 
        total: response.total,
        skip: response.skip,
        limit: response.limit
      });
      return response;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

// Get single term hook
export function useTerm(id: string, enabled = true) {
  return useQuery({
    queryKey: termsQueryKeys.detail(id),
    queryFn: async (): Promise<TermOut> => {
      apiLogger.info('Fetching term', { id });
      const response = await termService.get(id);
      apiLogger.info('Term fetched successfully', { id, term: response });
      return response;
    },
    enabled: enabled && !!id,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

// Search terms hook
export function useTermsSearch(query: string, enabled = true) {
  return useQuery({
    queryKey: termsQueryKeys.search(query),
    queryFn: async (): Promise<FindTermResult[]> => {
      apiLogger.info('Searching terms', { query });
      const response = await termService.find({ query });
      apiLogger.info('Terms search completed', { query, count: response.length });
      return response;
    },
    enabled: enabled && !!query.trim(),
    staleTime: 1000 * 60 * 2, // 2 minutes for search results
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
  });
}
