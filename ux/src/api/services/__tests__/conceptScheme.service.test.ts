/**
 * Concept Scheme Service Tests
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { ConceptSchemeService } from "../conceptScheme";
import type { AxiosInstance } from "axios";
import type { ListResponse } from "../../types/ontology";

describe("ConceptSchemeService", () => {
  let mockClient: AxiosInstance;
  let service: ConceptSchemeService;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
    } as unknown as AxiosInstance;

    service = new ConceptSchemeService(mockClient);
  });

  describe("list", () => {
    it("should fetch all concept schemes without limit", async () => {
      const mockSchemes = [
        {
          id: "scheme-1",
          title: "Scheme 1",
          taxonomy_id: "tax-1",
          version: 1,
        },
        {
          id: "scheme-2",
          title: "Scheme 2",
          taxonomy_id: "tax-1",
          version: 1,
        },
      ];
      const response: ListResponse<(typeof mockSchemes)[0]> = {
        items: mockSchemes,
        total: 2,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.list();
      expect(result).toEqual(mockSchemes);
    });

    it("should filter by taxonomy_id", async () => {
      const mockSchemes = [
        {
          id: "scheme-1",
          title: "Scheme 1",
          taxonomy_id: "tax-1",
          version: 1,
        },
      ];
      const response: ListResponse<(typeof mockSchemes)[0]> = {
        items: mockSchemes,
        total: 1,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      await service.list({ taxonomy_id: "tax-1" });

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.params).toHaveProperty("taxonomy_id", "tax-1");
    });
  });

  describe("get", () => {
    it("should fetch a single concept scheme by ID", async () => {
      const mockScheme = {
        id: "scheme-1",
        title: "Scheme 1",
        taxonomy_id: "tax-1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: mockScheme,
      });

      const result = await service.get("scheme-1");
      expect(result).toEqual(mockScheme);
    });

    it("should throw error when ID is not provided", async () => {
      await expect(service.get("")).rejects.toThrow("id is required");
    });
  });

  describe("create", () => {
    it("should create a new concept scheme within taxonomy", async () => {
      const newScheme = { title: "New Scheme" };
      const response = {
        id: "new-scheme",
        ...newScheme,
        taxonomy_id: "tax-1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.create("tax-1", newScheme);
      expect(result).toEqual(response);
    });

    it("should validate taxonomy ID is required", async () => {
      await expect(service.create("", { title: "New Scheme" })).rejects.toThrow(
        "taxonomyId is required",
      );
    });

    it("should validate title is required", async () => {
      await expect(service.create("tax-1", { title: "" })).rejects.toThrow(
        "title is required",
      );
    });

    it("should accept description in create request", async () => {
      const newScheme = {
        title: "New Scheme",
        description: "A description",
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: { id: "new-scheme", ...newScheme, version: 1 },
      });

      await service.create("tax-1", newScheme);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.data).toHaveProperty("title", "New Scheme");
      expect(callConfig.data).toHaveProperty("description", "A description");
    });

    it("should construct correct URL with taxonomy ID", async () => {
      const newScheme = { title: "New Scheme" };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: { id: "new-scheme", ...newScheme, version: 1 },
      });

      await service.create("tax-1", newScheme);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.url).toBe("/api/taxonomies/tax-1/schemes");
    });
  });

  describe("update", () => {
    it("should update an existing concept scheme", async () => {
      const updated = { title: "Updated Scheme" };
      const response = {
        id: "scheme-1",
        ...updated,
        taxonomy_id: "tax-1",
        version: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.update("scheme-1", updated);
      expect(result).toEqual(response);
    });

    it("should validate ID is required", async () => {
      await expect(service.update("", { title: "Updated" })).rejects.toThrow(
        "id is required",
      );
    });
  });

  describe("delete", () => {
    it("should delete a concept scheme", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      const result = await service.delete("scheme-1");
      expect(result).toBeUndefined();
    });

    it("should validate ID is required", async () => {
      await expect(service.delete("")).rejects.toThrow("id is required");
    });

    it("should send DELETE request with correct URL", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      await service.delete("scheme-1");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("DELETE");
      expect(callConfig.url).toBe("/api/schemes/scheme-1");
    });
  });
});
