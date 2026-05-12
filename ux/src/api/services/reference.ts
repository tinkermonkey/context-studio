import { BaseService } from "./base";
import type { components } from "@/api/types";
import type {
  GroundingWorkflowResponse,
  GroundingWorkflowCreate,
  GroundingWorkflowUpdate,
  WorkflowRun,
} from "@/api/types/grounding";

type ReferenceSearchRequest = components["schemas"]["ReferenceSearchRequest"];
type ReferenceSearchResponseSchema = components["schemas"]["ReferenceSearchResponseSchema"];
type ReferenceStatusResponseSchema = components["schemas"]["ReferenceStatusResponseSchema"];

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

// Re-export grounding workflow types for backward compatibility
// These types are defined in @/api/types/grounding and will be replaced with auto-generated types
// from the OpenAPI spec once the backend implements the endpoints
export type { GroundingWorkflowResponse, GroundingWorkflowCreate, GroundingWorkflowUpdate, WorkflowRun } from "@/api/types/grounding";
