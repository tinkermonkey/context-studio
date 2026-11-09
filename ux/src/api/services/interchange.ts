import { BaseService } from "./base";
import type { components } from "@/api/types";

export type DrSpecDriftRequest = components["schemas"]["DrSpecDriftRequest"];
export type DriftResponse = components["schemas"]["DriftResponse"];
export type DriftEntry = components["schemas"]["DriftEntryResponse"];

/**
 * A Context Studio bundle (v0): one taxonomy as JSON. The API returns it as a
 * plain object; only the fields the UI reads are typed.
 */
export type Bundle = {
  format: string;
  version: number;
  source: string;
  taxonomy: { identifier: string; title: string };
} & Record<string, unknown>;

class InterchangeService extends BaseService {
  async exportBundle(taxonomyId: string): Promise<Bundle> {
    return this.get<Bundle>(`/api/v1/interchange/bundles/${taxonomyId}`);
  }

  /** Report (dry run) or propose the drift between the DR spec on disk and its taxonomy. */
  async drSpecDrift(request: DrSpecDriftRequest): Promise<DriftResponse> {
    return this.post<DriftResponse>("/api/v1/interchange/dr-spec/drift", request);
  }
}

export const interchangeService = new InterchangeService();
