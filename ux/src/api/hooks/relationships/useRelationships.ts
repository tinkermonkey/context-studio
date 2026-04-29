/**
 * Relationship Query Hooks
 *
 * React Query hooks for relationship entities
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import { relationshipService } from "../../services/relationship";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type {
  Relationship,
  RelationshipCreate,
  RelationshipUpdate,
  RelationshipListParams,
} from "../../types/ontology";

/**
 * Hook to fetch all relationships
 */
export const useRelationships = (
  params?: RelationshipListParams,
  options?: UseQueryOptions<Relationship[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.RELATIONSHIPS, undefined, params),
    queryFn: () => relationshipService.list(params),
    ...options,
  });
};

/**
 * Hook to fetch a specific relationship by ID
 */
export const useRelationship = (
  id: string,
  options?: UseQueryOptions<Relationship, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.RELATIONSHIPS, id),
    queryFn: () => relationshipService.get(id),
    enabled: !!id,
    ...options,
  });
};

/**
 * Hook to create a new relationship
 */
export const useCreateRelationship = (
  options?: UseMutationOptions<Relationship, Error, RelationshipCreate>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => relationshipService.create(data),
    onSuccess: (newRelationship) => {
      // Invalidate relationships list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.RELATIONSHIPS],
      });
    },
    ...options,
  });
};

/**
 * Hook to update an existing relationship
 */
export const useUpdateRelationship = (
  options?: UseMutationOptions<
    Relationship,
    Error,
    { id: string; data: RelationshipUpdate }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => relationshipService.update(id, data),
    onSuccess: (updatedRelationship) => {
      // Update specific relationship cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.RELATIONSHIPS, updatedRelationship.id),
        updatedRelationship,
      );
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.RELATIONSHIPS],
      });
    },
    ...options,
  });
};

/**
 * Hook to delete a relationship
 */
export const useDeleteRelationship = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => relationshipService.delete(id),
    onSuccess: () => {
      // Invalidate all relationships queries
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.RELATIONSHIPS],
      });
    },
    ...options,
  });
};
