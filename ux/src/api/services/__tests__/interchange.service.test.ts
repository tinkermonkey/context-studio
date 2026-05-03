/**
 * Interchange Service Tests
 *
 * Unit tests for InterchangeService
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { InterchangeService, SerializationScope } from "../interchange";
import type { AxiosInstance } from "axios";
import type { ListResponse } from "../../types/ontology";

describe("InterchangeService", () => {
  let mockClient: AxiosInstance;
  let service: InterchangeService;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
    } as unknown as AxiosInstance;

    service = new InterchangeService(mockClient);
  });

  describe("exportFile", () => {
    it("should export ontology data and return blob", async () => {
      const mockBlob = new Blob(["mock data"], { type: "application/rdf+xml" });

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: mockBlob });

      const scope: SerializationScope = {
        scope_type: "whole_graph",
        include_descendants: false,
      };

      const result = await service.exportFile("owl", scope);

      expect(result).toBeInstanceOf(Blob);
      expect(vi.mocked(mockClient.request).mock.calls[0][0].method).toBe(
        "POST",
      );
      expect(vi.mocked(mockClient.request).mock.calls[0][0].responseType).toBe(
        "blob",
      );
    });

    it("should throw error if format is missing", async () => {
      const scope: SerializationScope = {
        scope_type: "whole_graph",
        include_descendants: false,
      };

      await expect(service.exportFile("", scope)).rejects.toThrow(
        "format is required",
      );
    });

    it("should throw error if scope is missing", async () => {
      await expect(
        service.exportFile("owl", null as unknown as SerializationScope),
      ).rejects.toThrow("scope is required");
    });
  });

  describe("importFile", () => {
    it("should import file in dry_run mode and return plan", async () => {
      const mockPlan: any = {
        conflicts: [],
        new_entity_count: 5,
        import_run_id: undefined,
        warnings: [],
        source_hash: "abc123",
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: mockPlan });

      const file = new File(["test data"], "test.owl", {
        type: "application/rdf+xml",
      });

      const result = await service.importFile("owl", file, true);

      expect(result).toEqual(mockPlan);
      expect((result as any).conflicts).toEqual([]);
      expect((result as any).new_entity_count).toBe(5);
      expect(vi.mocked(mockClient.request).mock.calls[0][0].method).toBe(
        "POST",
      );
    });

    it("should import file and return committed run", async () => {
      const mockRun: any = {
        id: "run-123",
        created_at: "2024-01-01T00:00:00Z",
        created_by: "user-1",
        format: "owl",
        source_uri: "test.owl",
        source_hash: "abc123",
        scope: { scope_type: "whole_graph" as const, include_descendants: false } as SerializationScope,
        resolutions: [],
        affected_entity_ids: ["entity-1", "entity-2"],
        status: "committed" as const,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: mockRun });

      const file = new File(["test data"], "test.owl", {
        type: "application/rdf+xml",
      });

      const result = await service.importFile("owl", file, false);

      expect(result).toEqual(mockRun);
      expect((result as any).id).toBe("run-123");
    });

    it("should throw error if format is missing", async () => {
      const file = new File(["test data"], "test.owl", {
        type: "application/rdf+xml",
      });

      await expect(service.importFile("", file, true)).rejects.toThrow(
        "format is required",
      );
    });

    it("should throw error if file is missing", async () => {
      await expect(
        service.importFile("owl", null as unknown as File, true),
      ).rejects.toThrow("file is required");
    });
  });

  describe("listRuns", () => {
    it("should fetch paginated list of runs", async () => {
      const mockRuns = [
        {
          id: "run-1",
          created_at: "2024-01-01T00:00:00Z",
          created_by: "user-1",
          format: "owl",
          source_uri: "test.owl",
          source_hash: "hash1",
          scope: { scope_type: "whole_graph", include_descendants: false } as SerializationScope,
          resolutions: [],
          affected_entity_ids: [],
          status: "committed" as const,
        },
      ];
      const response: ListResponse<(typeof mockRuns)[0]> = {
        items: mockRuns,
        total: 1,
        offset: 0,
        limit: 50,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.listRuns({ limit: 50, offset: 0 });

      expect(result).toHaveLength(1);
      expect(result[0].id).toBe("run-1");
    });

    it("should fetch all runs when limit is not specified", async () => {
      const mockRuns = [
        {
          id: "run-1",
          created_at: "2024-01-01T00:00:00Z",
          created_by: "user-1",
          format: "owl",
          source_uri: "test.owl",
          source_hash: "hash1",
          scope: { scope_type: "whole_graph", include_descendants: false } as SerializationScope,
          resolutions: [],
          affected_entity_ids: [],
          status: "committed" as const,
        },
      ];
      const response: ListResponse<(typeof mockRuns)[0]> = {
        items: mockRuns,
        total: 1,
        offset: 0,
        limit: 100,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.listRuns();

      expect(result).toHaveLength(1);
    });

    it("should filter by status", async () => {
      const mockRuns = [
        {
          id: "run-1",
          created_at: "2024-01-01T00:00:00Z",
          created_by: "user-1",
          format: "owl",
          source_uri: "test.owl",
          source_hash: "hash1",
          scope: { scope_type: "whole_graph", include_descendants: false } as SerializationScope,
          resolutions: [],
          affected_entity_ids: [],
          status: "pending" as const,
        },
      ];
      const response: ListResponse<(typeof mockRuns)[0]> = {
        items: mockRuns,
        total: 1,
        offset: 0,
        limit: 50,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.listRuns({ status: "pending", limit: 50 });

      expect(result).toHaveLength(1);
      expect(result[0].status).toBe("pending");
    });
  });

  describe("getRun", () => {
    it("should fetch a specific run by ID", async () => {
      const mockRun = {
        id: "run-123",
        created_at: "2024-01-01T00:00:00Z",
        created_by: "user-1",
        format: "owl",
        source_uri: "test.owl",
        source_hash: "abc123",
        scope: { scope_type: "whole_graph", include_descendants: false } as SerializationScope,
        resolutions: [],
        affected_entity_ids: ["entity-1"],
        status: "committed" as const,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: mockRun });

      const result = await service.getRun("run-123");

      expect(result).toEqual(mockRun);
      expect(result.id).toBe("run-123");
    });

    it("should throw error if ID is missing", async () => {
      await expect(service.getRun("")).rejects.toThrow("id is required");
    });
  });

  describe("getRunChangeEvents", () => {
    it("should fetch change events for a run", async () => {
      const mockEvents = [
        {
          id: "event-1",
          timestamp: "2024-01-01T00:00:00Z",
          entity_id: "entity-1",
          entity_type: "Class",
          change_type: "created",
          import_run_id: "run-123",
          details: { title: "New Class" },
        },
      ];
      const response: ListResponse<(typeof mockEvents)[0]> = {
        items: mockEvents,
        total: 1,
        offset: 0,
        limit: 50,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.getRunChangeEvents("run-123", {
        limit: 50,
        offset: 0,
      });

      expect(result).toHaveLength(1);
      expect(result[0].id).toBe("event-1");
    });

    it("should throw error if run ID is missing", async () => {
      await expect(service.getRunChangeEvents("", {})).rejects.toThrow(
        "id is required",
      );
    });
  });
});
