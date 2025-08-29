import { useMutation, useQueryClient } from '@tanstack/react-query';
import { relationshipService } from '../../services/relationships';
import { apiLogger } from '../../utils/logger';
import { relationshipsQueryKeys } from './useRelationships';
import { termsQueryKeys } from '../terms/useTerms';
import type { components } from '../../client/types';

// Type definitions
type TermRelationshipOut = components['schemas']['TermRelationshipOut'];
type TermRelationshipCreate = components['schemas']['TermRelationshipCreate'];
type TermRelationshipUpdate = components['schemas']['TermRelationshipUpdate'];

// Create relationship mutation
export function useCreateRelationship() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: TermRelationshipCreate): Promise<TermRelationshipOut> => {
      apiLogger.info('Creating relationship', { data });
      const response = await relationshipService.create(data);
      apiLogger.info('Relationship created successfully', { id: response.id });
      return response;
    },
    onSuccess: (data) => {
      // Invalidate and refetch relationships list
      queryClient.invalidateQueries({ queryKey: relationshipsQueryKeys.lists() });
      
      // Set the new relationship in the cache
      queryClient.setQueryData(relationshipsQueryKeys.detail(data.id), data);
      
      // Invalidate relationship queries for the source and target terms
      queryClient.invalidateQueries({ 
        queryKey: relationshipsQueryKeys.byTerm(data.source_term_id) 
      });
      queryClient.invalidateQueries({ 
        queryKey: relationshipsQueryKeys.byTerm(data.target_term_id) 
      });
      
      // Invalidate predicate-specific queries
      queryClient.invalidateQueries({ 
        queryKey: relationshipsQueryKeys.byPredicate(data.predicate) 
      });
      
      // Invalidate term queries as relationships might affect term display
      queryClient.invalidateQueries({ 
        queryKey: termsQueryKeys.detail(data.source_term_id) 
      });
      queryClient.invalidateQueries({ 
        queryKey: termsQueryKeys.detail(data.target_term_id) 
      });
    },
    onError: (error) => {
      apiLogger.error('Failed to create relationship', { error });
    },
  });
}

// Update relationship mutation
export function useUpdateRelationship() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: TermRelationshipUpdate }): Promise<TermRelationshipOut> => {
      apiLogger.info('Updating relationship', { id, data });
      const response = await relationshipService.update(id, data);
      apiLogger.info('Relationship updated successfully', { id });
      return response;
    },
    onSuccess: (data, variables) => {
      // Update the specific relationship in the cache
      queryClient.setQueryData(relationshipsQueryKeys.detail(variables.id), data);
      
      // Invalidate lists that might contain this relationship
      queryClient.invalidateQueries({ queryKey: relationshipsQueryKeys.lists() });
      
      // Invalidate relationship queries for the source and target terms
      queryClient.invalidateQueries({ 
        queryKey: relationshipsQueryKeys.byTerm(data.source_term_id) 
      });
      queryClient.invalidateQueries({ 
        queryKey: relationshipsQueryKeys.byTerm(data.target_term_id) 
      });
      
      // Invalidate predicate-specific queries
      queryClient.invalidateQueries({ 
        queryKey: relationshipsQueryKeys.byPredicate(data.predicate) 
      });
      
      // Invalidate term queries as relationships might affect term display
      queryClient.invalidateQueries({ 
        queryKey: termsQueryKeys.detail(data.source_term_id) 
      });
      queryClient.invalidateQueries({ 
        queryKey: termsQueryKeys.detail(data.target_term_id) 
      });
    },
    onError: (error) => {
      apiLogger.error('Failed to update relationship', { error });
    },
  });
}

