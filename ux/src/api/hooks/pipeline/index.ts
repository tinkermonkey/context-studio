import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import {
  pipelineService,
  type PipelineFlavorCreate,
  type PipelineFlavorUpdate,
} from "@/api/services/pipeline";
import type { components } from "@/api/types";

type PipelineConfigurationCreate = components["schemas"]["PipelineConfigurationCreate"];
type PipelineConfigurationUpdate = components["schemas"]["PipelineConfigurationUpdate"];

export function usePipelines() {
  return useQuery({
    queryKey: QUERY_KEYS.pipelines,
    queryFn: () => pipelineService.listPipelines(),
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
    queryKey: ["allPipelineExecutions", status, limit, offset],
    queryFn: () => pipelineService.getAllPipelineExecutions(status, limit, offset),
  });
}

export function usePipelineFlavors() {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineFlavors,
    queryFn: () => pipelineService.listFlavors(),
  });
}

export function usePipelineFlavor(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineFlavor(id),
    queryFn: () => pipelineService.getFlavor(id),
    enabled: !!id,
  });
}

export function useCreatePipelineFlavor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PipelineFlavorCreate) => pipelineService.createFlavor(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineFlavors });
    },
  });
}

export function useUpdatePipelineFlavor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PipelineFlavorUpdate }) =>
      pipelineService.updateFlavor(id, data),
    onSuccess: (_result, { id }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineFlavors });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineFlavor(id) });
    },
  });
}

export function useDeletePipelineFlavor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => pipelineService.deleteFlavor(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineFlavors });
    },
  });
}

export function useCreatePipelineFromFlavor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ flavorId, title }: { flavorId: string; title: string }) =>
      pipelineService.createPipelineFromFlavor(flavorId, title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelines });
    },
  });
}
