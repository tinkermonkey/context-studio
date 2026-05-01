/**
 * Individual Query Hooks
 *
 * React Query hooks for individual entities
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
} from "@tanstack/react-query";
import { individualService, type IndividualListParams } from "../../services/individual";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type { components } from "../../client/types";

type IndividualResponse = components["schemas"]["IndividualResponse"];
type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];
type IndividualUpdateRequest = components["schemas"]["IndividualUpdateRequest"];
type DataPropertyValueResponse = components["schemas"]["DataPropertyValueResponse"];

/**
 * Hook to fetch all individuals
 */
export const useIndividuals = (
  params?: IndividualListParams,
  options?: UseQueryOptions<IndividualResponse[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.INDIVIDUALS, undefined, params),
    queryFn: () => individualService.list(params),
    ...options,
  });
};

/**
 * Hook to fetch a specific individual by ID
 */
export const useIndividual = (
  id: string,
  options?: UseQueryOptions<IndividualResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.INDIVIDUALS, id),
    queryFn: () => individualService.get(id),
    enabled: !!id,
    ...options,
  });
};

/**
 * Hook to create a new individual
 */
export const useCreateIndividual = (
  options?: UseMutationOptions<IndividualResponse, Error, IndividualCreateRequest>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => individualService.create(data),
    onSuccess: (_newIndividual) => {
      // Invalidate individuals list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.INDIVIDUALS],
      });
    },
    ...options,
  });
};

/**
 * Hook to update an existing individual
 */
export const useUpdateIndividual = (
  options?: UseMutationOptions<
    IndividualResponse,
    Error,
    { id: string; data: IndividualUpdateRequest }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => individualService.update(id, data),
    onSuccess: (updatedIndividual) => {
      // Update specific individual cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.INDIVIDUALS, updatedIndividual.id),
        updatedIndividual,
      );
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.INDIVIDUALS],
      });
      // Invalidate inherited properties for this individual
      queryClient.invalidateQueries({
        queryKey: createQueryKey(
          `${QUERY_KEYS.INDIVIDUALS}_inherited_properties`,
          updatedIndividual.id,
        ),
      });
    },
    ...options,
  });
};

/**
 * Hook to delete an individual
 */
export const useDeleteIndividual = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => individualService.delete(id),
    onSuccess: () => {
      // Invalidate all individuals queries
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.INDIVIDUALS],
      });
    },
    ...options,
  });
};

/**
 * Hook to add a class to an individual
 */
export const useAddIndividualClass = (
  options?: UseMutationOptions<
    IndividualResponse,
    Error,
    { id: string; classId: string }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, classId }) => individualService.addClass(id, classId),
    onSuccess: (updatedIndividual) => {
      // Update individual cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.INDIVIDUALS, updatedIndividual.id),
        updatedIndividual,
      );
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.INDIVIDUALS],
      });
      // Invalidate inherited properties
      queryClient.invalidateQueries({
        queryKey: createQueryKey(
          `${QUERY_KEYS.INDIVIDUALS}_inherited_properties`,
          updatedIndividual.id,
        ),
      });
    },
    ...options,
  });
};

/**
 * Hook to remove a class from an individual
 */
export const useRemoveIndividualClass = (
  options?: UseMutationOptions<
    void,
    Error,
    { id: string; classId: string }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, classId }) => individualService.removeClass(id, classId),
    onSuccess: (_data, { id }) => {
      // Invalidate all individuals queries to refresh the data
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.INDIVIDUALS],
      });
      // Invalidate inherited properties since class removal changes the individual's inherited properties
      queryClient.invalidateQueries({
        queryKey: createQueryKey(
          `${QUERY_KEYS.INDIVIDUALS}_inherited_properties`,
          id,
        ),
      });
    },
    ...options,
  });
};

/**
 * Hook to set the order of classes for an individual
 */
export const useSetIndividualClasses = (
  options?: UseMutationOptions<
    IndividualResponse,
    Error,
    { id: string; classIds: string[] }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, classIds }) =>
      individualService.setClassOrder(id, classIds),
    onSuccess: (updatedIndividual) => {
      // Update individual cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.INDIVIDUALS, updatedIndividual.id),
        updatedIndividual,
      );
      // Invalidate list
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.INDIVIDUALS],
      });
      // Invalidate inherited properties
      queryClient.invalidateQueries({
        queryKey: createQueryKey(
          `${QUERY_KEYS.INDIVIDUALS}_inherited_properties`,
          updatedIndividual.id,
        ),
      });
    },
    ...options,
  });
};

/**
 * Hook to fetch inherited properties for an individual
 */
export const useIndividualInheritedProperties = (
  id: string,
  options?: UseQueryOptions<DataPropertyValueResponse[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      `${QUERY_KEYS.INDIVIDUALS}_inherited_properties`,
      id,
    ),
    queryFn: () => individualService.getInheritedProperties(id),
    enabled: !!id,
    ...options,
  });
};
