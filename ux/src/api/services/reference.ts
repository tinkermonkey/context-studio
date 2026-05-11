import { BaseService } from "./base";
import type { components } from "@/api/types";

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
}

export const referenceService = new ReferenceService();
