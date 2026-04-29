/**
 * Taxonomy Query Hooks
 *
 * React Query hooks for taxonomy entities
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import { taxonomyService } from "../../services/taxonomy";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type {
  Taxonomy,
  TaxonomyCreate,
  TaxonomyUpdate,
  TaxonomyListParams,
} from "../../types/ontology";

/**
 * Hook to fetch all taxonomies
 */
export const useTaxonomies = (
  params?: TaxonomyListParams,
  options?: UseQueryOptions<Taxonomy[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.TAXONOMIES, undefined, params),
    queryFn: () => taxonomyService.list(params),
    ...options,
  });
};

/**
 * Hook to fetch a specific taxonomy by ID
 */
export const useTaxonomy = (
  id: string,
  options?: UseQueryOptions<Taxonomy, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.TAXONOMIES, id),
    queryFn: () => taxonomyService.get(id),
    enabled: !!id,
    ...options,
  });
};

/**
 * Hook to create a new taxonomy
 */
export const useCreateTaxonomy = (
  options?: UseMutationOptions<Taxonomy, Error, TaxonomyCreate>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => taxonomyService.create(data),
    onSuccess: (_newTaxonomy) => {
      // Invalidate taxonomies list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.TAXONOMIES],
      });
    },
    ...options,
  });
};

/**
 * Hook to update an existing taxonomy
 */
export const useUpdateTaxonomy = (
  options?: UseMutationOptions<
    Taxonomy,
    Error,
    { id: string; data: TaxonomyUpdate }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => taxonomyService.update(id, data),
    onSuccess: (updatedTaxonomy) => {
      // Update specific taxonomy cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.TAXONOMIES, updatedTaxonomy.id),
        updatedTaxonomy,
      );
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.TAXONOMIES],
      });
    },
    ...options,
  });
};

/**
 * Hook to delete a taxonomy
 */
export const useDeleteTaxonomy = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => taxonomyService.delete(id),
    onSuccess: () => {
      // Invalidate all taxonomies queries
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.TAXONOMIES],
      });
    },
    ...options,
  });
};
