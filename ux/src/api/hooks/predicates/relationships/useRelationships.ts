import { useQuery } from '@tanstack/react-query';
import { relationshipService } from '../../services/relationships';
import { apiLogger } from '../../utils/logger';
import type { components } from '../../client/types';

// Type definitions for relationships
type TermRelationshipOut = components['schemas']['TermRelationshipOut'];

// Query keys
export const relationshipsQueryKeys = {
  all: ['relationships'] as const,
  lists: () => [...relationshipsQueryKeys.all, 'list'] as const,
  list: (params?: any) => [...relationshipsQueryKeys.lists(), params] as const,
  details: () => [...relationshipsQueryKeys.all, 'detail'] as const,
  detail: (id: string) => [...relationshipsQueryKeys.details(), id] as const,
  byTerm: (termId: string) => [...relationshipsQueryKeys.all, 'byTerm', termId] as const,
  byPredicate: (predicate: string) => [...relationshipsQueryKeys.all, 'byPredicate', predicate] as const,
};

// List relationships hook - automatically handles pagination to load all data
export function useRelationships(params?: { 
  skip?: number; 
  limit?: number; 
  source_term_id?: string; 
  target_term_id?: string; 
  predicate?: string; 
}) {
  return useQuery({
    queryKey: relationshipsQueryKeys.list(params),
    queryFn: async (): Promise<TermRelationshipOut[]> => {
      apiLogger.info('Fetching relationships', { params });
      const response = await relationshipService.list(params);
      apiLogger.info('Relationships fetched successfully', { count: response.length });
      return response;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

// List single page of relationships hook
export function useRelationshipsPage(params?: { 
  skip?: number; 
  limit?: number; 
  source_term_id?: string; 
  target_term_id?: string; 
  predicate?: string; 
}) {
  return useQuery({
    queryKey: [...relationshipsQueryKeys.lists(), 'page', params],
    queryFn: async (): Promise<TermRelationshipOut[]> => {
      apiLogger.info('Fetching relationships page', { params });
      const response = await relationshipService.listPage(params);
      apiLogger.info('Relationships page fetched successfully', { count: response.length });
      return response;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

// Get single relationship hook
export function useRelationship(id: string, enabled = true) {
  return useQuery({
    queryKey: relationshipsQueryKeys.detail(id),
    queryFn: async (): Promise<TermRelationshipOut> => {
      apiLogger.info('Fetching relationship', { id });
      const response = await relationshipService.get(id);
      apiLogger.info('Relationship fetched successfully', { id, relationship: response });
      return response;
    },
    enabled: enabled && !!id,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

// Get relationships for a specific term (as source or target)
export function useTermRelationships(termId: string, enabled = true) {
  return useQuery({
    queryKey: relationshipsQueryKeys.byTerm(termId),
    queryFn: async (): Promise<TermRelationshipOut[]> => {
      apiLogger.info('Fetching relationships for term', { termId });
      
      // Fetch relationships where the term is either source or target
      const [asSource, asTarget] = await Promise.all([
        relationshipService.list({ source_term_id: termId }),
        relationshipService.list({ target_term_id: termId })
      ]);
      
      // Combine and deduplicate
      const allRelationships = [...asSource, ...asTarget];
      const uniqueRelationships = allRelationships.filter((rel, index, self) => 
        index === self.findIndex(r => r.id === rel.id)
      );
      
      apiLogger.info('Term relationships fetched successfully', { 
        termId, 
        count: uniqueRelationships.length,
        asSource: asSource.length,
        asTarget: asTarget.length
      });
      
      return uniqueRelationships;
    },
    enabled: enabled && !!termId,
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}

// Get relationships by predicate
export function useRelationshipsByPredicate(predicate: string, enabled = true) {
  return useQuery({
    queryKey: relationshipsQueryKeys.byPredicate(predicate),
    queryFn: async (): Promise<TermRelationshipOut[]> => {
      apiLogger.info('Fetching relationships by predicate', { predicate });
      const response = await relationshipService.list({ predicate });
      apiLogger.info('Relationships by predicate fetched successfully', { 
        predicate, 
        count: response.length 
      });
      return response;
    },
    enabled: enabled && !!predicate.trim(),
    staleTime: 1000 * 60 * 5, // 5 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
  });
}
