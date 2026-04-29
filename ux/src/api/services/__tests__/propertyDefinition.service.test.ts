/**
 * Property Definition Service Tests
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { PropertyDefinitionService } from "../propertyDefinition";
import type { AxiosInstance } from "axios";
import type { ListResponse } from "../../types/ontology";

describe("PropertyDefinitionService", () => {
  let mockClient: AxiosInstance;
  let service: PropertyDefinitionService;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
    } as unknown as AxiosInstance;

    service = new PropertyDefinitionService(mockClient);
  });

  describe("list", () => {
    it("should fetch all property definitions without limit", async () => {
      const mockProperties = [
        {
          id: "prop-1",
          title: "Property 1",
          identifier: "prop-1",
          version: 1,
        },
        {
          id: "prop-2",
          title: "Property 2",
          identifier: "prop-2",
          version: 1,
        },
      ];
      const response: ListResponse<typeof mockProperties[0]> = {
        items: mockProperties,
        total: 2,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.list();
      expect(result).toEqual(mockProperties);
    });

    it("should fetch properties with pagination", async () => {
      const mockProperties = [
        {
          id: "prop-1",
          title: "Property 1",
          identifier: "prop-1",
          version: 1,
        },
      ];
      const response: ListResponse<typeof mockProperties[0]> = {
        items: mockProperties,
        total: 10,
        limit: 5,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      await service.list({ offset: 0, limit: 5 });

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.params).toEqual({ offset: 0, limit: 5 });
    });
  });

  describe("get", () => {
    it("should fetch a single property definition by ID", async () => {
      const mockProperty = {
        id: "prop-1",
        title: "Property 1",
        identifier: "prop-1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: mockProperty,
      });

      const result = await service.get("prop-1");
      expect(result).toEqual(mockProperty);
    });

    it("should throw error when ID is not provided", async () => {
      await expect(service.get("")).rejects.toThrow("id is required");
    });

    it("should construct correct URL", async () => {
      const mockProperty = {
        id: "prop-1",
        title: "Property 1",
        identifier: "prop-1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: mockProperty,
      });

      await service.get("prop-1");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.url).toBe("/api/properties/prop-1");
    });
  });

  describe("create", () => {
    it("should create a new property definition", async () => {
      const newProperty = { title: "New Property" };
      const response = {
        id: "new-prop",
        identifier: "new-prop",
        ...newProperty,
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.create(newProperty);
      expect(result).toEqual(response);
    });

    it("should validate title is required", async () => {
      await expect(service.create({ title: "" })).rejects.toThrow(
        "title is required"
      );
    });

    it("should accept optional range parameter", async () => {
      const newProperty = {
        title: "New Property",
        range: "xsd:string",
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: { id: "new-prop", ...newProperty, version: 1 },
      });

      await service.create(newProperty);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.data).toHaveProperty("title", "New Property");
      expect(callConfig.data).toHaveProperty("range", "xsd:string");
    });

    it("should send POST request to correct endpoint", async () => {
      const newProperty = { title: "New Property" };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: { id: "new-prop", ...newProperty, version: 1 },
      });

      await service.create(newProperty);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("POST");
      expect(callConfig.url).toBe("/api/properties");
    });
  });

  describe("update", () => {
    it("should update an existing property definition", async () => {
      const updated = { title: "Updated Property" };
      const response = {
        id: "prop-1",
        identifier: "prop-1",
        ...updated,
        version: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.update("prop-1", updated);
      expect(result).toEqual(response);
    });

    it("should validate ID is required", async () => {
      await expect(
        service.update("", { title: "Updated" })
      ).rejects.toThrow("id is required");
    });

    it("should allow partial updates", async () => {
      const updated = { range: "xsd:integer" };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: {
          id: "prop-1",
          title: "Property 1",
          ...updated,
          version: 2,
        },
      });

      await service.update("prop-1", updated);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.data).toEqual(updated);
    });
  });

  describe("delete", () => {
    it("should delete a property definition", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      const result = await service.delete("prop-1");
      expect(result).toBeUndefined();
    });

    it("should validate ID is required", async () => {
      await expect(service.delete("")).rejects.toThrow("id is required");
    });

    it("should send DELETE request", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      await service.delete("prop-1");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("DELETE");
      expect(callConfig.url).toBe("/api/properties/prop-1");
    });
  });
});
