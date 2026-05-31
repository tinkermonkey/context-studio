import { BaseService } from "./base";
import type { components } from "@/api/types";

// TODO: These types are not yet in the OpenAPI spec (Phase 2 work)
type PipelineFlavorResponse = any; // components["schemas"]["PipelineFlavorResponse"];
type PipelineFlavorCreateRequest = any; // components["schemas"]["PipelineFlavorCreateRequest"];
type PipelineFlavorUpdateRequest = any; // components["schemas"]["PipelineFlavorUpdateRequest"];

class FlavorService extends BaseService {
  async listFlavors(): Promise<PipelineFlavorResponse[]> {
    return this.get<PipelineFlavorResponse[]>("/api/pipelines/flavors");
  }

  async getFlavor(id: string): Promise<PipelineFlavorResponse> {
    return this.get<PipelineFlavorResponse>(`/api/pipelines/flavors/${id}`);
  }

  async createFlavor(data: PipelineFlavorCreateRequest): Promise<PipelineFlavorResponse> {
    return this.post<PipelineFlavorResponse>("/api/pipelines/flavors", data);
  }

  async updateFlavor(
    id: string,
    data: PipelineFlavorUpdateRequest,
  ): Promise<PipelineFlavorResponse> {
    return this.put<PipelineFlavorResponse>(`/api/pipelines/flavors/${id}`, data);
  }

  async deleteFlavor(id: string): Promise<void> {
    return this.delete<void>(`/api/pipelines/flavors/${id}`);
  }
}

export const flavorService = new FlavorService();
