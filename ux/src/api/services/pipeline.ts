import { BaseService } from "./base";
import type { components } from "@/api/types";

type PipelineTypeResponse = components["schemas"]["PipelineTypeResponse"];
type ImplementationResponse = components["schemas"]["ImplementationResponse"];
type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type PipelineConfigurationCreateRequest =
  components["schemas"]["PipelineConfigurationCreateRequest"];
type PipelineConfigurationUpdateRequest =
  components["schemas"]["PipelineConfigurationUpdateRequest"];
type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];
type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];
type ListPipelineRuns = components["schemas"]["ListResponse_PipelineRunResponse_"];
export type ApplyRunResponse = components["schemas"]["ApplyRunResponse"];
/** Why apply skipped a candidate (values of ApplyRunResponse.skip_reasons). */
export type SkipReason = NonNullable<ApplyRunResponse["skip_reasons"]>[string];
export type ApplyRunRequest = components["schemas"]["ApplyRunRequest"];
export type RecognitionDecision = components["schemas"]["RecognitionDecisionSchema"];
export type MergedMention = components["schemas"]["MergedMentionSchema"];
type RevertRunResponse = components["schemas"]["RevertRunResponse"];
type BatchResponse = components["schemas"]["BatchResponse"];
type CancelBatchResponse = components["schemas"]["CancelBatchResponse"];
type ResumeBatchResponse = components["schemas"]["ResumeBatchResponse"];
type ListChangeEvents = components["schemas"]["ListResponse_VersioningChangeEventResponse_"];
export type SourceSpan = components["schemas"]["SourceSpanSchema"];
export type NodeReference = components["schemas"]["NodeReference"];
export type PredicateReference = components["schemas"]["PredicateReference"];
export type TripleCandidate = components["schemas"]["TripleCandidate"];
export type SchemaClassCandidate = components["schemas"]["SchemaClassCandidate"];
export type SchemaPropertyCandidate = components["schemas"]["SchemaPropertyCandidate"];
export type SchemaConnectionCandidate = components["schemas"]["SchemaConnectionCandidate"];
export type SchemaExtractionCandidate =
  | SchemaClassCandidate
  | SchemaPropertyCandidate
  | SchemaConnectionCandidate;
export type RecognitionPreviewRequest = components["schemas"]["RecognitionPreviewRequest"];
export type RecognitionPreviewResponse = components["schemas"]["RecognitionPreviewResponse"];
export type RecognitionPreviewHit = components["schemas"]["RecognitionPreviewHitSchema"];
/** Discriminated union returned by every /runs/{id}/*candidates endpoint. */
export type CandidateItem =
  | SchemaExtractionCandidate
  | TripleCandidate
  | components["schemas"]["GroundingCandidate"]
  | components["schemas"]["RefinementCandidate"];

const SCHEMA_CANDIDATE_TYPES = new Set(["schema_class", "schema_property", "schema_connection"]);

export interface RunListParams {
  limit?: number;
  offset?: number;
  pipeline_type?: string;
  implementation_id?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
  applied?: "applied" | "not-applied";
}

export interface ApplyParams {
  /** Ignored by the server when the body carries accepted_candidate_ids. */
  confidence_threshold?: number;
  concept_scheme_id?: string;
  taxonomy_id?: string;
  node_id?: string;
  recognition_threshold?: number;
}

class PipelineService extends BaseService {
  // Discovery
  async listTypes(): Promise<PipelineTypeResponse[]> {
    return this.get<PipelineTypeResponse[]>("/api/pipelines/types");
  }

  async listImplementations(type: string): Promise<ImplementationResponse[]> {
    return this.get<ImplementationResponse[]>(`/api/pipelines/types/${type}/implementations`);
  }

  async listConfigurations(type: string, implId: string): Promise<PipelineConfigurationResponse[]> {
    return this.get<PipelineConfigurationResponse[]>(
      `/api/pipelines/types/${type}/implementations/${implId}/configurations`,
    );
  }

  // Configuration CRUD
  async createConfiguration(
    type: string,
    implId: string,
    body: PipelineConfigurationCreateRequest,
  ): Promise<PipelineConfigurationResponse> {
    return this.post<PipelineConfigurationResponse>(
      `/api/pipelines/types/${type}/implementations/${implId}/configurations`,
      body,
    );
  }

  async getConfiguration(configId: string): Promise<PipelineConfigurationResponse> {
    return this.get<PipelineConfigurationResponse>(`/api/pipeline_configurations/${configId}`);
  }

