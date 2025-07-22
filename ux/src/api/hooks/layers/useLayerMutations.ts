/**
 * Layers Mutation Hooks
 * 
 * React Query mutation hooks for layer entities
 */

import { useMutation, useQueryClient, UseMutationOptions } from '@tanstack/react-query';
import { layerService } from '../../services/layers';
import { QUERY_KEYS } from '../../config';
import { createQueryKey } from '../../utils/queryClient';
import type { components } from '../../client/types';

type LayerOut = components['schemas']['LayerOut'];
type LayerCreate = components['schemas']['LayerCreate'];
type LayerUpdate = components['schemas']['LayerUpdate'];

/**
 * Hook to create a new layer
 */
export const useCreateLayer = (
  options?: UseMutationOptions<LayerOut, Error, LayerCreate>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: LayerCreate) => layerService.create(data),
    onSuccess: (data) => {
      // Update the layers list cache
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.LAYERS],
      });
      
      // Add the new layer to the cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.LAYERS, data.id),
        data
      );
    },
    ...options,
  });
};

/**
 * Hook to update an existing layer
 */
export const useUpdateLayer = (
  options?: UseMutationOptions<LayerOut, Error, { id: string; data: LayerUpdate }>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: LayerUpdate }) => 
      layerService.update(id, data),
    onSuccess: (data, variables) => {
      // Update the specific layer in cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.LAYERS, variables.id),
        data
      );
      
      // Invalidate the layers list to refresh it
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.LAYERS],
      });
    },
    ...options,
  });
};

/**
 * Hook to delete a layer
 */
export const useDeleteLayer = (
  options?: UseMutationOptions<void, Error, string>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => layerService.delete(id),
    onSuccess: (_, id) => {
      // Remove the layer from cache
      queryClient.removeQueries({
        queryKey: createQueryKey(QUERY_KEYS.LAYERS, id),
      });
      
      // Invalidate the layers list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.LAYERS],
      });
      
      // Also invalidate related domains and terms
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.DOMAINS],
      });
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.TERMS],
      });
    },
    ...options,
  });
};
