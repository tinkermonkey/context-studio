/**
 * Pipeline Execution Hooks
 *
 * React Query hooks for the new unified pipeline execution system
 */

import { useMutation, UseMutationOptions } from "@tanstack/react-query";
import {
  pipelineExecutionService,
  type GenericPipelineExecutionRequest,
  type GenericPipelineExecutionResponse,
  type StreamingChunk,
} from "../../services/pipelineExecution";

/**
 * Hook to execute a pipeline using the new generic execution system
 */
export const usePipelineExecutionMutation = (
  options?: UseMutationOptions<
    GenericPipelineExecutionResponse,
    Error,
    GenericPipelineExecutionRequest
  >,
) => {
  return useMutation({
    mutationFn: (request: GenericPipelineExecutionRequest) =>
      pipelineExecutionService.executePipeline(request),
    ...options,
  });
};

/**
 * Hook to execute a pipeline with streaming response
 */
export const usePipelineExecutionStreamMutation = (
  onChunk?: (chunk: StreamingChunk) => void,
  options?: UseMutationOptions<
    GenericPipelineExecutionResponse,
    Error,
    GenericPipelineExecutionRequest
  >,
) => {
  return useMutation({
    mutationFn: (request: GenericPipelineExecutionRequest) =>
      pipelineExecutionService.executePipelineStream(request, onChunk),
    ...options,
  });
};

/**
 * Hook to execute multiple pipeline flavors in parallel
 */
export const useBatchPipelineExecutionMutation = (
  options?: UseMutationOptions<
    GenericPipelineExecutionResponse[],
    Error,
    GenericPipelineExecutionRequest[]
  >,
) => {
  return useMutation({
    mutationFn: async (requests: GenericPipelineExecutionRequest[]) => {
      const promises = requests.map(request =>
        pipelineExecutionService.executePipeline(request)
      );
      return Promise.all(promises);
    },
    ...options,
  });
};

/**
 * Hook to execute multiple pipeline flavors with streaming
 */
export const useBatchPipelineExecutionStreamMutation = (
  onChunk?: (chunk: StreamingChunk & { flavorId: string }) => void,
  options?: UseMutationOptions<
    GenericPipelineExecutionResponse[],
    Error,
    GenericPipelineExecutionRequest[]
  >,
) => {
  return useMutation({
    mutationFn: async (requests: GenericPipelineExecutionRequest[]) => {
      const promises = requests.map(request =>
        pipelineExecutionService.executePipelineStream(request, (chunk) => {
          onChunk?.({ ...chunk, flavorId: request.flavor_id });
        })
      );
      return Promise.all(promises);
    },
    ...options,
  });
};