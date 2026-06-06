import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService, type RunListParams } from "@/api/services/pipeline";

export function usePipelineRun(runId: string, options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineRun(runId),
    queryFn: () => pipelineService.getRun(runId),
    enabled: !!runId,
    refetchInterval:
      options?.refetchInterval ??
      ((query) => {
        const status = query.state.data?.status;
        return status === "PENDING" || status === "RUNNING" ? 2000 : false;
      }),
  });
}

export function usePipelineRuns(params?: RunListParams) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineRuns(params),
    queryFn: () => pipelineService.listRuns(params),
  });
}
