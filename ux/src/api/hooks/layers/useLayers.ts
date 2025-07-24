/**
 * Layers Query Hooks
 * 
 * React Query hooks for layer entities
 */

import { useQuery, UseQueryOptions } from '@tanstack/react-query';
import { layerService, type LayerListParams, type LayerFindParams } from '../../services/layers';
import { QUERY_KEYS } from '../../config';
import { createQueryKey } from '../../utils/queryClient';
import type { PaginatedResponse } from '../../services/base';
import type { components } from '../../client/types';

type LayerOut = components['schemas']['LayerOut'];
type FindLayerResult = components['schemas']['FindLayerResult'];

/**
 * Hook to fetch all layers
 * Automatically handles pagination to load all data
 */
export const useLayers = (
  params?: LayerListParams,
  options?: UseQueryOptions<LayerOut[], Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LAYERS, undefined, params),
    queryFn: () => layerService.list(params),
    ...options,
  });
};

/**
 * Hook to fetch a single page of layers
 */
export const useLayersPage = (
  params?: LayerListParams,
  options?: UseQueryOptions<LayerOut[], Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LAYERS, 'page', params),
    queryFn: () => layerService.listPage(params),
    ...options,
  });
};

/**
 * Hook to fetch a single page of layers with pagination metadata
 */
export const useLayersPageWithMetadata = (
  params?: LayerListParams,
  options?: UseQueryOptions<PaginatedResponse<LayerOut>, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LAYERS, 'page-metadata', params),
    queryFn: () => layerService.listPageWithMetadata(params),
    ...options,
  });
};

/**
 * Hook to fetch a specific layer by ID
 */
export const useLayer = (
  id: string,
  options?: UseQueryOptions<LayerOut, Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.LAYERS, id),
    queryFn: () => layerService.get(id),
    enabled: !!id,
    ...options,
  });
};

/**
 * Hook to search layers
 */
export const useLayerSearch = (
  params: LayerFindParams,
  options?: UseQueryOptions<FindLayerResult[], Error>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.FIND, QUERY_KEYS.LAYERS, params),
    queryFn: () => layerService.find(params),
    enabled: !!params.query,
    ...options,
  });
};
