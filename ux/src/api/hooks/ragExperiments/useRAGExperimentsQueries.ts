/**
 * RAG Experiments Queries
 *
 * TanStack Query queries for RAG experiment data fetching
 */

import { useQuery } from "@tanstack/react-query";
import { ragExperimentsService } from "@/api/services/ragExperiments";
import { QUERY_KEYS, API_CONFIG } from "@/api/config";
import type {
  ListParagraphsParams,
  GetComparisonParams,
} from "@/api/services/ragExperiments";

/**
 * List test paragraphs with pagination
 */
export function useTestParagraphs(params: ListParagraphsParams = {}) {
  return useQuery({
    queryKey: [QUERY_KEYS.RAG_EXPERIMENTS, "paragraphs", params],
    queryFn: () => ragExperimentsService.listTestParagraphs(params),
    staleTime: API_CONFIG.staleTime,
  });
}

/**
 * Get a specific test paragraph by ID
 */
export function useTestParagraph(paragraphId: string | undefined) {
  return useQuery({
    queryKey: [QUERY_KEYS.RAG_EXPERIMENTS, "paragraph", paragraphId],
    queryFn: () => {
      if (!paragraphId) {
        throw new Error("Paragraph ID is required");
      }
      return ragExperimentsService.getTestParagraph(paragraphId);
    },
    enabled: !!paragraphId,
    staleTime: API_CONFIG.staleTime,
  });
}

/**
 * Get pipeline comparison results for a test paragraph
 */
export function usePipelineComparison(params: GetComparisonParams | undefined) {
  return useQuery({
    queryKey: [
      QUERY_KEYS.RAG_EXPERIMENTS,
      "comparison",
      params?.paragraphId,
      params?.pipelineNames,
    ],
    queryFn: () => {
      if (!params?.paragraphId) {
        throw new Error("Paragraph ID is required for comparison");
      }
      return ragExperimentsService.getPipelineComparison(params);
    },
    enabled: !!params?.paragraphId,
    staleTime: API_CONFIG.staleTime,
  });
}

/**
 * Get detailed results for a specific pipeline run
 */
export function usePipelineRunDetails(runId: string | undefined) {
  return useQuery({
    queryKey: [QUERY_KEYS.RAG_EXPERIMENTS, "runDetails", runId],
    queryFn: () => {
      if (!runId) {
        throw new Error("Run ID is required");
      }
      return ragExperimentsService.getPipelineRunDetails(runId);
    },
    enabled: !!runId,
    staleTime: API_CONFIG.staleTime,
  });
}
