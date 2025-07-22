import { useMutation, useQueryClient } from '@tanstack/react-query';
import { termService } from '../../services/terms';
import { apiLogger } from '../../utils/logger';
import { termsQueryKeys } from './useTerms';
import type { components } from '../../client/types';

// Type definitions
type TermOut = components['schemas']['TermOut'];
type TermCreate = components['schemas']['TermCreate'];
type TermUpdate = components['schemas']['TermUpdate'];

// Create term mutation
export function useCreateTerm() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: TermCreate): Promise<TermOut> => {
      apiLogger.info('Creating term', { data });
      const response = await termService.create(data);
      apiLogger.info('Term created successfully', { id: response.id });
      return response;
    },
    onSuccess: (data) => {
      // Invalidate and refetch terms list
      queryClient.invalidateQueries({ queryKey: termsQueryKeys.lists() });
      
      // Set the new term in the cache
      queryClient.setQueryData(termsQueryKeys.detail(data.id), data);
      
      // If the term belongs to a domain, invalidate domain-specific queries
      if (data.domain_id) {
        queryClient.invalidateQueries({ 
          queryKey: termsQueryKeys.list({ domain_id: data.domain_id }) 
        });
      }
      
      // If the term belongs to a layer, invalidate layer-specific queries
      if (data.layer_id) {
        queryClient.invalidateQueries({ 
          queryKey: termsQueryKeys.list({ layer_id: data.layer_id }) 
        });
      }
    },
    onError: (error) => {
      apiLogger.error('Failed to create term', { error });
    },
  });
}

// Update term mutation
export function useUpdateTerm() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: TermUpdate }): Promise<TermOut> => {
      apiLogger.info('Updating term', { id, data });
      const response = await termService.update(id, data);
      apiLogger.info('Term updated successfully', { id });
      return response;
    },
    onSuccess: (data, variables) => {
      // Update the specific term in the cache
      queryClient.setQueryData(termsQueryKeys.detail(variables.id), data);
      
      // Invalidate lists that might contain this term
      queryClient.invalidateQueries({ queryKey: termsQueryKeys.lists() });
      
      // If the term's domain changed, invalidate domain-specific queries
      if (data.domain_id) {
        queryClient.invalidateQueries({ 
          queryKey: termsQueryKeys.list({ domain_id: data.domain_id }) 
        });
      }
      
      // If the term's layer changed, invalidate layer-specific queries
      if (data.layer_id) {
        queryClient.invalidateQueries({ 
          queryKey: termsQueryKeys.list({ layer_id: data.layer_id }) 
        });
      }
    },
    onError: (error) => {
      apiLogger.error('Failed to update term', { error });
    },
  });
}

// Delete term mutation
export function useDeleteTerm() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      apiLogger.info('Deleting term', { id });
      await termService.delete(id);
      apiLogger.info('Term deleted successfully', { id });
    },
    onSuccess: (_, id) => {
      // Remove the term from the cache
      queryClient.removeQueries({ queryKey: termsQueryKeys.detail(id) });
      
      // Invalidate lists that might contain this term
      queryClient.invalidateQueries({ queryKey: termsQueryKeys.lists() });
      
      // Invalidate search results
      queryClient.invalidateQueries({ queryKey: termsQueryKeys.all });
    },
    onError: (error) => {
      apiLogger.error('Failed to delete term', { error });
    },
  });
}

// Bulk operations
export function useBulkDeleteTerms() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (ids: string[]): Promise<void> => {
      apiLogger.info('Bulk deleting terms', { ids, count: ids.length });
      await Promise.all(ids.map(id => termService.delete(id)));
      apiLogger.info('Terms bulk deleted successfully', { count: ids.length });
    },
    onSuccess: (_, ids) => {
      // Remove all terms from the cache
      ids.forEach(id => {
        queryClient.removeQueries({ queryKey: termsQueryKeys.detail(id) });
      });
      
      // Invalidate all term-related queries
      queryClient.invalidateQueries({ queryKey: termsQueryKeys.all });
    },
    onError: (error) => {
      apiLogger.error('Failed to bulk delete terms', { error });
    },
  });
}
