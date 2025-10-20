/**
 * RAG Mutation Hooks
 *
 * React Query mutation hooks for RAG pipeline operations
 */

import { useMutation, UseMutationOptions } from "@tanstack/react-query";
import {
  ragService,
  type RAGConfigUpdate,
} from "@/api/services/rag";
import { operations } from "@/api/client/types";

// Infer response types from operations
type ExtractEntitiesResponse = operations["extract_entities_api_rag_extract_post"]["responses"]["200"]["content"]["application/json"];
type UpdateConfigResponse = operations["update_config_api_rag_config_update_post"]["responses"]["200"]["content"]["application/json"];
type DeleteTraceResponse = operations["delete_trace_api_rag_trace__request_id__delete"]["responses"]["200"]["content"]["application/json"];

export interface ExtractEntitiesParams {
  text: string;
  enableTrace?: boolean;
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
    mutationFn: ({ text, enableTrace = false }: ExtractEntitiesParams) =>
      ragService.extractEntities(text, enableTrace),
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
