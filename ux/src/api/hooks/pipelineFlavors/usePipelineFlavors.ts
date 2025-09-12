/**
 * Pipeline Flavors Query Hooks
 *
 * React Query hooks for LLM pipeline flavor operations
 */

import { useQuery, UseQueryOptions } from "@tanstack/react-query";
import {
  pipelineFlavorService,
  type PipelineFlavor,
  type PipelineFlavorListResponse,
  type ListFlavorsParams,
} from "../../services/pipelineFlavors";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to list all pipeline flavors
 */
export const usePipelineFlavors = (
  params?: ListFlavorsParams,
  options?: UseQueryOptions<PipelineFlavorListResponse, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.PIPELINE_FLAVORS, "list", params),
    queryFn: () => pipelineFlavorService.list(params),
    ...options,
  });
};

/**
 * Hook to get a specific pipeline flavor by ID
 */
export const usePipelineFlavor = (
  id: string,
  options?: UseQueryOptions<PipelineFlavor, Error>,
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.PIPELINE_FLAVORS, "detail", { id }),
    queryFn: () => pipelineFlavorService.get(id),
    enabled: !!id,
    ...options,
  });
};