// Delete relationship mutation
export function useDeleteRelationship() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string): Promise<TermRelationshipOut | null> => {
      // Get the relationship data before deletion for cache invalidation
      const relationshipData = queryClient.getQueryData<TermRelationshipOut>(
        relationshipsQueryKeys.detail(id)
      );
      
      apiLogger.info('Deleting relationship', { id });
      await relationshipService.delete(id);
      apiLogger.info('Relationship deleted successfully', { id });
      
      return relationshipData || null;
    },
    onSuccess: (relationshipData, id) => {
      // Remove the relationship from the cache
      queryClient.removeQueries({ queryKey: relationshipsQueryKeys.detail(id) });
      
      // Invalidate lists that might contain this relationship
      queryClient.invalidateQueries({ queryKey: relationshipsQueryKeys.lists() });
      
      // If we have the relationship data, invalidate specific queries
      if (relationshipData) {
        queryClient.invalidateQueries({ 
          queryKey: relationshipsQueryKeys.byTerm(relationshipData.source_term_id) 
        });
        queryClient.invalidateQueries({ 
          queryKey: relationshipsQueryKeys.byTerm(relationshipData.target_term_id) 
        });
        queryClient.invalidateQueries({ 
          queryKey: relationshipsQueryKeys.byPredicate(relationshipData.predicate) 
        });
        
        // Invalidate term queries as relationships might affect term display
        queryClient.invalidateQueries({ 
          queryKey: termsQueryKeys.detail(relationshipData.source_term_id) 
        });
        queryClient.invalidateQueries({ 
          queryKey: termsQueryKeys.detail(relationshipData.target_term_id) 
        });
      } else {
        // If we don't have the relationship data, invalidate broader queries
        queryClient.invalidateQueries({ queryKey: relationshipsQueryKeys.all });
        queryClient.invalidateQueries({ queryKey: termsQueryKeys.all });
      }
    },
    onError: (error) => {
      apiLogger.error('Failed to delete relationship', { error });
    },
  });
}

// Bulk operations
export function useBulkDeleteRelationships() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (ids: string[]): Promise<void> => {
      apiLogger.info('Bulk deleting relationships', { ids, count: ids.length });
      await Promise.all(ids.map(id => relationshipService.delete(id)));
      apiLogger.info('Relationships bulk deleted successfully', { count: ids.length });
    },
    onSuccess: (_, ids) => {
      // Remove all relationships from the cache
      ids.forEach(id => {
        queryClient.removeQueries({ queryKey: relationshipsQueryKeys.detail(id) });
      });
      
      // Invalidate all relationship-related queries
      queryClient.invalidateQueries({ queryKey: relationshipsQueryKeys.all });
      
      // Invalidate all term queries as relationships might affect term display
      queryClient.invalidateQueries({ queryKey: termsQueryKeys.all });
    },
    onError: (error) => {
      apiLogger.error('Failed to bulk delete relationships', { error });
    },
  });
}

// Create multiple relationships at once
export function useBulkCreateRelationships() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (relationships: TermRelationshipCreate[]): Promise<TermRelationshipOut[]> => {
      apiLogger.info('Bulk creating relationships', { count: relationships.length });
      const results = await Promise.all(
        relationships.map(data => relationshipService.create(data))
      );
      apiLogger.info('Relationships bulk created successfully', { count: results.length });
      return results;
    },
    onSuccess: (data) => {
      // Add all new relationships to the cache
      data.forEach(relationship => {
        queryClient.setQueryData(relationshipsQueryKeys.detail(relationship.id), relationship);
      });
      
      // Invalidate all relationship-related queries
      queryClient.invalidateQueries({ queryKey: relationshipsQueryKeys.all });
      
      // Invalidate term queries for all affected terms
      const affectedTermIds = new Set<string>();
      data.forEach(rel => {
        affectedTermIds.add(rel.source_term_id);
        affectedTermIds.add(rel.target_term_id);
      });
      
      affectedTermIds.forEach(termId => {
        queryClient.invalidateQueries({ queryKey: termsQueryKeys.detail(termId) });
      });
    },
    onError: (error) => {
      apiLogger.error('Failed to bulk create relationships', { error });
    },
  });
}
