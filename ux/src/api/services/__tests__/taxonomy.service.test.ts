/**
 * Taxonomy Service Tests
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { TaxonomyService } from "../taxonomy";
import type { AxiosInstance } from "axios";
import type { ListResponse } from "../../types/ontology";

describe("TaxonomyService", () => {
  let mockClient: AxiosInstance;
  let service: TaxonomyService;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
    } as unknown as AxiosInstance;

    service = new TaxonomyService(mockClient);
  });

  describe("list", () => {
    it("should fetch all taxonomies without limit", async () => {
      const mockTaxonomies = [
        { id: "tax-1", title: "Taxonomy 1", version: 1 },
        { id: "tax-2", title: "Taxonomy 2", version: 1 },
      ];
      const response: ListResponse<(typeof mockTaxonomies)[0]> = {
        items: mockTaxonomies,
        total: 2,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.list();
      expect(result).toEqual(mockTaxonomies);
    });

    it("should fetch taxonomies with pagination params", async () => {
      const mockTaxonomies = [{ id: "tax-1", title: "Taxonomy 1", version: 1 }];
      const response: ListResponse<(typeof mockTaxonomies)[0]> = {
        items: mockTaxonomies,
        total: 5,
        limit: 1,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.list({ offset: 0, limit: 1 });
      expect(result).toEqual(mockTaxonomies);
      expect(vi.mocked(mockClient.request).mock.calls[0][0].params).toEqual({
        offset: 0,
        limit: 1,
      });
    });

    it("should throw error on validation failure", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: { results: [] },
      });

      await expect(service.list()).rejects.toThrow(
        "Response format did not match",
      );
    });
  });

  describe("get", () => {
    it("should fetch a single taxonomy by ID", async () => {
      const mockTaxonomy = { id: "tax-1", title: "Taxonomy 1", version: 1 };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: mockTaxonomy,
      });

      const result = await service.get("tax-1");
      expect(result).toEqual(mockTaxonomy);
    });

    it("should throw error when ID is not provided", async () => {
      await expect(service.get("")).rejects.toThrow("id is required");
    });

    it("should construct correct URL", async () => {
      const mockTaxonomy = { id: "tax-1", title: "Taxonomy 1", version: 1 };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: mockTaxonomy,
      });

      await service.get("tax-1");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.url).toBe("/api/taxonomies/tax-1");
    });
  });

  describe("create", () => {
    it("should create a new taxonomy", async () => {
      const newTaxonomy = { title: "New Taxonomy" };
      const response = { id: "new-tax", ...newTaxonomy, version: 1 };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.create(newTaxonomy);
      expect(result).toEqual(response);
    });

    it("should validate title is required", async () => {
      await expect(service.create({ title: "" })).rejects.toThrow(
        "title is required",
      );
    });

    it("should validate title max length", async () => {
      const longTitle = "a".repeat(256);
      await expect(service.create({ title: longTitle })).rejects.toThrow(
        "cannot exceed 255",
      );
    });

    it("should send POST request with correct data", async () => {
      const newTaxonomy = { title: "Test Taxonomy" };
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: { id: "new-tax", ...newTaxonomy, version: 1 },
      });

      await service.create(newTaxonomy);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("POST");
      expect(callConfig.url).toBe("/api/taxonomies");
      expect(callConfig.data).toEqual(newTaxonomy);
    });
  });

  describe("update", () => {
    it("should update an existing taxonomy", async () => {
      const updated = { title: "Updated Title" };
      const response = { id: "tax-1", ...updated, version: 2 };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.update("tax-1", updated);
      expect(result).toEqual(response);
    });

    it("should validate ID is required", async () => {
      await expect(service.update("", { title: "New Title" })).rejects.toThrow(
        "id is required",
      );
    });

    it("should send PUT request with correct data", async () => {
      const updated = { title: "Updated Title" };
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: { id: "tax-1", ...updated, version: 2 },
      });

      await service.update("tax-1", updated);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("PUT");
      expect(callConfig.url).toBe("/api/taxonomies/tax-1");
      expect(callConfig.data).toEqual(updated);
    });
  });

  describe("delete", () => {
    it("should delete a taxonomy", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      const result = await service.delete("tax-1");
      expect(result).toBeUndefined();
    });

    it("should validate ID is required", async () => {
      await expect(service.delete("")).rejects.toThrow("id is required");
    });

    it("should send DELETE request", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      await service.delete("tax-1");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("DELETE");
      expect(callConfig.url).toBe("/api/taxonomies/tax-1");
    });
  });
});
