import { useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService, type ApplyParams } from "@/api/services/pipeline";
import type { components } from "@/api/types";

type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];

export function useRunPipeline() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ type, request }: { type: string; request: PipelineRunRequest }) =>
      pipelineService.runPipeline(type, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineRuns() });
    },
  });
}

export function useApplyRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, params }: { runId: string; params: ApplyParams }) =>
      pipelineService.applyRun(runId, params),
    onSuccess: (_result, { runId }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineRun(runId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineRuns() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineCandidates(runId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classes() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.relationships() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individuals() });
    },
  });
}

export function useRevertRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => pipelineService.revertRun(runId),
    onSuccess: (_result, runId) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineRun(runId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineRuns() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.classes() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.relationships() });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.properties });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.individuals() });
    },
  });
}
