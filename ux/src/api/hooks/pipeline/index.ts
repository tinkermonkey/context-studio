import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService } from "@/api/services/pipeline";
import type { components } from "@/api/types";

// TODO: These types are not yet in the OpenAPI spec (Phase 2 work)
type PipelineConfigurationCreate = any; // components["schemas"]["PipelineConfigurationCreate"];
type PipelineConfigurationUpdate = any; // components["schemas"]["PipelineConfigurationUpdate"];

export function usePipelines(refetchInterval?: number | false) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelines,
    queryFn: () => pipelineService.listPipelines(),
    refetchInterval,
  });
}

export function usePipeline(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.pipeline(id),
    queryFn: () => pipelineService.getPipeline(id),
    enabled: !!id,
  });
}

export function useCreatePipeline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PipelineConfigurationCreate) => pipelineService.createPipeline(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelines });
    },
  });
}

export function useUpdatePipeline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PipelineConfigurationUpdate }) =>
      pipelineService.updatePipeline(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelines });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipeline(id) });
    },
  });
}

export function useDeletePipeline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pipelineService.deletePipeline(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelines });
    },
  });
}

export function useExecutePipeline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, inputText }: { id: string; inputText: string }) =>
      pipelineService.executePipeline(id, inputText),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.pipelines,
      });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.pipelineExecutions(id),
      });
      queryClient.invalidateQueries({
        queryKey: ["all-pipeline-executions"],
      });
    },
  });
}

export function usePipelineExecutions(pipelineId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineExecutions(pipelineId),
    queryFn: () => pipelineService.getPipelineExecutions(pipelineId),
    enabled: !!pipelineId,
  });
}

export function useAllPipelineExecutions(status?: string, limit: number = 100, offset: number = 0) {
  return useQuery({
    queryKey: QUERY_KEYS.allPipelineExecutions(status, limit, offset),
    queryFn: () => pipelineService.getAllPipelineExecutions(status, limit, offset),
  });
}
