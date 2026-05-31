import { BaseService } from "./base";

// TODO: These types are not yet in the OpenAPI spec (Phase 2 work)
type PipelineConfigurationResponse = any;
type PipelineConfigurationCreate = any;
type PipelineConfigurationUpdate = any;
type ExecutionResponse = any;
type PipelineExecuteRequest = any;

class PipelineService extends BaseService {
  async listPipelines(): Promise<PipelineConfigurationResponse[]> {
    return this.get<PipelineConfigurationResponse[]>("/api/pipelines");
  }

  async getPipeline(id: string): Promise<PipelineConfigurationResponse> {
    return this.get<PipelineConfigurationResponse>(`/api/pipelines/${id}`);
  }

  async createPipeline(data: PipelineConfigurationCreate): Promise<PipelineConfigurationResponse> {
    return this.post<PipelineConfigurationResponse>("/api/pipelines", data);
  }

  async updatePipeline(
    id: string,
    data: PipelineConfigurationUpdate,
  ): Promise<PipelineConfigurationResponse> {
    return this.put<PipelineConfigurationResponse>(`/api/pipelines/${id}`, data);
  }

  async deletePipeline(id: string): Promise<void> {
    return this.delete<void>(`/api/pipelines/${id}`);
  }

  async executePipeline(id: string, inputText: string): Promise<ExecutionResponse> {
    const body: PipelineExecuteRequest = { input_text: inputText };
    return this.post<ExecutionResponse>(`/api/pipelines/${id}/execute`, body);
  }

  async getPipelineExecutions(pipelineId: string): Promise<ExecutionResponse[]> {
    return this.get<ExecutionResponse[]>(`/api/pipelines/${pipelineId}/executions`);
  }

  async getAllPipelineExecutions(
    status?: string,
    limit?: number,
    offset?: number,
  ): Promise<any> {
    const params = new URLSearchParams();
    if (status) params.append("status_filter", status);
    if (limit != null) params.append("limit", limit.toString());
    if (offset != null) params.append("offset", offset.toString());

    const queryString = params.toString();
    const url = `/api/pipelines/executions${queryString ? `?${queryString}` : ""}`;
    return this.get<any>(url);
  }
}

export const pipelineService = new PipelineService();
