import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService, type ExtractionExample } from "@/api/services/pipeline";

export type { ExtractionExample };

/** The example paragraph library; it ships with the app, so it never goes stale. */
export function useExtractionExamples() {
  return useQuery<ExtractionExample[]>({
    queryKey: QUERY_KEYS.extractionExamples(),
    queryFn: () => pipelineService.listExtractionExamples(),
    staleTime: Infinity,
  });
}
