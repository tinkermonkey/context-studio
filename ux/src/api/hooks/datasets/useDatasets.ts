/**
 * Datasets Query Hooks
 *
 * React Query hooks for dataset entities
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import { datasetService } from "../../services/datasets";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";
import type { components } from "../../client/types";

type DatasetResponse = components["schemas"]["DatasetResponse"];
type ActionLogResponse = components["schemas"]["ActionLogResponse"];

/**
 * Hook to fetch all datasets
 */
export const useDatasets = (
  options?: UseQueryOptions<DatasetResponse[], Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.DATASETS),
    queryFn: () => datasetService.list(),
    ...options,
  });
};

/**
 * Hook to fetch a specific dataset by ID
 */
export const useDataset = (
  id: string,
  options?: UseQueryOptions<DatasetResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.DATASETS, id),
    queryFn: () => datasetService.get(id),
    enabled: !!id,
    ...options,
  });
};

/**
 * Hook to fetch the currently active dataset
 */
export const useActiveDataset = (
  options?: UseQueryOptions<DatasetResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.DATASETS, "active"),
    queryFn: () => datasetService.getActive(),
    ...options,
  });
};

/**
 * Hook to fetch the datasets directory path
 */
export const useDatasetsDirectory = (
  options?: UseQueryOptions<{ datasets_directory: string }, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.DATASETS, "directory"),
    queryFn: () =>
      datasetService.getDirectory() as Promise<{ datasets_directory: string }>,
    ...options,
  });
};

/**
 * Hook to fetch startup info
 */
export const useStartupInfo = (
  options?: UseQueryOptions<
    { dataset_id?: string; dataset_title?: string },
    Error
  >,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.DATASETS, "startup-info"),
    queryFn: () =>
      datasetService.getStartupInfo() as Promise<{
        dataset_id?: string;
        dataset_title?: string;
      }>,
    ...options,
  });
};

/**
 * Hook to fetch dataset action log
 */
export const useDatasetActionLog = (
  days?: number,
  options?: UseQueryOptions<ActionLogResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(
      QUERY_KEYS.DATASETS,
      "action-log",
      days ? { days } : undefined,
    ),
    queryFn: () => datasetService.getActionLog(days ? { days } : undefined),
    ...options,
  });
};
