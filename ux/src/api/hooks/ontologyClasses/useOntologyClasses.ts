/**
 * Ontology Class Query Hooks
 *
 * React Query hooks for ontology class entities
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import { ontologyClassService } from "../../services/ontologyClass";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type {
  OntologyClass,
  OntologyClassCreate,
  OntologyClassUpdate,
  OntologyClassListParams,
} from "../../types/ontology";

/**
 * Hook to fetch all ontology classes
 */
export const useOntologyClasses = (
  params?: OntologyClassListParams,
  options?: UseQueryOptions<OntologyClass[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.ONTOLOGY_CLASSES, undefined, params),
    queryFn: () => ontologyClassService.list(params),
    ...options,
  });
};

/**
 * Hook to fetch a specific ontology class by ID
 */
export const useOntologyClass = (
  id: string,
  options?: UseQueryOptions<OntologyClass, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.ONTOLOGY_CLASSES, id),
    queryFn: () => ontologyClassService.get(id),
    enabled: !!id,
    ...options,
  });
};

/**
 * Hook to create a new ontology class
 */
export const useCreateOntologyClass = (
  options?: UseMutationOptions<
    OntologyClass,
    Error,
    { schemeId: string; data: OntologyClassCreate }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ schemeId, data }) =>
      ontologyClassService.create(schemeId, data),
    onSuccess: (_newClass) => {
      // Invalidate ontology classes list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.ONTOLOGY_CLASSES],
      });
    },
    ...options,
  });
};

/**
 * Hook to update an existing ontology class
 */
export const useUpdateOntologyClass = (
  options?: UseMutationOptions<
    OntologyClass,
    Error,
    { id: string; data: OntologyClassUpdate }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => ontologyClassService.update(id, data),
    onSuccess: (updatedClass) => {
      // Update specific class cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.ONTOLOGY_CLASSES, updatedClass.id),
        updatedClass,
      );
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.ONTOLOGY_CLASSES],
      });
    },
    ...options,
  });
};

/**
 * Hook to delete an ontology class
 */
export const useDeleteOntologyClass = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => ontologyClassService.delete(id),
    onSuccess: () => {
      // Invalidate all ontology classes queries
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.ONTOLOGY_CLASSES],
      });
    },
    ...options,
  });
};
