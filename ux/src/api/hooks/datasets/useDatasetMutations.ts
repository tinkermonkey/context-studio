/**
 * Dataset Mutation Hooks
 *
 * React Query mutation hooks for dataset operations
 */

import {
  useMutation,
  useQueryClient,
  UseMutationOptions,
} from "@tanstack/react-query";
import {
  datasetService,
  type DatasetResponse,
  type CreateDatasetRequest,
  type AddExistingDatasetRequest,
  type UpdateDatasetDirectoryRequest,
} from "../../services/datasets";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to create a new dataset
 */
export const useCreateDataset = (
  options?: UseMutationOptions<DatasetResponse, Error, CreateDatasetRequest>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateDatasetRequest) => datasetService.create(data),
    onSuccess: () => {
      // Invalidate and refetch datasets list
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS),
      });
    },
    ...options,
  });
};

/**
 * Hook to delete a dataset
 */
export const useDeleteDataset = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => datasetService.delete(id),
    onSuccess: (_, deletedId) => {
      // Remove the specific dataset from cache
      queryClient.removeQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS, deletedId),
      });
      // Invalidate datasets list
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS),
      });
      // Invalidate active dataset in case it was the deleted one
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS, "active"),
      });
    },
    ...options,
  });
};

/**
 * Hook to activate a dataset
 */
export const useActivateDataset = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => datasetService.activate(id),
    onSuccess: () => {
      // Invalidate active dataset and datasets list (to update is_active flags)
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS, "active"),
      });
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS),
      });

      // Also invalidate other data that depends on the active dataset
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.LAYERS),
      });
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DOMAINS),
      });
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.TERMS),
      });
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.RELATIONSHIPS),
      });
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.GRAPH),
      });
    },
    ...options,
  });
};

/**
 * Hook to forget a dataset
 */
export const useForgetDataset = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => datasetService.forget(id),
    onSuccess: (_, forgottenId) => {
      // Remove the specific dataset from cache
      queryClient.removeQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS, forgottenId),
      });
      // Invalidate datasets list
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS),
      });
      // Invalidate active dataset in case it was the forgotten one
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS, "active"),
      });
    },
    ...options,
  });
};

/**
 * Hook to add an existing dataset
 */
export const useAddExistingDataset = (
  options?: UseMutationOptions<
    DatasetResponse,
    Error,
    AddExistingDatasetRequest
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AddExistingDatasetRequest) =>
      datasetService.addExisting(data),
    onSuccess: () => {
      // Invalidate and refetch datasets list
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS),
      });
    },
    ...options,
  });
};

/**
 * Hook to update the datasets directory
 */
export const useUpdateDatasetsDirectory = (
  options?: UseMutationOptions<
    { success: boolean; message: string },
    Error,
    UpdateDatasetDirectoryRequest
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateDatasetDirectoryRequest) =>
      datasetService.updateDirectory(data),
    onSuccess: () => {
      // Invalidate directory info
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS, "directory"),
      });
      // Invalidate datasets list as the directory change might affect available datasets
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.DATASETS),
      });
    },
    ...options,
  });
};
