import { useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { sourcesService, type ExtractSourceRequest } from "@/api/services/sources";
import type { PipelineImplementation } from "@/api/services/pipeline";

/** Start extraction on a source; the runs it starts carry on in the background. */
export function useExtractSource() {
  const queryClient = useQueryClient();
  return useMutation({
    meta: { skipGlobalErrorToast: true },
    mutationFn: ({ sourceId, body }: { sourceId: string; body: ExtractSourceRequest }) =>
      sourcesService.extractSource(sourceId, body),
    // A source names its last extraction, so the list shows the new runs.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.sourcesRoot }),
  });
}

/**
 * Whether an implementation can extract a source. The server refuses (422) one
 * that cannot, e.g. one that reads pasted text only.
 */
export const canExtractSource = (implementation: PipelineImplementation) =>
  implementation.extracts_sources === true;
