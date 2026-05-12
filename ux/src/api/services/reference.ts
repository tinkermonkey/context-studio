import { BaseService } from "./base";
import type { components } from "@/api/types";

type ReferenceSearchRequest = components["schemas"]["ReferenceSearchRequest"];
type ReferenceSearchResponseSchema = components["schemas"]["ReferenceSearchResponseSchema"];
type ReferenceStatusResponseSchema = components["schemas"]["ReferenceStatusResponseSchema"];

export interface GroundingWorkflowResponse {
  id: string;
  title: string;
  description?: string;
  source: string;
  class_scope: string[];
  status: "active" | "inactive" | "error";
  last_run?: string;
  last_run_record_count?: number;
}

export interface GroundingWorkflowCreate {
  title: string;
  source: string;
  class_scope: string[];
}

export interface GroundingWorkflowUpdate {
  title?: string;
  source?: string;
  class_scope?: string[];
  status?: "active" | "inactive" | "error";
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  status: "success" | "failed" | "running";
  record_count: number;
  timestamp: string;
  error_message?: string;
}

class ReferenceService extends BaseService {
  async search(
    term: string,
    options?: { limit?: number; sources?: string[] },
  ): Promise<ReferenceSearchResponseSchema> {
    const body: ReferenceSearchRequest = {
      term,
      limit: options?.limit ?? 10,
      sources: options?.sources,
    };
    return this.post<ReferenceSearchResponseSchema>("/api/reference/search", body);
  }

  async getStatus(): Promise<ReferenceStatusResponseSchema> {
    return this.get<ReferenceStatusResponseSchema>("/api/reference/status");
  }

  async listGroundingWorkflows(): Promise<GroundingWorkflowResponse[]> {
    return this.get<GroundingWorkflowResponse[]>("/api/reference/grounding-workflows");
  }

  async getGroundingWorkflow(id: string): Promise<GroundingWorkflowResponse> {
    return this.get<GroundingWorkflowResponse>(`/api/reference/grounding-workflows/${id}`);
  }

  async createGroundingWorkflow(data: GroundingWorkflowCreate): Promise<GroundingWorkflowResponse> {
    return this.post<GroundingWorkflowResponse>("/api/reference/grounding-workflows", data);
  }

  async updateGroundingWorkflow(
    id: string,
    data: GroundingWorkflowUpdate,
  ): Promise<GroundingWorkflowResponse> {
    return this.put<GroundingWorkflowResponse>(`/api/reference/grounding-workflows/${id}`, data);
  }

  async deleteGroundingWorkflow(id: string): Promise<void> {
    return this.delete<void>(`/api/reference/grounding-workflows/${id}`);
  }

  async runGroundingWorkflow(id: string): Promise<WorkflowRun> {
    return this.post<WorkflowRun>(`/api/reference/grounding-workflows/${id}/run`, {});
  }

  async getGroundingWorkflowRuns(workflowId: string): Promise<WorkflowRun[]> {
    return this.get<WorkflowRun[]>(`/api/reference/grounding-workflows/${workflowId}/runs`);
  }
}

export const referenceService = new ReferenceService();
