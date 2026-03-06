/**
 * Pipeline Execution Hooks
 *
 * React Query hooks for the new unified pipeline execution system
 */

import { useMutation, UseMutationOptions } from "@tanstack/react-query";
import {
  pipelineExecutionService,
  type PipelineExecutionRequest,
  type PipelineExecutionResponse,
  type StreamingChunk,
} from "../../services/pipelineExecution";

/**
 * Hook to execute a pipeline using the new generic execution system
 */
export const usePipelineExecutionMutation = (
  options?: UseMutationOptions<
    PipelineExecutionResponse,
    Error,
    PipelineExecutionRequest
  >,
) => {
  return useMutation({
    mutationFn: (request: PipelineExecutionRequest) =>
      pipelineExecutionService.executePipeline(request),
    ...options,
  });
};

/**
 * Hook to execute a pipeline with streaming response
 */
export const usePipelineExecutionStreamMutation = (
  options?: UseMutationOptions<
    PipelineExecutionResponse,
    Error,
    PipelineExecutionRequest
  >,
) => {
  return useMutation({
    mutationFn: (request: PipelineExecutionRequest) =>
      pipelineExecutionService.executePipeline(request),
    ...options,
  });
};

/**
 * Hook to execute multiple pipeline flavors in parallel
 */
export const useBatchPipelineExecutionMutation = (
  options?: UseMutationOptions<
    PipelineExecutionResponse[],
    Error,
    PipelineExecutionRequest[]
  >,
) => {
  return useMutation({
    mutationFn: async (requests: PipelineExecutionRequest[]) => {
      const promises = requests.map((request) =>
        pipelineExecutionService.executePipeline(request),
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
  options?: UseMutationOptions<
    PipelineExecutionResponse[],
    Error,
    PipelineExecutionRequest[]
  >,
) => {
  return useMutation({
    mutationFn: async (requests: PipelineExecutionRequest[]) => {
      const promises = requests.map((request) =>
        pipelineExecutionService.executePipeline(request),
      );
      return Promise.all(promises);
    },
    ...options,
  });
};
