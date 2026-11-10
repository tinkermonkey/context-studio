import { BaseService } from "./base";
import type { components } from "@/api/types";

/** An atomic statement split from a reviewer's or maintainer's note about a taxonomy. */
export type Claim = components["schemas"]["ClaimResponse"];
/** A decision model's answers about a claim. */
export type ClaimTriage = components["schemas"]["ClaimTriageSchema"];
/** A recorded verdict: benchmark gold. */
export type ClaimVerdict = components["schemas"]["ClaimVerdictSchema"];
export type ClaimVerdictRequest = components["schemas"]["ClaimVerdictRequest"];
export type Validity = components["schemas"]["Validity"];
type ClaimList = components["schemas"]["ListResponse_ClaimResponse_"];

/** The list and export routes' filters. */
export interface ClaimFilters {
  /** Only claims about this entity. */
  subject_id?: string;
  /** Only claims from this note. */
  note_ref?: string;
  /** Only triaged (true) or untriaged (false) claims. */
  triaged?: boolean;
  /** Only claims with (true) or without (false) a verdict. */
  has_verdict?: boolean;
  /** Only claims triaged as this. */
  validity?: Validity;
}

export interface ClaimListParams extends ClaimFilters {
  limit?: number;
  offset?: number;
}

class ClaimsService extends BaseService {
  /** A taxonomy's claims, oldest first. */
  async listClaims(taxonomyId: string, params?: ClaimListParams): Promise<ClaimList> {
    return this.get<ClaimList>(
      `/api/taxonomies/${taxonomyId}/claims`,
      params as unknown as Record<string, unknown>,
    );
  }

  /** Every matching claim as JSONL text, one ClaimResponse per line. */
  async exportClaims(taxonomyId: string, filters?: ClaimFilters): Promise<string> {
    return this.get<string>(
      `/api/taxonomies/${taxonomyId}/claims/export`,
      filters as unknown as Record<string, unknown>,
      { responseType: "text" },
    );
  }

  async getClaim(id: string): Promise<Claim> {
    return this.get<Claim>(`/api/claims/${id}`);
  }

  /** Record a person's verdict, replacing any earlier one. */
  async setVerdict(id: string, data: ClaimVerdictRequest): Promise<Claim> {
    return this.put<Claim>(`/api/claims/${id}/verdict`, data);
  }

  async clearVerdict(id: string): Promise<Claim> {
    return this.delete<Claim>(`/api/claims/${id}/verdict`);
  }
}

export const claimsService = new ClaimsService();
