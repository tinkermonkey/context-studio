import { BaseService } from "./base";
import type { components } from "@/api/types";

type PipelineConfigurationResponse =
  components["schemas"]["PipelineConfigurationResponse"];
type PipelineConfigurationCreate =
  components["schemas"]["PipelineConfigurationCreate"];
type PipelineConfigurationUpdate =
  components["schemas"]["PipelineConfigurationUpdate"];
type ExecutionResponse = components["schemas"]["ExecutionResponse"];
type PipelineExecuteRequest = components["schemas"]["PipelineExecuteRequest"];

class PipelineService extends BaseService {
  async listPipelines(): Promise<PipelineConfigurationResponse[]> {
    return this.get<PipelineConfigurationResponse[]>("/api/pipelines");
  }

  async getPipeline(id: string): Promise<PipelineConfigurationResponse> {
    return this.get<PipelineConfigurationResponse>(`/api/pipelines/${id}`);
  }

  async createPipeline(
    data: PipelineConfigurationCreate
  ): Promise<PipelineConfigurationResponse> {
    return this.post<PipelineConfigurationResponse>("/api/pipelines", data);
  }

  async updatePipeline(
    id: string,
    data: PipelineConfigurationUpdate
  ): Promise<PipelineConfigurationResponse> {
    return this.put<PipelineConfigurationResponse>(
      `/api/pipelines/${id}`,
      data
    );
  }

  async deletePipeline(id: string): Promise<void> {
    return this.delete<void>(`/api/pipelines/${id}`);
  }

  async executePipeline(
    id: string,
    inputText: string
  ): Promise<ExecutionResponse> {
    const body: PipelineExecuteRequest = { input_text: inputText };
    return this.post<ExecutionResponse>(`/api/pipelines/${id}/execute`, body);
  }

  async getPipelineExecutions(pipelineId: string): Promise<ExecutionResponse[]> {
    return this.get<ExecutionResponse[]>(
      `/api/pipelines/${pipelineId}/executions`
    );
  }
}

export const pipelineService = new PipelineService();
