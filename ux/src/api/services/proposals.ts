import { BaseService } from "./base";
import type { components } from "@/api/types";

export type ChangeProposal = components["schemas"]["ChangeProposalResponse"];
export type ProposedOperation = components["schemas"]["ProposedOperationResponse"];
export type ChangeProposalCreateRequest = components["schemas"]["ChangeProposalCreateRequest"];
export type ChangeProposalApplyRequest = components["schemas"]["ChangeProposalApplyRequest"];
export type ChangeProposalRejectRequest = components["schemas"]["ChangeProposalRejectRequest"];
/** Decided operations to reopen, to decide again. */
export type ChangeProposalReopenRequest = components["schemas"]["ChangeProposalReopenRequest"];
/** An individual the extraction missed, as the reviewer found it in the proposal's source. */
export type AddIndividualRequest = components["schemas"]["AddIndividualRequest"];
/** What a reviewer notes for benchmark gold on a decision: the tier, and also defensible classes. */
export type ReviewAnnotation = components["schemas"]["ReviewAnnotationRequest"];
/** Why a reviewer rejected an operation, as a code (sent with a reject, kept on the operation). */
export type RejectionReason = components["schemas"]["RejectionReason"];
export type ChangeProposalRevertResponse = components["schemas"]["ChangeProposalRevertResponse"];
export type ChangeProposalRevertConflict =
  components["schemas"]["ChangeProposalRevertConflictDetail"];
export type RevertBlocker = components["schemas"]["RevertBlocker"];
export type RevertPreview = components["schemas"]["RevertPreviewResponse"];
export type RevertPreviewItem = components["schemas"]["RevertPreviewItem"];
/** One operation's decision in DR's decisions file (`proposal-import.ts --decisions`). */
export type DrDecision = components["schemas"]["DrDecisionResponse"];
export type ApprovalPolicy = components["schemas"]["ApprovalPolicyResponse"];
export type ApprovalPolicyRequest = components["schemas"]["ApprovalPolicyRequest"];
/** A standing reviewer or policy decision on one operation, with who decided it and when. */
export type GoldDecision = components["schemas"]["GoldDecisionResponse"];
type GoldDecisionList = components["schemas"]["ListResponse_GoldDecisionResponse_"];
type ChangeProposalList = components["schemas"]["ListResponse_ChangeProposalResponse_"];

/** Two pipelines' proposals for one source, their individual creates paired. */
export type ProposalComparison = components["schemas"]["ProposalComparisonResponse"];
export type ComparisonPair = components["schemas"]["PairResponse"];
export type ComparedOperation = components["schemas"]["ComparedOperationResponse"];
export type ComparedProposal = components["schemas"]["ComparedProposalResponse"];
export type ComparisonGroup = components["schemas"]["ComparisonGroup"];
export type PairState = components["schemas"]["PairState"];
export type PairVerdict = components["schemas"]["Verdict"];
export type PairDecisionRequest = components["schemas"]["PairDecisionRequest"];
export type PairDecisionResponse = components["schemas"]["PairDecisionResponse"];
export type AcceptRestResponse = components["schemas"]["AcceptRestResponse"];
export type ComparisonSample = components["schemas"]["SampleResponse"];

/** How many agreements a comparison asks to check before accepting the rest. */
export const DEFAULT_SAMPLE_SIZE = 10;

export interface ChangeProposalListParams {
  taxonomy_id?: string;
  status?: ChangeProposal["status"];
  source?: ChangeProposal["source"];
  /** Landed (true) or not yet landed (false) in a mirrored taxonomy's source. */
  landed?: boolean;
  /** Only proposals a run of this pipeline implementation made (their origin's), e.g. "gold_check". */
  implementation_id?: string;
  limit?: number;
  offset?: number;
}

export const APPLY_TIMEOUT_MS = 5 * 60 * 1000;

class ProposalsService extends BaseService {
  async listProposals(params?: ChangeProposalListParams): Promise<ChangeProposalList> {
    return this.get<ChangeProposalList>(
      "/api/proposals",
      params as unknown as Record<string, unknown>,
    );
  }