  async updateConfiguration(
    configId: string,
    body: PipelineConfigurationUpdateRequest,
  ): Promise<PipelineConfigurationResponse> {
    return this.put<PipelineConfigurationResponse>(
      `/api/pipeline_configurations/${configId}`,
      body,
    );
  }

  async deleteConfiguration(configId: string): Promise<void> {
    return this.delete<void>(`/api/pipeline_configurations/${configId}`);
  }

  // Execution
  async runPipeline(type: string, request: PipelineRunRequest): Promise<PipelineRunResponse> {
    return this.post<PipelineRunResponse>(`/api/pipelines/${type}/run`, request, undefined, {
      timeout: 120_000,
    });
  }

  // Runs
  async getRun(runId: string): Promise<PipelineRunResponse> {
    return this.get<PipelineRunResponse>(`/api/pipelines/runs/${runId}`);
  }

  async listRuns(params?: RunListParams): Promise<ListPipelineRuns> {
    return this.get<ListPipelineRuns>(
      "/api/pipelines/runs",
      params as unknown as Record<string, unknown>,
    );
  }

  async getCandidates(runId: string): Promise<CandidateItem[]> {
    return this.get<CandidateItem[]>(`/api/pipelines/runs/${runId}/candidates`);
  }

  /** Typed schema_extraction candidates (classes, properties, connections) with provenance. */
  async getSchemaExtractionCandidates(runId: string): Promise<SchemaExtractionCandidate[]> {
    const items = await this.get<CandidateItem[]>(
      `/api/pipelines/runs/${runId}/schema-extraction-candidates`,
    );
    return items.filter((c): c is SchemaExtractionCandidate =>
      SCHEMA_CANDIDATE_TYPES.has(c.candidate_type),
    );
  }

  /** Typed individual_extraction triple candidates with provenance. */
  async getIndividualExtractionCandidates(runId: string): Promise<TripleCandidate[]> {
    const items = await this.get<CandidateItem[]>(
      `/api/pipelines/runs/${runId}/individual-extraction-candidates`,
    );
    return items.filter((c): c is TripleCandidate => c.candidate_type === "triple");
  }

  /** Zero-write preview of which mentions would resolve to existing individuals on apply. */
  async previewRecognition(
    runId: string,
    body: RecognitionPreviewRequest,
  ): Promise<RecognitionPreviewResponse> {
    return this.post<RecognitionPreviewResponse>(
      `/api/pipelines/runs/${runId}/recognition-preview`,
      body,
    );
  }

  async getRunChangeEvents(
    runId: string,
    offset: number = 0,
    limit: number = 100,
  ): Promise<ListChangeEvents> {
    return this.get<ListChangeEvents>(`/api/pipelines/runs/${runId}/change-events`, {
      offset,
      limit,
    });
  }

  // Materialization
  /**
   * Apply a run. Query params carry scope/thresholds; the optional body carries
   * explicit selections (accepted candidate ids, per-mention recognition decisions).
   */
  async applyRun(
    runId: string,
    params: ApplyParams,
    body?: ApplyRunRequest,
  ): Promise<ApplyRunResponse> {
    return this.post<ApplyRunResponse>(
      `/api/pipelines/runs/${runId}/apply`,
      body,
      params as unknown as Record<string, unknown>,
    );
  }

  async revertRun(runId: string): Promise<RevertRunResponse> {
    return this.post<RevertRunResponse>(`/api/pipelines/runs/${runId}/revert`, undefined);
  }

  // Batch (scaffolded, deferred)
  async createBatch(data: unknown): Promise<BatchResponse> {
    return this.post<BatchResponse>("/api/pipelines/batches", data);
  }

  async getBatch(batchId: string): Promise<BatchResponse> {
    return this.get<BatchResponse>(`/api/pipelines/batches/${batchId}`);
  }

  async enqueueBatchRuns(batchId: string, data: unknown): Promise<BatchResponse> {
    return this.post<BatchResponse>(`/api/pipelines/batches/${batchId}/runs`, data);
  }

  async cancelBatch(batchId: string): Promise<CancelBatchResponse> {
    return this.post<CancelBatchResponse>(`/api/pipelines/batches/${batchId}/cancel`, undefined);
  }

  async resumeBatch(batchId: string): Promise<ResumeBatchResponse> {
    return this.post<ResumeBatchResponse>(`/api/pipelines/batches/${batchId}/resume`, undefined);
  }
}

export const pipelineService = new PipelineService();
