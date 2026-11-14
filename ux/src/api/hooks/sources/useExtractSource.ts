import { useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { sourcesService, type ExtractSourceRequest } from "@/api/services/sources";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";
import { usePipelineImplementations } from "@/api/hooks/pipeline/usePipelineImplementations";

const INDIVIDUAL_EXTRACTION = "individual_extraction";

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
 * The individual_extraction implementations that can extract a source: those
 * that name the configuration they extract one with. The server refuses (422)
 * any other, e.g. one that reads pasted text only.
 */
export function useExtractionImplementations() {
  const { data, isLoading } = usePipelineImplementations(INDIVIDUAL_EXTRACTION);
  return {
    implementations: (data ?? []).filter((i) => !!i.source_configuration),
    isLoading,
  };
}

/**
 * The enabled individual_extraction configurations of the implementation a
 * source is extracted with, from the same query the paste-text review page
 * reads. None until an implementation is chosen.
 */
export function useExtractionConfigurations(implementationId: string) {
  const { data, isLoading } = usePipelineConfigurations(INDIVIDUAL_EXTRACTION, implementationId);
  return {
    configurations: (data ?? []).filter((c) => c.enabled !== false),
    isLoading,
  };
}
