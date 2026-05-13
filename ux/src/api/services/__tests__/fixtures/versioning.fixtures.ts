/**
 * Test fixtures for VersioningService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

export function createChangeHistory(
  overrides?: Partial<components["schemas"]["ChangeHistoryResponse"]>,
): components["schemas"]["ChangeHistoryResponse"] {
  return {
    events: [
      {
        id: "change-1",
        entity_id: "entity-1",
        entity_type: "taxonomy",
        operation: "create",
        new_state: { title: "Test" },
        timestamp: new Date().toISOString(),
        processed: true,
      },
    ],
    total: 1,
    ...overrides,
  };
}

export function createChangeset(
  overrides?: Partial<components["schemas"]["ChangesetResponse"]>,
): components["schemas"]["ChangesetResponse"] {
  return {
    id: "changeset-1",
    name: "Update taxonomy",
    description: "Update taxonomy description",
    state: "working",
    updated_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

export function createChangesetCreateRequest(
  overrides?: Partial<components["schemas"]["ChangesetCreateRequest"]>,
): components["schemas"]["ChangesetCreateRequest"] {
  return {
    name: "New changeset",
    description: "Description of changes",
    ...overrides,
  };
}

export function createSyncStatus(
  overrides?: Partial<components["schemas"]["SyncStatusResponse"]>,
): components["schemas"]["SyncStatusResponse"] {
  return {
    unprocessed_count: 0,
    is_configured: true,
    is_degraded: false,
    ...overrides,
  };
}

export function createSyncResult(
  overrides?: Partial<components["schemas"]["SyncResultResponse"]>,
): components["schemas"]["SyncResultResponse"] {
  return {
    pushed: 10,
    pulled: 0,
    ...overrides,
  };
}

export function createProposal(
  overrides?: Partial<components["schemas"]["ProposalResponse"]>,
): components["schemas"]["ProposalResponse"] {
  return {
    id: "proposal-1",
    changeset_id: "changeset-1",
    state: "open",
    submitted_at: new Date().toISOString(),
    ...overrides,
  };
}

export function createConflictReport(
  overrides?: Partial<components["schemas"]["ConflictReportResponse"]>,
): components["schemas"]["ConflictReportResponse"] {
  return {
    proposal_id: "proposal-1",
    conflicts: [
      {
        entity_id: "entity-1",
        field_name: "title",
        base_value: "Base Title",
        incoming_value: "Different Title",
        is_resolved: false,
      },
    ],
    has_conflicts: true,
    ...overrides,
  };
}
