import { BaseService } from "./base";
import type { components } from "@/api/types";

type PipelineTypeResponse = components["schemas"]["PipelineTypeResponse"];
type ImplementationResponse = components["schemas"]["ImplementationResponse"];
type ConfigurationResponse = components["schemas"]["ConfigurationResponse"];
type PipelineRunRequest = components["schemas"]["PipelineRunRequest"];
type PipelineRunResponse = components["schemas"]["PipelineRunResponse"];
type ListPipelineRuns = components["schemas"]["ListResponse_PipelineRunResponse_"];
type CandidateResponse = components["schemas"]["CandidateResponse"];
type ApplyRunResponse = components["schemas"]["ApplyRunResponse"];
type RevertRunResponse = components["schemas"]["RevertRunResponse"];
type BatchResponse = components["schemas"]["BatchResponse"];
type CancelBatchResponse = components["schemas"]["CancelBatchResponse"];
type ResumeBatchResponse = components["schemas"]["ResumeBatchResponse"];
type ListChangeEvents = components["schemas"]["ListResponse_VersioningChangeEventResponse_"];

export interface RunListParams {
  limit?: number;
  offset?: number;
  pipeline_type?: string;
  implementation_id?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
}

export interface ApplyParams {
  confidence_threshold: number;
  concept_scheme_id?: string;
  taxonomy_id?: string;
  node_id?: string;
}

class PipelineService extends BaseService {
  // Discovery
  async listTypes(): Promise<PipelineTypeResponse[]> {
    return this.get<PipelineTypeResponse[]>("/api/pipelines/types");
  }

  async listImplementations(type: string): Promise<ImplementationResponse[]> {
    return this.get<ImplementationResponse[]>(`/api/pipelines/types/${type}/implementations`);
  }

  async listConfigurations(type: string, implId: string): Promise<ConfigurationResponse[]> {
    return this.get<ConfigurationResponse[]>(
      `/api/pipelines/types/${type}/implementations/${implId}/configurations`,
    );
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

  async getCandidates(runId: string): Promise<CandidateResponse[]> {
    return this.get<CandidateResponse[]>(`/api/pipelines/runs/${runId}/candidates`);
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
  async applyRun(runId: string, params: ApplyParams): Promise<ApplyRunResponse> {
    return this.post<ApplyRunResponse>(
      `/api/pipelines/runs/${runId}/apply`,
      undefined,
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
