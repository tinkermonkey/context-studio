import { BaseService } from "./base";
import type { components } from "@/api/types";

export type ChangeProposal = components["schemas"]["ChangeProposalResponse"];
export type ProposedOperation = components["schemas"]["ProposedOperationResponse"];
export type ChangeProposalCreateRequest = components["schemas"]["ChangeProposalCreateRequest"];
export type ChangeProposalApplyRequest = components["schemas"]["ChangeProposalApplyRequest"];
export type ChangeProposalRejectRequest = components["schemas"]["ChangeProposalRejectRequest"];
export type ChangeProposalRevertResponse = components["schemas"]["ChangeProposalRevertResponse"];
type ChangeProposalList = components["schemas"]["ListResponse_ChangeProposalResponse_"];

export interface ChangeProposalListParams {
  taxonomy_id?: string;
  status?: ChangeProposal["status"];
  source?: ChangeProposal["source"];
  limit?: number;
  offset?: number;
}

class ProposalsService extends BaseService {
  async listProposals(params?: ChangeProposalListParams): Promise<ChangeProposalList> {
    return this.get<ChangeProposalList>(
      "/api/proposals",
      params as unknown as Record<string, unknown>,
    );
  }

  async getProposal(id: string): Promise<ChangeProposal> {
    return this.get<ChangeProposal>(`/api/proposals/${id}`);
  }

  async createProposal(data: ChangeProposalCreateRequest): Promise<ChangeProposal> {
    return this.post<ChangeProposal>("/api/proposals", data);
  }

  async applyProposal(id: string, data: ChangeProposalApplyRequest): Promise<ChangeProposal> {
    return this.post<ChangeProposal>(`/api/proposals/${id}/apply`, data);
  }

  async rejectProposal(id: string, data: ChangeProposalRejectRequest): Promise<ChangeProposal> {
    return this.post<ChangeProposal>(`/api/proposals/${id}/reject`, data);
  }

  async revertProposal(id: string): Promise<ChangeProposalRevertResponse> {
    return this.post<ChangeProposalRevertResponse>(`/api/proposals/${id}/revert`);
  }
}

export const proposalsService = new ProposalsService();
