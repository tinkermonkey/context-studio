import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { ApiError } from "@/api/client/interceptors";
import { pipelineService } from "@/api/services/pipeline";
import { hasRunStatus } from "@/api/hooks/pipeline/runStatus";

/** How often an unfinished extraction run is re-read for its chunk progress. */
export const RUN_POLL_MS = 2000;
/** Retries for a run read that failed for a reason other than a missing run. */
const MAX_RETRIES = 2;

/** True while a run is pending or running: the only states it can move on from. */
export function isRunActive(status: string | null | undefined): boolean {
  return hasRunStatus(status, "pending", "running");
}

/**
 * True once a run has stopped: completed, failed, cancelled, interrupted (the
 * app closed while it ran) or any other state that is not pending or running.
 */
export function isRunFinished(status: string | null | undefined): boolean {
  return !isRunActive(status);
}

/**
 * A source extraction run, re-read until it finishes. A run that can't be
 * read stops the polling: a missing one (404) is not retried at all.
 */
export function useExtractionRun(runId: string | undefined) {
  return useQuery({
    queryKey: QUERY_KEYS.pipelineRun(runId ?? ""),
    queryFn: () => pipelineService.getRun(runId!),
    enabled: !!runId,
    retry: (failures, error) =>
      !(error instanceof ApiError && error.status === 404) && failures < MAX_RETRIES,
    refetchInterval: (query) => {
      if (query.state.status === "error") return false;
      const data = query.state.data;
      return data && isRunFinished(data.status) ? false : RUN_POLL_MS;
    },
  });
}

/** Cancel a run; it stops at its next chunk and the poll picks up `cancelled`. */
export function useCancelExtractionRun() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: (runId: string) => pipelineService.cancelRun(runId),
    onSuccess: (_run, runId) =>
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.pipelineRun(runId) }),
  });
}
