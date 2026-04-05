/**
 * RAG Mutation Hooks
 *
 * React Query mutation hooks for RAG pipeline operations
 */

import { useMutation, UseMutationOptions } from "@tanstack/react-query";
import { ragService, type RAGConfigUpdate } from "@/api/services/rag";

// Response types for RAG operations
// These operations are not yet in the OpenAPI spec, so we use generic types
type ExtractEntitiesResponse = Record<string, unknown>;
type UpdateConfigResponse = Record<string, unknown>;
type DeleteTraceResponse = Record<string, unknown>;

export interface ExtractEntitiesParams {
  text: string;
  enableTrace?: boolean;
  enableLlmLayer?: boolean;
}

/**
 * Hook to extract entities from text using the RAG pipeline
 */
export const useExtractEntities = (
  options?: UseMutationOptions<
    ExtractEntitiesResponse,
    Error,
    ExtractEntitiesParams
  >,
) => {
  return useMutation({
    mutationFn: ({
      text,
      enableTrace = false,
      enableLlmLayer,
    }: ExtractEntitiesParams) =>
      ragService.extractEntities(text, enableTrace, enableLlmLayer),
    ...options,
  });
};

/**
 * Hook to update RAG pipeline configuration
 */
export const useUpdateRAGConfig = (
  options?: UseMutationOptions<UpdateConfigResponse, Error, RAGConfigUpdate>,
) => {
  return useMutation({
    mutationFn: (config: RAGConfigUpdate) => ragService.updateConfig(config),
    ...options,
  });
};

/**
 * Hook to delete trace data for a specific request
 */
export const useDeleteTrace = (
  options?: UseMutationOptions<DeleteTraceResponse, Error, string>,
) => {
  return useMutation({
    mutationFn: (requestId: string) => ragService.deleteTrace(requestId),
    ...options,
  });
};
