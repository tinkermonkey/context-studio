/**
 * Test fixtures for VersioningService using OpenAPI-generated types.
 */

import type { components } from "@/api/types";

export function createChangeHistory(
  overrides?: Partial<components["schemas"]["ChangeHistoryResponse"]>
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
  overrides?: Partial<components["schemas"]["ChangesetResponse"]>
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
  overrides?: Partial<components["schemas"]["ChangesetCreateRequest"]>
): components["schemas"]["ChangesetCreateRequest"] {
  return {
    name: "New changeset",
    description: "Description of changes",
    ...overrides,
  };
}

export function createSyncStatus(
  overrides?: Partial<components["schemas"]["SyncStatusResponse"]>
): components["schemas"]["SyncStatusResponse"] {
  return {
    unprocessed_count: 0,
    is_configured: true,
    is_degraded: false,
    ...overrides,
  };
}

export function createSyncResult(
  overrides?: Partial<components["schemas"]["SyncResultResponse"]>
): components["schemas"]["SyncResultResponse"] {
  return {
    pushed: 10,
    pulled: 0,
    ...overrides,
  };
}
