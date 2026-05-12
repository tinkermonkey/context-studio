import { BaseService } from "./base";
import type { components } from "@/api/types";

type ChangeHistoryResponse = components["schemas"]["ChangeHistoryResponse"];
type ChangesetResponse = components["schemas"]["ChangesetResponse"];
type ChangesetCreateRequest = components["schemas"]["ChangesetCreateRequest"];
type ProposalResponse = components["schemas"]["ProposalResponse"];
type SyncStatusResponse = components["schemas"]["SyncStatusResponse"];
type SyncResultResponse = components["schemas"]["SyncResultResponse"];
type ConflictReportResponse = components["schemas"]["ConflictReportResponse"];

interface ChangesParams {
  limit?: number;
}

class VersioningService extends BaseService {
  async listChangesets(params?: ChangesParams): Promise<ChangesetResponse[]> {
    return this.get<ChangesetResponse[]>(
      "/api/v1/versioning/changesets",
      params as Record<string, unknown>,
    );
  }

  async getChanges(params?: ChangesParams): Promise<ChangeHistoryResponse> {
    return this.get<ChangeHistoryResponse>(
      "/api/v1/versioning/changes",
      params as Record<string, unknown>,
    );
  }

  async getChangesByEntity(
    entityId: string,
    params?: ChangesParams,
  ): Promise<ChangeHistoryResponse> {
    return this.get<ChangeHistoryResponse>(
      `/api/v1/versioning/changes/${entityId}`,
      params as Record<string, unknown>,
    );
  }

  async createChangeset(data: ChangesetCreateRequest): Promise<ChangesetResponse> {
    return this.post<ChangesetResponse>("/api/v1/versioning/changesets", data);
  }

  async getChangeset(id: string): Promise<ChangesetResponse> {
    return this.get<ChangesetResponse>(`/api/v1/versioning/changesets/${id}`);
  }

  async getSyncStatus(): Promise<SyncStatusResponse> {
    return this.get<SyncStatusResponse>("/api/v1/versioning/sync/status");
  }

  async pushSync(): Promise<SyncResultResponse> {
    return this.post<SyncResultResponse>("/api/v1/versioning/sync/push");
  }

  async pullSync(): Promise<SyncResultResponse> {
    return this.post<SyncResultResponse>("/api/v1/versioning/sync/pull");
  }

  async applyChangeset(id: string): Promise<ProposalResponse> {
    return this.post<ProposalResponse>(`/api/v1/versioning/changesets/${id}/apply`);
  }

  async getProposalConflicts(proposalId: string): Promise<ConflictReportResponse> {
    return this.get<ConflictReportResponse>(
      `/api/v1/versioning/proposals/${proposalId}/conflicts`,
    );
  }

  async resolveConflicts(
    proposalId: string,
    resolutions: Record<string, Record<string, unknown>>,
  ): Promise<ConflictReportResponse> {
    return this.post<ConflictReportResponse>(
      `/api/v1/versioning/proposals/${proposalId}/resolve`,
      { resolutions },
    );
  }
}

export const versioningService = new VersioningService();
