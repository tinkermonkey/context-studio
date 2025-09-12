/**
 * Pipeline Flavors Mutation Hooks
 *
 * React Query mutation hooks for LLM pipeline flavor operations
 */

import {
  useMutation,
  useQueryClient,
  UseMutationOptions,
} from "@tanstack/react-query";
import {
  pipelineFlavorService,
  type PipelineFlavor,
  type CreatePipelineFlavorRequest,
  type UpdatePipelineFlavorRequest,
} from "../../services/pipelineFlavors";
import { QUERY_KEYS } from "../../config";
import { createQueryKey } from "../../utils/queryClient";

/**
 * Hook to create a new pipeline flavor
 */
export const useCreatePipelineFlavor = (
  options?: UseMutationOptions<
    PipelineFlavor,
    Error,
    CreatePipelineFlavorRequest
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreatePipelineFlavorRequest) =>
      pipelineFlavorService.create(data),
    onSuccess: (createdFlavor, variables) => {
      // Invalidate all pipeline flavors queries, including filtered lists
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.PIPELINE_FLAVORS],
        exact: false,
      });
      // Also invalidate the specific pipeline type list that was just updated
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PIPELINE_FLAVORS, "list", {
          pipeline: variables.pipeline,
        }),
      });
    },
    ...options,
  });
};

/**
 * Hook to update a pipeline flavor
 */
export const useUpdatePipelineFlavor = (
  options?: UseMutationOptions<
    PipelineFlavor,
    Error,
    { id: string; data: UpdatePipelineFlavorRequest }
  >,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: string;
      data: UpdatePipelineFlavorRequest;
    }) => pipelineFlavorService.update(id, data),
    onSuccess: (updatedFlavor, { id }) => {
      // Invalidate the specific pipeline flavor detail
      queryClient.invalidateQueries({
        queryKey: createQueryKey(QUERY_KEYS.PIPELINE_FLAVORS, "detail", { id }),
      });
      // Invalidate all pipeline flavors queries (including filtered lists)
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.PIPELINE_FLAVORS],
        exact: false,
      });
    },
    ...options,
  });
};

/**
 * Hook to delete a pipeline flavor
 */
export const useDeletePipelineFlavor = (
  options?: UseMutationOptions<void, Error, string>,
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => pipelineFlavorService.delete(id),
    onSuccess: (_, deletedId) => {
      // Remove the specific pipeline flavor from cache
      queryClient.removeQueries({
        queryKey: createQueryKey(QUERY_KEYS.PIPELINE_FLAVORS, "detail", {
          id: deletedId,
        }),
      });
      // Invalidate all pipeline flavors queries (including filtered lists)
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.PIPELINE_FLAVORS],
        exact: false,
      });
    },
    ...options,
  });
};
