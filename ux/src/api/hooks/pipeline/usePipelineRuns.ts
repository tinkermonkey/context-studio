import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService, type RunListParams } from "@/api/services/pipeline";
import type { components } from "@/api/types";

export type CandidateResponse = components["schemas"]["CandidateResponse"];

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

export function usePipelineCandidates(runId: string, enabled?: boolean) {
  return useQuery<CandidateResponse[]>({
    queryKey: QUERY_KEYS.pipelineCandidates(runId),
    queryFn: () => pipelineService.getCandidates(runId),
    enabled: !!runId && enabled !== false,
  });
}

export function usePipelineRunChangeEvents(
  runId: string,
  options?: { offset?: number; limit?: number; enabled?: boolean },
) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineRunChangeEvents(runId, options),
    queryFn: () =>
      pipelineService.getRunChangeEvents(runId, options?.offset || 0, options?.limit || 100),
    enabled: !!runId && options?.enabled !== false,
  });
}
