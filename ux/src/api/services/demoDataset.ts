import { BaseService } from "./base";
import type { components } from "@/api/types";

type DemoDatasetDescriptorResponse = components["schemas"]["DemoDatasetDescriptorResponse"];
type DemoDatasetLoadResponse = components["schemas"]["DemoDatasetLoadResponse"];

class DemoDatasetService extends BaseService {
  async list(): Promise<DemoDatasetDescriptorResponse[]> {
    return this.get<DemoDatasetDescriptorResponse[]>("/api/v1/admin/demo-datasets");
  }

  async load(name: string): Promise<DemoDatasetLoadResponse> {
    return this.post<DemoDatasetLoadResponse>(`/api/v1/admin/demo-datasets/${name}/load`);
  }
}

export const demoDatasetService = new DemoDatasetService();
