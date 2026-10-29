import { BaseService } from "./base";

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
}

export const interchangeService = new InterchangeService();
