/**
 * Relationship Service Tests
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { RelationshipService } from "../relationship";
import type { AxiosInstance } from "axios";
import type { ListResponse, Relationship } from "../../types/ontology";

describe("RelationshipService", () => {
  let mockClient: AxiosInstance;
  let service: RelationshipService;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
    } as unknown as AxiosInstance;

    service = new RelationshipService(mockClient);
  });

  describe("list", () => {
    it("should fetch all relationships without limit", async () => {
      const mockRelationships: Relationship[] = [
        {
          id: "rel-1",
          source_id: "class-1",
          target_id: "class-2",
          property_definition_id: "prop-1",
          version: 1,
        },
        {
          id: "rel-2",
          source_id: "class-2",
          target_id: "class-3",
          property_definition_id: "prop-1",
          version: 1,
        },
      ];
      const response: ListResponse<(typeof mockRelationships)[0]> = {
        items: mockRelationships,
        total: 2,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.list();
      expect(result).toEqual(mockRelationships);
    });

    it("should use correct field names in query params", async () => {
      const mockRelationships: Relationship[] = [
        {
          id: "rel-1",
          source_id: "class-1",
          target_id: "class-2",
          property_definition_id: "prop-1",
          version: 1,
        },
      ];
      const response: ListResponse<(typeof mockRelationships)[0]> = {
        items: mockRelationships,
        total: 1,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      await service.list({
        source_id: "class-1",
        target_id: "class-2",
        relationship_type: "type-1",
      });

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.params).toMatchObject({
        source_id: "class-1",
        target_id: "class-2",
        relationship_type: "type-1",
      });
    });

    it("should use correct field names (not source_node_id/target_node_id)", async () => {
      const mockRelationships: Relationship[] = [];
      const response: ListResponse<Relationship> = {
        items: mockRelationships,
        total: 0,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      await service.list({ source_id: "class-1" });

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      // Verify we use source_id, not source_node_id
      expect(callConfig.params).toHaveProperty("source_id");
      expect(callConfig.params).not.toHaveProperty("source_node_id");
    });
  });

  describe("get", () => {
    it("should fetch a single relationship by ID", async () => {
      const mockRelationship = {
        id: "rel-1",
        source_id: "class-1",
        target_id: "class-2",
        property_definition_id: "prop-1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: mockRelationship,
      });

      const result = await service.get("rel-1");
      expect(result).toEqual(mockRelationship);
    });

    it("should use correct field names in response", async () => {
      const mockRelationship = {
        id: "rel-1",
        source_id: "class-1",
        target_id: "class-2",
        property_definition_id: "prop-1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: mockRelationship,
      });

      const result = await service.get("rel-1");

      // Verify response contains source_id and target_id, not source_node_id/target_node_id
      expect(result).toHaveProperty("source_id");
      expect(result).toHaveProperty("target_id");
      expect(result).toHaveProperty("property_definition_id");
      expect(result).not.toHaveProperty("source_node_id");
      expect(result).not.toHaveProperty("target_node_id");
      expect(result).not.toHaveProperty("property_id");
    });

    it("should throw error when ID is not provided", async () => {
      await expect(service.get("")).rejects.toThrow("id is required");
    });
  });

  describe("create", () => {
    it("should create a new relationship", async () => {
      const newRelationship = {
        source_id: "class-1",
        target_id: "class-2",
        relationship_type: "type-1",
      };
      const response = {
        id: "new-rel",
        ...newRelationship,
        property_definition_id: "prop-1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.create(newRelationship);
      expect(result).toEqual(response);
    });

    it("should validate source_id is required", async () => {
      await expect(
        service.create({
          source_id: "",
          target_id: "class-2",
          relationship_type: "type-1",
        }),
      ).rejects.toThrow("source_id is required");
    });

    it("should validate target_id is required", async () => {
      await expect(
        service.create({
          source_id: "class-1",
          target_id: "",
          relationship_type: "type-1",
        }),
      ).rejects.toThrow("target_id is required");
    });

    it("should validate relationship_type is required", async () => {
      await expect(
        service.create({
          source_id: "class-1",
          target_id: "class-2",
          relationship_type: "",
        }),
      ).rejects.toThrow("relationship_type is required");
    });

    it("should send POST request with correct field names", async () => {
      const newRelationship = {
        source_id: "class-1",
        target_id: "class-2",
        relationship_type: "type-1",
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: { id: "new-rel", ...newRelationship, version: 1 },
      });

      await service.create(newRelationship);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("POST");
      expect(callConfig.data).toHaveProperty("source_id");
      expect(callConfig.data).toHaveProperty("target_id");
      expect(callConfig.data).not.toHaveProperty("source_node_id");
      expect(callConfig.data).not.toHaveProperty("target_node_id");
    });
  });

  describe("update", () => {
    it("should update an existing relationship", async () => {
      const updated = {
        source_id: "class-1",
        target_id: "class-3",
      };
      const response = {
        id: "rel-1",
        ...updated,
        property_definition_id: "prop-1",
        version: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.update("rel-1", updated);
      expect(result).toEqual(response);
    });

    it("should validate ID is required", async () => {
      await expect(
        service.update("", { source_id: "class-1" }),
      ).rejects.toThrow("id is required");
    });

    it("should send PUT request with correct field names", async () => {
      const updated = { target_id: "class-3" };
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: {
          id: "rel-1",
          source_id: "class-1",
          ...updated,
          version: 2,
        },
      });

      await service.update("rel-1", updated);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("PUT");
      expect(callConfig.data).not.toHaveProperty("source_node_id");
      expect(callConfig.data).not.toHaveProperty("target_node_id");
    });
  });

  describe("delete", () => {
    it("should delete a relationship", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      const result = await service.delete("rel-1");
      expect(result).toBeUndefined();
    });

    it("should validate ID is required", async () => {
      await expect(service.delete("")).rejects.toThrow("id is required");
    });

    it("should send DELETE request", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      await service.delete("rel-1");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("DELETE");
      expect(callConfig.url).toBe("/api/relationships/rel-1");
    });
  });
});
