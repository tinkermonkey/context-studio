import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService, type RunListParams } from "@/api/services/pipeline";

export function usePipelineRun(runId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineRun(runId),
    queryFn: () => pipelineService.getRun(runId),
    enabled: !!runId,
  });
}

export function usePipelineRuns(params?: RunListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineRuns(params),
    queryFn: () => pipelineService.listRuns(params),
  });
}
