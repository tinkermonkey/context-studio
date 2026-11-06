import { BaseService } from "./base";
import type { components } from "@/api/types";

export type ChangeProposal = components["schemas"]["ChangeProposalResponse"];
export type ProposedOperation = components["schemas"]["ProposedOperationResponse"];
export type ChangeProposalCreateRequest = components["schemas"]["ChangeProposalCreateRequest"];
export type ChangeProposalApplyRequest = components["schemas"]["ChangeProposalApplyRequest"];
export type ChangeProposalRejectRequest = components["schemas"]["ChangeProposalRejectRequest"];
export type ChangeProposalRevertResponse = components["schemas"]["ChangeProposalRevertResponse"];
export type ChangeProposalRevertConflict =
  components["schemas"]["ChangeProposalRevertConflictDetail"];
export type RevertBlocker = components["schemas"]["RevertBlocker"];
/** One operation's decision in DR's decisions file (`proposal-import.ts --decisions`). */
export type DrDecision = components["schemas"]["DrDecisionResponse"];
export type ApprovalPolicy = components["schemas"]["ApprovalPolicyResponse"];
export type ApprovalPolicyRequest = components["schemas"]["ApprovalPolicyRequest"];
/** A standing reviewer or policy decision on one operation, with who decided it and when. */
export type GoldDecision = components["schemas"]["GoldDecisionResponse"];
type GoldDecisionList = components["schemas"]["ListResponse_GoldDecisionResponse_"];
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

  /** DR's decisions file for a reflection-plan proposal; 409 once it is reverted. */
  async getDecisions(id: string): Promise<DrDecision[]> {
    return this.get<DrDecision[]>(`/api/proposals/${id}/decisions`);
  }

  /**
   * Every standing decision (gold) on one proposal's operations, with who
   * decided and when; pages through the taxonomy's gold filtered by proposal.
   */
  async listProposalGold(taxonomyId: string, proposalId: string): Promise<GoldDecision[]> {
    const limit = 500;
    const decisions: GoldDecision[] = [];
    for (let offset = 0; ; offset += limit) {
      const page = await this.get<GoldDecisionList>(`/api/taxonomies/${taxonomyId}/gold`, {
        proposal_id: proposalId,
        limit,
        offset,
      });
      decisions.push(...page.items);
      if (page.items.length < limit || decisions.length >= page.total) return decisions;
    }
  }

  async getApprovalPolicy(taxonomyId: string): Promise<ApprovalPolicy> {
    return this.get<ApprovalPolicy>(`/api/taxonomies/${taxonomyId}/approval-policy`);
  }

  async setApprovalPolicy(
    taxonomyId: string,
    data: ApprovalPolicyRequest,
  ): Promise<ApprovalPolicy> {
    return this.put<ApprovalPolicy>(`/api/taxonomies/${taxonomyId}/approval-policy`, data);
  }
}

export const proposalsService = new ProposalsService();
