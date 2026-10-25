import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import {
  pipelineService,
  type RecognitionPreviewRequest,
  type RecognitionPreviewResponse,
  type SchemaExtractionCandidate,
  type TripleCandidate,
} from "@/api/services/pipeline";

export type {
  NodeReference,
  PredicateReference,
  RecognitionPreviewHit,
  RecognitionPreviewResponse,
  SchemaExtractionCandidate,
  SchemaRecognitionHit,
  SourceSpan,
  TripleCandidate,
} from "@/api/services/pipeline";

export function useSchemaExtractionCandidates(runId: string, enabled?: boolean) {
  return useQuery<SchemaExtractionCandidate[]>({
    queryKey: QUERY_KEYS.pipelineSchemaExtractionCandidates(runId),
    queryFn: () => pipelineService.getSchemaExtractionCandidates(runId),
    enabled: !!runId && enabled !== false,
  });
}

export function useIndividualExtractionCandidates(runId: string, enabled?: boolean) {
  return useQuery<TripleCandidate[]>({
    queryKey: QUERY_KEYS.pipelineIndividualExtractionCandidates(runId),
    queryFn: () => pipelineService.getIndividualExtractionCandidates(runId),
    enabled: !!runId && enabled !== false,
  });
}

/**
 * Recognition preview is a zero-write POST, so it is modelled as a query keyed
 * on the run and request (thresholds; concept_scheme_id for schema runs); it
 * recomputes against the current graph on refetch.
 */
export function useRecognitionPreview(
  runId: string,
  thresholds: Partial<RecognitionPreviewRequest>,
  enabled?: boolean,
) {
  return useQuery<RecognitionPreviewResponse>({
    queryKey: QUERY_KEYS.pipelineRecognitionPreview(runId, thresholds),
    queryFn: () => pipelineService.previewRecognition(runId, thresholds),
    enabled: !!runId && enabled !== false,
  });
}
