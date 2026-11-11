import { useMutation, useQueryClient } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { sourcesService, type ExtractSourceRequest } from "@/api/services/sources";
import { usePipelineConfigurations } from "@/api/hooks/pipeline/usePipelineConfigurations";

const INDIVIDUAL_EXTRACTION = "individual_extraction";
/**
 * The only implementation that extracts a source chunk by chunk; the server
 * refuses (422) a configuration of any other, e.g. open_v1.
 */
export const SOURCE_EXTRACTION_IMPLEMENTATION = "default";

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
 * The enabled individual_extraction configurations source extraction can use:
 * the `default` implementation's, from the same query the paste-text review
 * page reads.
 */
export function useExtractionConfigurations() {
  const { data, isLoading } = usePipelineConfigurations(
    INDIVIDUAL_EXTRACTION,
    SOURCE_EXTRACTION_IMPLEMENTATION,
  );
  return {
    configurations: (data ?? []).filter((c) => c.enabled !== false),
    isLoading,
  };
}
