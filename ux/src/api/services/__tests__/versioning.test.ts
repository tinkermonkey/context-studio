/**
 * Unit tests for VersioningService using MSW to mock HTTP responses.
 * Tests verify change history, changesets, and sync operations.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { versioningService } from "../versioning";
import {
  createChangeHistory,
  createChangeset,
  createChangesetCreateRequest,
  createSyncStatus,
  createSyncResult,
  createProposal,
  createConflictReport,
} from "./fixtures/versioning.fixtures";

const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

describe("VersioningService", () => {
  describe("getChanges", () => {
    it("returns change history without parameters", async () => {
      const mockHistory = createChangeHistory({
        events: [
          {
            id: "change-1",
            entity_id: "entity-1",
            entity_type: "taxonomy",
            operation: "create",
            new_state: { title: "Test" },
            timestamp: "2025-05-09T12:00:00Z",
            processed: true,
          },
        ],
      });

      server.use(http.get("*/api/v1/versioning/changes", () => HttpResponse.json(mockHistory)));

      const result = await versioningService.getChanges();

      expect(result).toEqual(mockHistory);
      expect(result.events).toHaveLength(1);
      expect(result.events[0].operation).toBe("create");
    });

    it("returns change history with limit parameter", async () => {
      const mockHistory = createChangeHistory({
        events: [
          {
            id: "change-1",
            entity_id: "entity-1",
            entity_type: "taxonomy",
            operation: "update",
            new_state: { title: "Updated" },
            timestamp: "2025-05-09T12:00:00Z",
            processed: true,
          },
        ],
      });

      server.use(http.get("*/api/v1/versioning/changes", () => HttpResponse.json(mockHistory)));

      const result = await versioningService.getChanges({ limit: 10 });

      expect(result.events).toHaveLength(1);
    });

    it("throws ApiError on 500 from getChanges", async () => {
      server.use(
        http.get("*/api/v1/versioning/changes", () =>
          HttpResponse.json(
            {
              detail: "Failed to retrieve changes",
            },
            { status: 500 },
          ),
        ),
      );

      await expect(versioningService.getChanges()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getChangesByEntity", () => {
    it("returns change history for specific entity", async () => {
      const mockHistory = createChangeHistory({
        events: [
          {
            id: "change-1",
            entity_id: "entity-123",
            entity_type: "taxonomy",
            operation: "create",
            new_state: { title: "Test" },
            timestamp: "2025-05-09T12:00:00Z",
            processed: true,
          },
          {
            id: "change-2",
            entity_id: "entity-123",
            entity_type: "taxonomy",
            operation: "update",
            new_state: { title: "Updated" },
            timestamp: "2025-05-09T12:30:00Z",
            processed: true,
          },
        ],
        total: 2,
      });

      server.use(
        http.get("*/api/v1/versioning/changes/entity-123", () => HttpResponse.json(mockHistory)),
      );

      const result = await versioningService.getChangesByEntity("entity-123");

      expect(result.events).toHaveLength(2);
      expect(result.total).toBe(2);
    });

    it("throws ApiError on 404 for non-existent entity", async () => {
      server.use(
        http.get("*/api/v1/versioning/changes/not-found", () =>
          HttpResponse.json(
            {
              detail: "Entity not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(versioningService.getChangesByEntity("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("createChangeset", () => {
    it("creates and returns new changeset", async () => {
      const createRequest = createChangesetCreateRequest({
        name: "Update taxonomy structure",
      });
      const mockResponse = createChangeset({
        id: "changeset-999",
        name: "Update taxonomy structure",
        state: "working",
      });

      server.use(
        http.post("*/api/v1/versioning/changesets", () => HttpResponse.json(mockResponse)),
      );

      const result = await versioningService.createChangeset(createRequest);

      expect(result).toEqual(mockResponse);
      expect(result.id).toBe("changeset-999");
      expect(result.state).toBe("working");
    });

    it("throws ApiError on 400 for invalid changeset data", async () => {
      server.use(
        http.post("*/api/v1/versioning/changesets", () =>
          HttpResponse.json(
            {
              detail: "Changeset name is required",
            },
            { status: 400 },
          ),
        ),
      );

      await expect(
        versioningService.createChangeset({ name: "", description: "" }),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });

    it("throws ApiError on 409 for duplicate changeset", async () => {
      server.use(
        http.post("*/api/v1/versioning/changesets", () =>
          HttpResponse.json(
            {
              detail: "Changeset with this name already exists",
            },
            { status: 409 },
          ),
        ),
      );

      await expect(versioningService.createChangeset({ name: "Existing" })).rejects.toMatchObject({
        name: "ApiError",
        status: 409,
      });
    });
  });

  describe("getChangeset", () => {
    it("returns changeset by ID", async () => {
      const mockChangeset = createChangeset({
        id: "changeset-123",
        name: "Specific changeset",
      });

      server.use(
        http.get("*/api/v1/versioning/changesets/changeset-123", () =>
          HttpResponse.json(mockChangeset),
        ),
      );

      const result = await versioningService.getChangeset("changeset-123");

      expect(result).toEqual(mockChangeset);
      expect(result.name).toBe("Specific changeset");
    });

    it("throws ApiError on 404 for non-existent changeset", async () => {
      server.use(
        http.get("*/api/v1/versioning/changesets/not-found", () =>
          HttpResponse.json(
            {
              detail: "Changeset not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(versioningService.getChangeset("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("getSyncStatus", () => {
    it("returns current sync status", async () => {
      const mockStatus = createSyncStatus({
        unprocessed_count: 0,
        is_configured: true,
        is_degraded: false,
      });

      server.use(http.get("*/api/v1/versioning/sync/status", () => HttpResponse.json(mockStatus)));

      const result = await versioningService.getSyncStatus();

      expect(result).toEqual(mockStatus);
      expect(result.unprocessed_count).toBe(0);
      expect(result.is_configured).toBe(true);
    });

    it("returns sync status with pending changes", async () => {
      const mockStatus = createSyncStatus({
        unprocessed_count: 5,
        is_configured: true,
        is_degraded: false,
      });

      server.use(http.get("*/api/v1/versioning/sync/status", () => HttpResponse.json(mockStatus)));

      const result = await versioningService.getSyncStatus();

      expect(result.unprocessed_count).toBe(5);
      expect(result.is_configured).toBe(true);
    });

    it("throws ApiError on 500 from getSyncStatus", async () => {
      server.use(
        http.get("*/api/v1/versioning/sync/status", () =>
          HttpResponse.json(
            {
              detail: "Failed to get sync status",
            },
            { status: 500 },
          ),
        ),
      );

      await expect(versioningService.getSyncStatus()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("pushSync", () => {
    it("pushes local changes to remote", async () => {
      const mockResult = createSyncResult({
        pushed: 5,
        pulled: 0,
      });

      server.use(http.post("*/api/v1/versioning/sync/push", () => HttpResponse.json(mockResult)));

      const result = await versioningService.pushSync();

      expect(result.pushed).toBe(5);
      expect(result.pulled).toBe(0);
    });

    it("throws ApiError on 409 for sync conflict", async () => {
      server.use(
        http.post("*/api/v1/versioning/sync/push", () =>
          HttpResponse.json(
            {
              detail: "Sync conflict detected",
            },
            { status: 409 },
          ),
        ),
      );

      await expect(versioningService.pushSync()).rejects.toMatchObject({
        name: "ApiError",
        status: 409,
      });
    });

    it("throws ApiError on 503 when remote unavailable", async () => {
      server.use(
        http.post("*/api/v1/versioning/sync/push", () =>
          HttpResponse.json(
            {
              detail: "Remote service unavailable",
            },
            { status: 503 },
          ),
        ),
      );

      await expect(versioningService.pushSync()).rejects.toMatchObject({
        name: "ApiError",
        status: 503,
      });
    });
  });

  describe("pullSync", () => {
    it("pulls remote changes to local", async () => {
      const mockResult = createSyncResult({
        pushed: 0,
        pulled: 3,
      });

      server.use(http.post("*/api/v1/versioning/sync/pull", () => HttpResponse.json(mockResult)));

      const result = await versioningService.pullSync();

      expect(result.pushed).toBe(0);
      expect(result.pulled).toBe(3);
    });

    it("throws ApiError on 400 when local changes pending", async () => {
      server.use(
        http.post("*/api/v1/versioning/sync/pull", () =>
          HttpResponse.json(
            {
              detail: "Local changes must be pushed before pulling",
            },
            { status: 400 },
          ),
        ),
      );

      await expect(versioningService.pullSync()).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("listChangesets", () => {
    it("returns list of changesets from GET /api/v1/versioning/changesets", async () => {
      const mockChangesets = [
        createChangeset({ id: "cs-1", name: "Changeset 1" }),
        createChangeset({ id: "cs-2", name: "Changeset 2" }),
      ];

      server.use(
        http.get("*/api/v1/versioning/changesets", () => HttpResponse.json(mockChangesets)),
      );

      const result = await versioningService.listChangesets();

      expect(result).toHaveLength(2);
      expect(result[0].name).toBe("Changeset 1");
    });

    it("throws ApiError on 500 from listChangesets", async () => {
      server.use(
        http.get("*/api/v1/versioning/changesets", () =>
          HttpResponse.json(
            {
              detail: "Internal server error",
            },
            { status: 500 },
          ),
        ),
      );

      await expect(versioningService.listChangesets()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("applyChangeset", () => {
    it("applies changeset and returns proposal from POST /api/v1/versioning/changesets/:id/apply", async () => {
      const mockProposal = createProposal({ changeset_id: "changeset-123" });

      server.use(
        http.post("*/api/v1/versioning/changesets/changeset-123/apply", () =>
          HttpResponse.json(mockProposal),
        ),
      );

      const result = await versioningService.applyChangeset("changeset-123");

      expect(result.changeset_id).toBe("changeset-123");
    });

    it("throws ApiError with 404 on applyChangeset with non-existent changeset", async () => {
      server.use(
        http.post("*/api/v1/versioning/changesets/not-found/apply", () =>
          HttpResponse.json(
            {
              detail: "Changeset not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(versioningService.applyChangeset("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("getProposalConflicts", () => {
    it("returns conflict report from GET /api/v1/versioning/proposals/:id/conflicts", async () => {
      const mockConflicts = createConflictReport({ proposal_id: "proposal-123" });

      server.use(
        http.get("*/api/v1/versioning/proposals/proposal-123/conflicts", () =>
          HttpResponse.json(mockConflicts),
        ),
      );

      const result = await versioningService.getProposalConflicts("proposal-123");

      expect(result.proposal_id).toBe("proposal-123");
      expect(result.has_conflicts).toBe(true);
    });

    it("throws ApiError with 404 on getProposalConflicts with non-existent proposal", async () => {
      server.use(
        http.get("*/api/v1/versioning/proposals/not-found/conflicts", () =>
          HttpResponse.json(
            {
              detail: "Proposal not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(versioningService.getProposalConflicts("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("resolveConflicts", () => {
    it("resolves conflicts from POST /api/v1/versioning/proposals/:id/resolve", async () => {
      const mockConflicts = createConflictReport({ has_conflicts: false });

      server.use(
        http.post("*/api/v1/versioning/proposals/proposal-123/resolve", () =>
          HttpResponse.json(mockConflicts),
        ),
      );

      const resolutions: Record<string, Record<string, unknown>> = {
        "entity-1": {
          title: "Resolved Title",
        },
      };

      const result = await versioningService.resolveConflicts("proposal-123", resolutions);

      expect(result.has_conflicts).toBe(false);
    });

    it("throws ApiError with 400 on resolveConflicts with incomplete resolutions", async () => {
      const resolutions: Record<string, Record<string, unknown>> = {
        "entity-1": {
          title: "Resolved Title",
        },
      };

      server.use(
        http.post("*/api/v1/versioning/proposals/proposal-123/resolve", () =>
          HttpResponse.json(
            {
              detail: "All conflicts must be resolved",
            },
            { status: 400 },
          ),
        ),
      );

      await expect(
        versioningService.resolveConflicts("proposal-123", resolutions),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });
});
