/**
 * RAG Experiments Mutations
 *
 * TanStack Query mutations for RAG experiment operations
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ragExperimentsService } from "@/api/services/ragExperiments";
import { QUERY_KEYS } from "@/api/config";
import type {
  CreateTestParagraphRequest,
  UpdateTestParagraphRequest,
  CreateAnnotationRequest,
  RunPipelineTestRequest,
} from "@/api/services/ragExperiments";

/**
 * Create a new test paragraph
 */
export function useCreateTestParagraph() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: { text: string; notes?: string }) =>
      ragExperimentsService.createTestParagraph(params.text, params.notes),
    onSuccess: () => {
      // Invalidate the paragraphs list to refetch
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.RAG_EXPERIMENTS, "paragraphs"],
      });
    },
  });
}

/**
 * Update an existing test paragraph
 */
export function useUpdateTestParagraph() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: {
      paragraphId: string;
      text?: string;
      notes?: string;
    }) =>
      ragExperimentsService.updateTestParagraph(
        params.paragraphId,
        params.text,
        params.notes,
      ),
    onSuccess: (data, variables) => {
      // Invalidate specific paragraph and list
      queryClient.invalidateQueries({
        queryKey: [
          QUERY_KEYS.RAG_EXPERIMENTS,
          "paragraph",
          variables.paragraphId,
        ],
      });
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.RAG_EXPERIMENTS, "paragraphs"],
      });
    },
  });
}

/**
 * Delete a test paragraph
 */
export function useDeleteTestParagraph() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (paragraphId: string) =>
      ragExperimentsService.deleteTestParagraph(paragraphId),
    onSuccess: (data, paragraphId) => {
      // Invalidate paragraph list and remove specific paragraph from cache
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.RAG_EXPERIMENTS, "paragraphs"],
      });
      queryClient.removeQueries({
        queryKey: [QUERY_KEYS.RAG_EXPERIMENTS, "paragraph", paragraphId],
      });
    },
  });
}

/**
 * Create an annotation for a test paragraph
 */
export function useCreateAnnotation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: {
      paragraphId: string;
      startChar: number;
      endChar: number;
      structureNodeId: string;
    }) =>
      ragExperimentsService.createAnnotation(
        params.paragraphId,
        params.startChar,
        params.endChar,
        params.structureNodeId,
      ),
    onSuccess: (data, variables) => {
      // Invalidate the specific paragraph to refetch with new annotation
      queryClient.invalidateQueries({
        queryKey: [
          QUERY_KEYS.RAG_EXPERIMENTS,
          "paragraph",
          variables.paragraphId,
        ],
      });
      // Also invalidate the list in case it shows annotation counts
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.RAG_EXPERIMENTS, "paragraphs"],
      });
    },
  });
}

/**
 * Delete an annotation
 */
export function useDeleteAnnotation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: { annotationId: string; paragraphId: string }) =>
      ragExperimentsService.deleteAnnotation(params.annotationId),
    onSuccess: (data, variables) => {
      // Invalidate the paragraph to refetch without the annotation
      queryClient.invalidateQueries({
        queryKey: [
          QUERY_KEYS.RAG_EXPERIMENTS,
          "paragraph",
          variables.paragraphId,
        ],
      });
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.RAG_EXPERIMENTS, "paragraphs"],
      });
    },
  });
}

/**
 * Run pipeline tests
 */
export function useRunPipelineTest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: {
      paragraphIds: string[];
      pipelineNames: string[];
      enableTrace?: boolean;
      enableLlmLayer?: boolean;
    }) =>
      ragExperimentsService.runPipelineTest(
        params.paragraphIds,
        params.pipelineNames,
        params.enableTrace ?? false,
        params.enableLlmLayer,
      ),
    onSuccess: (data, variables) => {
      // Invalidate comparison results for all tested paragraphs
      variables.paragraphIds.forEach((paragraphId) => {
        queryClient.invalidateQueries({
          queryKey: [QUERY_KEYS.RAG_EXPERIMENTS, "comparison", paragraphId],
        });
      });
    },
  });
}
