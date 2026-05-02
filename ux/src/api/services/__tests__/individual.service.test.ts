/**
 * Individual Service Tests
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { IndividualService } from "../individual";
import type { AxiosInstance } from "axios";
import type { components } from "../../client/types";

type ListResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};
type IndividualResponse = components["schemas"]["IndividualResponse"];
type DataPropertyValueResponse = components["schemas"]["DataPropertyValueResponse"];

describe("IndividualService", () => {
  let mockClient: AxiosInstance;
  let service: IndividualService;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
    } as unknown as AxiosInstance;

    service = new IndividualService(mockClient);
  });

  describe("list", () => {
    it("should fetch all individuals without limit", async () => {
      const mockIndividuals: IndividualResponse[] = [
        {
          id: "ind-1",
          class_ids: ["class-1"],
          title: "Individual 1",
          version: 1,
        },
        {
          id: "ind-2",
          class_ids: ["class-2"],
          title: "Individual 2",
          version: 1,
        },
      ];
      const response: ListResponse<IndividualResponse> = {
        items: mockIndividuals,
        total: 2,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.list();
      expect(result).toEqual(mockIndividuals);
    });

    it("should fetch individuals with pagination params", async () => {
      const mockIndividuals: IndividualResponse[] = [
        {
          id: "ind-1",
          class_ids: ["class-1"],
          title: "Individual 1",
          version: 1,
        },
      ];
      const response: ListResponse<IndividualResponse> = {
        items: mockIndividuals,
        total: 5,
        limit: 1,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.list({ offset: 0, limit: 1 });
      expect(result).toEqual(mockIndividuals);
      expect(vi.mocked(mockClient.request).mock.calls[0][0].params).toEqual({
        offset: 0,
        limit: 1,
      });
    });

    it("should include class_id filter in query params", async () => {
      const mockIndividuals: IndividualResponse[] = [
        {
          id: "ind-1",
          class_ids: ["class-1"],
          title: "Individual 1",
          version: 1,
        },
      ];
      const response: ListResponse<IndividualResponse> = {
        items: mockIndividuals,
        total: 1,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      await service.list({ class_id: "class-1" });

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.params).toHaveProperty("class_id", "class-1");
    });
  });

  describe("get", () => {
    it("should fetch a single individual by ID", async () => {
      const mockIndividual: IndividualResponse = {
        id: "ind-1",
        class_ids: ["class-1"],
        title: "Individual 1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: mockIndividual,
      });

      const result = await service.get("ind-1");
      expect(result).toEqual(mockIndividual);
    });

    it("should throw error when ID is not provided", async () => {
      await expect(service.get("")).rejects.toThrow("id is required");
    });

    it("should construct correct URL", async () => {
      const mockIndividual: IndividualResponse = {
        id: "ind-1",
        class_ids: ["class-1"],
        title: "Individual 1",
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: mockIndividual,
      });

      await service.get("ind-1");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.url).toBe("/api/individuals/ind-1");
    });
  });

  describe("create", () => {
    it("should create a new individual", async () => {
      const newIndividual = {
        title: "New Individual",
        class_ids: ["class-1"],
      };
      const response: IndividualResponse = {
        id: "new-ind",
        ...newIndividual,
        version: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.create(newIndividual);
      expect(result).toEqual(response);
    });

    it("should validate title is required", async () => {
      await expect(
        service.create({ title: "", class_ids: ["class-1"] }),
      ).rejects.toThrow("title is required");
    });

    it("should validate title max length", async () => {
      const longTitle = "a".repeat(256);
      await expect(
        service.create({ title: longTitle, class_ids: ["class-1"] }),
      ).rejects.toThrow("cannot exceed 255");
    });

    it("should validate class_ids is required", async () => {
      await expect(
        service.create({
          title: "Test Individual",
          class_ids: undefined as any,
        }),
      ).rejects.toThrow("class_ids is required");
    });

    it("should send POST request with correct data", async () => {
      const newIndividual = {
        title: "Test Individual",
        class_ids: ["class-1"],
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: {
          id: "new-ind",
          ...newIndividual,
          version: 1,
        },
      });

      await service.create(newIndividual);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("POST");
      expect(callConfig.url).toBe("/api/individuals");
      expect(callConfig.data).toEqual(newIndividual);
    });
  });

  describe("update", () => {
    it("should update an existing individual", async () => {
      const updated = { title: "Updated Title" };
      const response: IndividualResponse = {
        id: "ind-1",
        class_ids: ["class-1"],
        ...updated,
        version: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.update("ind-1", updated);
      expect(result).toEqual(response);
    });

    it("should validate ID is required", async () => {
      await expect(
        service.update("", { title: "New Title" }),
      ).rejects.toThrow("id is required");
    });

    it("should validate title max length when provided", async () => {
      const longTitle = "a".repeat(256);
      await expect(
        service.update("ind-1", { title: longTitle }),
      ).rejects.toThrow("cannot exceed 255");
    });

    it("should send PUT request with correct data", async () => {
      const updated = { title: "Updated Title" };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: {
          id: "ind-1",
          class_ids: ["class-1"],
          ...updated,
          version: 2,
        },
      });

      await service.update("ind-1", updated);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("PUT");
      expect(callConfig.url).toBe("/api/individuals/ind-1");
      expect(callConfig.data).toEqual(updated);
    });
  });

  describe("delete", () => {
    it("should delete an individual", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      const result = await service.delete("ind-1");
      expect(result).toBeUndefined();
    });

    it("should validate ID is required", async () => {
      await expect(service.delete("")).rejects.toThrow("id is required");
    });

    it("should send DELETE request", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      await service.delete("ind-1");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("DELETE");
      expect(callConfig.url).toBe("/api/individuals/ind-1");
    });
  });

  describe("addClass", () => {
    it("should add a class to an individual", async () => {
      const response: IndividualResponse = {
        id: "ind-1",
        class_ids: ["class-1", "class-2"],
        title: "Individual 1",
        version: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.addClass("ind-1", "class-2");
      expect(result).toEqual(response);
    });

    it("should validate individual ID is required", async () => {
      await expect(service.addClass("", "class-1")).rejects.toThrow(
        "id is required",
      );
    });

    it("should validate class ID is required", async () => {
      await expect(service.addClass("ind-1", "")).rejects.toThrow(
        "classId is required",
      );
    });

    it("should send POST request to correct endpoint", async () => {
      const response: IndividualResponse = {
        id: "ind-1",
        class_ids: ["class-1", "class-2"],
        title: "Individual 1",
        version: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      await service.addClass("ind-1", "class-2");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("POST");
      expect(callConfig.url).toBe("/api/individuals/ind-1/classes");
      expect(callConfig.data).toEqual({ class_id: "class-2" });
    });
  });

  describe("removeClass", () => {
    it("should remove a class from an individual", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      const result = await service.removeClass("ind-1", "class-2");
      expect(result).toBeUndefined();
    });

    it("should validate individual ID is required", async () => {
      await expect(service.removeClass("", "class-1")).rejects.toThrow(
        "id is required",
      );
    });

    it("should validate class ID is required", async () => {
      await expect(service.removeClass("ind-1", "")).rejects.toThrow(
        "classId is required",
      );
    });

    it("should send DELETE request to correct endpoint", async () => {
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: undefined,
      });

      await service.removeClass("ind-1", "class-2");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("DELETE");
      expect(callConfig.url).toBe("/api/individuals/ind-1/classes/class-2");
    });
  });

  describe("setClassOrder", () => {
    it("should set the order of classes for an individual", async () => {
      const classIds = ["class-2", "class-1"];
      const response: IndividualResponse = {
        id: "ind-1",
        class_ids: classIds,
        title: "Individual 1",
        version: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.setClassOrder("ind-1", classIds);
      expect(result).toEqual(response);
    });

    it("should validate individual ID is required", async () => {
      await expect(
        service.setClassOrder("", ["class-1"]),
      ).rejects.toThrow("id is required");
    });

    it("should validate class IDs are required", async () => {
      await expect(
        service.setClassOrder("ind-1", undefined as any),
      ).rejects.toThrow("classIds is required");
    });

    it("should send PUT request with correct data", async () => {
      const classIds = ["class-2", "class-1"];

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: {
          id: "ind-1",
          class_ids: classIds,
          title: "Individual 1",
          version: 2,
        },
      });

      await service.setClassOrder("ind-1", classIds);

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("PUT");
      expect(callConfig.url).toBe("/api/individuals/ind-1/classes");
      expect(callConfig.data).toEqual({ class_ids: classIds });
    });
  });

  describe("getInheritedProperties", () => {
    it("should fetch inherited properties for an individual", async () => {
      const mockProperties: DataPropertyValueResponse[] = [
        {
          property_identifier: "prop-1",
          value: "value1",
          datatype: "string",
        },
      ];
      const response: ListResponse<DataPropertyValueResponse> = {
        items: mockProperties,
        total: 1,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      const result = await service.getInheritedProperties("ind-1");
      expect(result).toEqual(mockProperties);
    });

    it("should validate individual ID is required", async () => {
      await expect(
        service.getInheritedProperties(""),
      ).rejects.toThrow("id is required");
    });

    it("should send GET request to correct endpoint", async () => {
      const mockProperties: DataPropertyValueResponse[] = [];
      const response: ListResponse<DataPropertyValueResponse> = {
        items: mockProperties,
        total: 0,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: response,
      });

      await service.getInheritedProperties("ind-1");

      const callConfig = vi.mocked(mockClient.request).mock.calls[0][0];
      expect(callConfig.method).toBe("GET");
      expect(callConfig.url).toBe("/api/individuals/ind-1/inherited-properties");
    });
  });
});
