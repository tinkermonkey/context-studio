import { BaseService } from "./base";
import type { components } from "@/api/types";

type PipelineConfigurationResponse = components["schemas"]["PipelineConfigurationResponse"];
type PipelineConfigurationCreate = components["schemas"]["PipelineConfigurationCreate"];
type PipelineConfigurationUpdate = components["schemas"]["PipelineConfigurationUpdate"];
type ExecutionResponse = components["schemas"]["ExecutionResponse"];
type PipelineExecuteRequest = components["schemas"]["PipelineExecuteRequest"];

export interface PipelineFlavorResponse {
  id: string;
  name: string;
  description?: string;
  steps: Array<Record<string, unknown>>;
  step_count: number;
  created_at: string;
  last_updated: string;
}

export interface PipelineFlavorCreate {
  name: string;
  description?: string;
  steps: Array<Record<string, unknown>>;
}

export interface PipelineFlavorUpdate {
  name?: string;
  description?: string;
  steps?: Array<Record<string, unknown>>;
}

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
  ): Promise<components["schemas"]["ListResponse_ExecutionWithPipelineResponse_"]> {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (limit) params.append("limit", limit.toString());
    if (offset) params.append("offset", offset.toString());

    const queryString = params.toString();
    const url = `/api/pipelines/executions${queryString ? `?${queryString}` : ""}`;
    return this.get<components["schemas"]["ListResponse_ExecutionWithPipelineResponse_"]>(url);
  }

  async listFlavors(): Promise<PipelineFlavorResponse[]> {
    return this.get<PipelineFlavorResponse[]>("/api/pipelines/flavors");
  }

  async getFlavor(id: string): Promise<PipelineFlavorResponse> {
    return this.get<PipelineFlavorResponse>(`/api/pipelines/flavors/${id}`);
  }

  async createFlavor(data: PipelineFlavorCreate): Promise<PipelineFlavorResponse> {
    return this.post<PipelineFlavorResponse>("/api/pipelines/flavors", data);
  }

  async updateFlavor(id: string, data: PipelineFlavorUpdate): Promise<PipelineFlavorResponse> {
    return this.put<PipelineFlavorResponse>(`/api/pipelines/flavors/${id}`, data);
  }

  async deleteFlavor(id: string): Promise<void> {
    return this.delete<void>(`/api/pipelines/flavors/${id}`);
  }

  async createPipelineFromFlavor(
    flavorId: string,
    title: string,
  ): Promise<PipelineConfigurationResponse> {
    return this.post<PipelineConfigurationResponse>(
      `/api/pipelines/flavors/${flavorId}/create-pipeline`,
      { title },
    );
  }
}

export const pipelineService = new PipelineService();
