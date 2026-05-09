/**
 * Unit tests for VersioningService using MSW to mock HTTP responses.
 * Tests verify change history, changesets, and sync operations.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { versioningService } from "../versioning";
import {
  createChangeHistory,
  createChangeset,
  createChangesetCreateRequest,
  createSyncStatus,
  createSyncResult,
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

      server.use(
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) => res(ctx.json(mockHistory))),
      );

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

      server.use(
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) => res(ctx.json(mockHistory))),
      );

      const result = await versioningService.getChanges({ limit: 10 });

      expect(result.events).toHaveLength(1);
    });

    it("throws ApiError on 500 from getChanges", async () => {
      server.use(
        rest.get("*/api/v1/versioning/changes", (req, res, ctx) =>
          res(
            ctx.status(500),
            ctx.json({
              detail: "Failed to retrieve changes",
            }),
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
        rest.get("*/api/v1/versioning/changes/entity-123", (req, res, ctx) =>
          res(ctx.json(mockHistory)),
        ),
      );

      const result = await versioningService.getChangesByEntity("entity-123");

      expect(result.events).toHaveLength(2);
      expect(result.total).toBe(2);
    });

    it("throws ApiError on 404 for non-existent entity", async () => {
      server.use(
        rest.get("*/api/v1/versioning/changes/not-found", (req, res, ctx) =>
          res(
            ctx.status(404),
            ctx.json({
              detail: "Entity not found",
            }),
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
        rest.post("*/api/v1/versioning/changesets", (req, res, ctx) => res(ctx.json(mockResponse))),
      );

      const result = await versioningService.createChangeset(createRequest);

      expect(result).toEqual(mockResponse);
      expect(result.id).toBe("changeset-999");
      expect(result.state).toBe("working");
    });

    it("throws ApiError on 400 for invalid changeset data", async () => {
      server.use(
        rest.post("*/api/v1/versioning/changesets", (req, res, ctx) =>
          res(
            ctx.status(400),
            ctx.json({
              detail: "Changeset name is required",
            }),
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
        rest.post("*/api/v1/versioning/changesets", (req, res, ctx) =>
          res(
            ctx.status(409),
            ctx.json({
              detail: "Changeset with this name already exists",
            }),
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
        rest.get("*/api/v1/versioning/changesets/changeset-123", (req, res, ctx) =>
          res(ctx.json(mockChangeset)),
        ),
      );

      const result = await versioningService.getChangeset("changeset-123");

      expect(result).toEqual(mockChangeset);
      expect(result.name).toBe("Specific changeset");
    });

    it("throws ApiError on 404 for non-existent changeset", async () => {
      server.use(
        rest.get("*/api/v1/versioning/changesets/not-found", (req, res, ctx) =>
          res(
            ctx.status(404),
            ctx.json({
              detail: "Changeset not found",
            }),
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

      server.use(
        rest.get("*/api/v1/versioning/sync/status", (req, res, ctx) => res(ctx.json(mockStatus))),
      );

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

      server.use(
        rest.get("*/api/v1/versioning/sync/status", (req, res, ctx) => res(ctx.json(mockStatus))),
      );

      const result = await versioningService.getSyncStatus();

      expect(result.unprocessed_count).toBe(5);
      expect(result.is_configured).toBe(true);
    });

    it("throws ApiError on 500 from getSyncStatus", async () => {
      server.use(
        rest.get("*/api/v1/versioning/sync/status", (req, res, ctx) =>
          res(
            ctx.status(500),
            ctx.json({
              detail: "Failed to get sync status",
            }),
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

      server.use(
        rest.post("*/api/v1/versioning/sync/push", (req, res, ctx) => res(ctx.json(mockResult))),
      );

      const result = await versioningService.pushSync();

      expect(result.pushed).toBe(5);
      expect(result.pulled).toBe(0);
    });

    it("throws ApiError on 409 for sync conflict", async () => {
      server.use(
        rest.post("*/api/v1/versioning/sync/push", (req, res, ctx) =>
          res(
            ctx.status(409),
            ctx.json({
              detail: "Sync conflict detected",
            }),
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
        rest.post("*/api/v1/versioning/sync/push", (req, res, ctx) =>
          res(
            ctx.status(503),
            ctx.json({
              detail: "Remote service unavailable",
            }),
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

      server.use(
        rest.post("*/api/v1/versioning/sync/pull", (req, res, ctx) => res(ctx.json(mockResult))),
      );

      const result = await versioningService.pullSync();

      expect(result.pushed).toBe(0);
      expect(result.pulled).toBe(3);
    });

    it("throws ApiError on 400 when local changes pending", async () => {
      server.use(
        rest.post("*/api/v1/versioning/sync/pull", (req, res, ctx) =>
          res(
            ctx.status(400),
            ctx.json({
              detail: "Local changes must be pushed before pulling",
            }),
          ),
        ),
      );

      await expect(versioningService.pullSync()).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });
});
