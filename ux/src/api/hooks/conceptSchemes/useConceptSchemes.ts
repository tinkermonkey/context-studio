/**
 * Concept Scheme Query Hooks
 *
 * React Query hooks for concept scheme entities
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import { conceptSchemeService } from "../../services/conceptScheme";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type {
  ConceptScheme,
  ConceptSchemeCreate,
  ConceptSchemeUpdate,
  ConceptSchemeListParams,
} from "../../types/ontology";

/**
 * Hook to fetch all concept schemes
 */
export const useConceptSchemes = (
  params?: ConceptSchemeListParams,
  options?: UseQueryOptions<ConceptScheme[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.CONCEPT_SCHEMES, undefined, params),
    queryFn: () => conceptSchemeService.list(params),
    ...options,
  });
};

/**
 * Hook to fetch a specific concept scheme by ID
 */
export const useConceptScheme = (
  id: string,
  options?: UseQueryOptions<ConceptScheme, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.CONCEPT_SCHEMES, id),
    queryFn: () => conceptSchemeService.get(id),
    enabled: !!id,
    ...options,
  });
};

/**
 * Hook to create a new concept scheme
 */
export const useCreateConceptScheme = (
  options?: UseMutationOptions<
    ConceptScheme,
    Error,
    { taxonomyId: string; data: ConceptSchemeCreate }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ taxonomyId, data }) =>
      conceptSchemeService.create(taxonomyId, data),
    onSuccess: (newScheme) => {
      // Invalidate concept schemes list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.CONCEPT_SCHEMES],
      });
    },
    ...options,
  });
};

/**
 * Hook to update an existing concept scheme
 */
export const useUpdateConceptScheme = (
  options?: UseMutationOptions<
    ConceptScheme,
    Error,
    { id: string; data: ConceptSchemeUpdate }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => conceptSchemeService.update(id, data),
    onSuccess: (updatedScheme) => {
      // Update specific scheme cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.CONCEPT_SCHEMES, updatedScheme.id),
        updatedScheme,
      );
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.CONCEPT_SCHEMES],
      });
    },
    ...options,
  });
};

/**
 * Hook to delete a concept scheme
 */
export const useDeleteConceptScheme = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => conceptSchemeService.delete(id),
    onSuccess: () => {
      // Invalidate all concept schemes queries
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.CONCEPT_SCHEMES],
      });
    },
    ...options,
  });
};
