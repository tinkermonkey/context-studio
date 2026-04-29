/**
 * Property Definition Query Hooks
 *
 * React Query hooks for property definition entities
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import { propertyDefinitionService } from "../../services/propertyDefinition";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type {
  PropertyDefinition,
  PropertyDefinitionCreate,
  PropertyDefinitionUpdate,
  PropertyDefinitionListParams,
} from "../../types/ontology";

/**
 * Hook to fetch all property definitions
 */
export const usePropertyDefinitions = (
  params?: PropertyDefinitionListParams,
  options?: UseQueryOptions<PropertyDefinition[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.PROPERTY_DEFINITIONS,
      undefined,
      params,
    ),
    queryFn: () => propertyDefinitionService.list(params),
    ...options,
  });
};

/**
 * Hook to fetch a specific property definition by ID
 */
export const usePropertyDefinition = (
  id: string,
  options?: UseQueryOptions<PropertyDefinition, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.PROPERTY_DEFINITIONS, id),
    queryFn: () => propertyDefinitionService.get(id),
    enabled: !!id,
    ...options,
  });
};

/**
 * Hook to create a new property definition
 */
export const useCreatePropertyDefinition = (
  options?: UseMutationOptions<PropertyDefinition, Error, PropertyDefinitionCreate>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => propertyDefinitionService.create(data),
    onSuccess: (newProperty) => {
      // Invalidate property definitions list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.PROPERTY_DEFINITIONS],
      });
    },
    ...options,
  });
};

/**
 * Hook to update an existing property definition
 */
export const useUpdatePropertyDefinition = (
  options?: UseMutationOptions<
    PropertyDefinition,
    Error,
    { id: string; data: PropertyDefinitionUpdate }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) =>
      propertyDefinitionService.update(id, data),
    onSuccess: (updatedProperty) => {
      // Update specific property cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.PROPERTY_DEFINITIONS, updatedProperty.id),
        updatedProperty,
      );
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.PROPERTY_DEFINITIONS],
      });
    },
    ...options,
  });
};

/**
 * Hook to delete a property definition
 */
export const useDeletePropertyDefinition = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => propertyDefinitionService.delete(id),
    onSuccess: () => {
      // Invalidate all property definitions queries
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.PROPERTY_DEFINITIONS],
      });
    },
    ...options,
  });
};