  /** Every proposal matching `params`, paging through the list by its total. */
  async listAllProposals(
    params: Omit<ChangeProposalListParams, "limit" | "offset"> = {},
  ): Promise<ChangeProposal[]> {
    const limit = 500;
    const proposals: ChangeProposal[] = [];
    for (let offset = 0; ; offset += limit) {
      const page = await this.listProposals({ ...params, limit, offset });
      proposals.push(...page.items);
      if (page.items.length < limit || proposals.length >= page.total) return proposals;
    }
  }

  /** Pair two individual extractions of one source (422 not_comparable otherwise). */
  async compareProposals(
    a: string,
    b: string,
    sampleSize = DEFAULT_SAMPLE_SIZE,
  ): Promise<ProposalComparison> {
    return this.get<ProposalComparison>(`/api/proposals/${a}/compare/${b}`, {
      sample_size: sampleSize,
    });
  }

  /**
   * Decide one pair once for both proposals; 422 invalid_decision, 409
   * already_decided. A failed landing comes back as outcome "failed".
   */
  async decidePair(
    a: string,
    b: string,
    data: PairDecisionRequest,
    sampleSize = DEFAULT_SAMPLE_SIZE,
  ): Promise<PairDecisionResponse> {
    return this.post<PairDecisionResponse>(`/api/proposals/${a}/compare/${b}/decide`, data, {
      sample_size: sampleSize,
    });
  }

  /** Accept the agreements outside the sample; 409 sample_unchecked, 422 sample_too_small. */
  async acceptRest(
    a: string,
    b: string,
    sampleSize = DEFAULT_SAMPLE_SIZE,
  ): Promise<AcceptRestResponse> {
    return this.post<AcceptRestResponse>(`/api/proposals/${a}/compare/${b}/accept-rest`, {
      sample_size: sampleSize,
    });
  }

  async getProposal(id: string): Promise<ChangeProposal> {
    return this.get<ChangeProposal>(`/api/proposals/${id}`);
  }

  async createProposal(data: ChangeProposalCreateRequest): Promise<ChangeProposal> {
    return this.post<ChangeProposal>("/api/proposals", data);
  }

  /** A bulk apply can run longer than the default 30 s timeout, so it waits up to APPLY_TIMEOUT_MS. */
  async applyProposal(id: string, data: ChangeProposalApplyRequest): Promise<ChangeProposal> {
    return this.post<ChangeProposal>(`/api/proposals/${id}/apply`, data, undefined, {
      timeout: APPLY_TIMEOUT_MS,
    });
  }

  async rejectProposal(id: string, data: ChangeProposalRejectRequest): Promise<ChangeProposal> {
    return this.post<ChangeProposal>(`/api/proposals/${id}/reject`, data);
  }

  /**
   * Reopen decided individual and relationship creates, to decide them again: an
   * applied one is undone (with the applied relationships that use it), and its
   * decisions are superseded. 409 when refused; nothing changed.
   */
  async reopenOperations(id: string, data: ChangeProposalReopenRequest): Promise<ChangeProposal> {
    return this.post<ChangeProposal>(`/api/proposals/${id}/reopen`, data);
  }

  /**
   * Add an individual the extraction missed, with the passage the reviewer
   * selected in the proposal's source, and apply it: the proposal afterwards.
   * 422 (detail.errors with a code) when the title, a class or the passage is
   * invalid or the title is taken; 409 when the proposal takes no additions.
   */
  async addIndividual(id: string, data: AddIndividualRequest): Promise<ChangeProposal> {
    return this.post<ChangeProposal>(`/api/proposals/${id}/operations`, data);
  }

  async revertProposal(id: string): Promise<ChangeProposalRevertResponse> {
    return this.post<ChangeProposalRevertResponse>(`/api/proposals/${id}/revert`);
  }

  /** The fields edited since the apply that an in-place revert would overwrite. */
  async getRevertPreview(id: string): Promise<RevertPreview> {
    return this.get<RevertPreview>(`/api/proposals/${id}/revert/preview`);
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
