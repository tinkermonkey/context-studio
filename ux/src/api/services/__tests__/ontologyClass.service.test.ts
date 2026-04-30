/**
 * Ontology Class Service Tests
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { OntologyClassService } from "../ontologyClass";
import type { AxiosInstance } from "axios";
import type { ListResponse } from "../../types/ontology";

describe("OntologyClassService", () => {
  let mockClient: AxiosInstance;
  let service: OntologyClassService;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
    } as unknown as AxiosInstance;

    service = new OntologyClassService(mockClient);
  });

  describe("list", () => {
    it("should fetch all classes without limit", async () => {
      const mockClasses = [
        {
          id: "class-1",
          title: "Class 1",
          concept_scheme_id: "scheme-1",
          taxonomy_id: "tax-1",
          version: 1,
        },
        {
          id: "class-2",
          title: "Class 2",
          concept_scheme_id: "scheme-1",
          taxonomy_id: "tax-1",
          version: 1,
        },
      ];
      const response: ListResponse<(typeof mockClasses)[0]> = {
        items: mockClasses,
        total: 2,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.list();
      expect(result).toEqual(mockClasses);
    });

    it("should fetch classes by concept_scheme_id", async () => {
      const mockClasses = [
        {
          id: "class-1",
          title: "Class 1",
          concept_scheme_id: "scheme-1",
          taxonomy_id: "tax-1",
          version: 1,
        },
      ];
      const response: ListResponse<(typeof mockClasses)[0]> = {
        items: mockClasses,
        total: 1,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      await service.list({ concept_scheme_id: "scheme-1" });

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.params).toHaveProperty("concept_scheme_id", "scheme-1");
    });

    it("should fetch classes with pagination", async () => {
      const mockClasses = [
        {
          id: "class-1",
          title: "Class 1",
          concept_scheme_id: "scheme-1",
          taxonomy_id: "tax-1",
          version: 1,
        },
      ];
      const response: ListResponse<(typeof mockClasses)[0]> = {
        items: mockClasses,
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
    it("should fetch a single class by ID", async () => {
      const mockClass = {
        id: "class-1",
        title: "Class 1",
        concept_scheme_id: "scheme-1",
        taxonomy_id: "tax-1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: mockClass,
      });

      const result = await service.get("class-1");
      expect(result).toEqual(mockClass);
    });

    it("should throw error when ID is not provided", async () => {
      await expect(service.get("")).rejects.toThrow("id is required");
    });
  });

  describe("create", () => {
    it("should create a new ontology class within scheme", async () => {
      const newClass = { title: "New Class" };
      const response = {
        id: "new-class",
        ...newClass,
        concept_scheme_id: "scheme-1",
        taxonomy_id: "tax-1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.create("scheme-1", newClass);
      expect(result).toEqual(response);
    });

    it("should validate scheme ID is required", async () => {
      await expect(service.create("", { title: "New Class" })).rejects.toThrow(
        "schemeId is required",
      );
    });

    it("should validate title is required", async () => {
      await expect(service.create("scheme-1", { title: "" })).rejects.toThrow(
        "title is required",
      );
    });

    it("should accept parent_class_id in create request", async () => {
      const newClass = {
        title: "Child Class",
        parent_class_id: "parent-1",
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: { id: "new-class", ...newClass, version: 1 },
      });

      await service.create("scheme-1", newClass);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.data).toHaveProperty("parent_class_id", "parent-1");
    });

    it("should construct correct URL with scheme ID", async () => {
      const newClass = { title: "New Class" };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: { id: "new-class", ...newClass, version: 1 },
      });

      await service.create("scheme-1", newClass);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.url).toBe("/api/schemes/scheme-1/classes");
    });
  });

  describe("update", () => {
    it("should update an existing class", async () => {
      const updated = { title: "Updated Class" };
      const response = {
        id: "class-1",
        ...updated,
        concept_scheme_id: "scheme-1",
        taxonomy_id: "tax-1",
        version: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.update("class-1", updated);
      expect(result).toEqual(response);
    });

    it("should validate ID is required", async () => {
      await expect(service.update("", { title: "Updated" })).rejects.toThrow(
        "id is required",
      );
    });
  });

  describe("delete", () => {
    it("should delete a class", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      const result = await service.delete("class-1");
      expect(result).toBeUndefined();
    });

    it("should validate ID is required", async () => {
      await expect(service.delete("")).rejects.toThrow("id is required");
    });
  });
});
