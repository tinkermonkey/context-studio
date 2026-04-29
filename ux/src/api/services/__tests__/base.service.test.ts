/**
 * BaseService Tests
 *
 * Tests for the BaseService class, focusing on error handling and data extraction
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { BaseService, type PaginatedResponse } from "../base";
import type { ListResponse } from "../../types/ontology";
import type { AxiosInstance } from "axios";

// Create a test service class that extends BaseService
class TestService extends BaseService {
  constructor(client: AxiosInstance) {
    super(client);
  }

  // Expose the private extractItems method for testing
  public testExtractItems<T>(
    response: ListResponse<T> | PaginatedResponse<T>,
  ): T[] {
    return this.extractItems(response);
  }

  // Expose getAllPaginated for testing
  public testGetAllPaginated<T>(
    url: string,
    params?: Record<string, unknown>,
  ): Promise<T[]> {
    return this.getAllPaginated<T>(url, params);
  }

  // Expose getPage for testing
  public testGetPage<T>(
    url: string,
    params?: Record<string, unknown>,
  ): Promise<T[]> {
    return this.getPage<T>(url, params);
  }

  // Expose withErrorContext for testing
  public testWithErrorContext<T>(
    operation: () => Promise<T>,
    context: string,
  ): Promise<T> {
    return this.withErrorContext(operation, context);
  }
}

describe("BaseService", () => {
  let mockClient: AxiosInstance;
  let service: TestService;

  beforeEach(() => {
    // Create a mock Axios client
    mockClient = {
      request: vi.fn(),
    } as unknown as AxiosInstance;

    service = new TestService(mockClient);
  });

  describe("extractItems", () => {
    it("should extract items from ListResponse format with 'items' property", () => {
      const mockItems = [
        { id: "1", title: "Item 1" },
        { id: "2", title: "Item 2" },
      ];
      const response: ListResponse<{ id: string; title: string }> = {
        items: mockItems,
        total: 2,
        limit: 50,
        offset: 0,
      };

      const result = service.testExtractItems(response);
      expect(result).toEqual(mockItems);
    });

    it("should extract items from PaginatedResponse format with 'data' property", () => {
      const mockItems = [
        { id: "1", title: "Item 1" },
        { id: "2", title: "Item 2" },
      ];
      const response: PaginatedResponse<{ id: string; title: string }> = {
        data: mockItems,
        total: 2,
        skip: 0,
        limit: 50,
      };

      const result = service.testExtractItems(response);
      expect(result).toEqual(mockItems);
    });

    it("should throw error when response format matches neither ListResponse nor PaginatedResponse", () => {
      // Response with neither 'items' nor 'data' property
      const invalidResponse = {
        results: [{ id: "1", title: "Item 1" }],
      } as unknown as ListResponse<{ id: string; title: string }>;

      expect(() => service.testExtractItems(invalidResponse)).toThrow(
        "Response format did not match ListResponse or PaginatedResponse",
      );
    });

    it("should throw error when 'items' is not an array", () => {
      const invalidResponse = {
        items: "not an array",
      } as unknown as ListResponse<{ id: string; title: string }>;

      expect(() => service.testExtractItems(invalidResponse)).toThrow(
        "Response format did not match ListResponse or PaginatedResponse",
      );
    });

    it("should throw error when 'data' is not an array", () => {
      const invalidResponse = {
        data: "not an array",
        total: 1,
        skip: 0,
        limit: 50,
      } as unknown as PaginatedResponse<{ id: string; title: string }>;

      expect(() => service.testExtractItems(invalidResponse)).toThrow(
        "Response format did not match ListResponse or PaginatedResponse",
      );
    });

    it("should return empty array when ListResponse has empty items", () => {
      const response: ListResponse<{ id: string; title: string }> = {
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      };

      const result = service.testExtractItems(response);
      expect(result).toEqual([]);
    });

    it("should return empty array when PaginatedResponse has empty data", () => {
      const response: PaginatedResponse<{ id: string; title: string }> = {
        data: [],
        total: 0,
        skip: 0,
        limit: 50,
      };

      const result = service.testExtractItems(response);
      expect(result).toEqual([]);
    });
  });

  describe("getAllPaginated", () => {
    it("should propagate extractItems error when response format is invalid", async () => {
      // Mock client to return invalid response format
      const invalidResponse = { results: [] }; // Neither 'items' nor 'data'
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: invalidResponse,
      });

      await expect(
        service.testGetAllPaginated<{ id: string; title: string }>(
          "/api/items",
        ),
      ).rejects.toThrow(
        "Response format did not match ListResponse or PaginatedResponse",
      );
    });

    it("should extract items from valid paginated response", async () => {
      const mockItems = [
        { id: "1", title: "Item 1" },
        { id: "2", title: "Item 2" },
      ];
      const response: PaginatedResponse<{ id: string; title: string }> = {
        data: mockItems,
        total: 2,
        skip: 0,
        limit: 50,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.testGetAllPaginated<{
        id: string;
        title: string;
      }>("/api/items");
      expect(result).toEqual(mockItems);
    });

    it("should stop fetching when fewer items than limit are returned", async () => {
      const page1Items = [
        { id: "1", title: "Item 1" },
        { id: "2", title: "Item 2" },
      ];

      // First page response - fewer items than limit indicates last page
      const response1: PaginatedResponse<{ id: string; title: string }> = {
        data: page1Items,
        total: 2,
        skip: 0,
        limit: 100, // maxPageSize is 100 by default
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response1 });

      const result = await service.testGetAllPaginated<{
        id: string;
        title: string;
      }>("/api/items");

      // Should return all items from first page and stop because items.length < limit
      expect(result).toEqual(page1Items);
      // Should only make one request
      expect(vi.mocked(mockClient.request).mock.calls.length).toBe(1);
    });

    it("should fetch multiple pages until all items retrieved", async () => {
      // Create arrays with exactly 100 items (the default maxPageSize)
      const page1Items = Array.from({ length: 100 }, (_, i) => ({
        id: String(i + 1),
        title: `Item ${i + 1}`,
      }));
      const page2Items = Array.from({ length: 50 }, (_, i) => ({
        id: String(101 + i),
        title: `Item ${101 + i}`,
      }));

      const response1: PaginatedResponse<{ id: string; title: string }> = {
        data: page1Items,
        total: 150,
        skip: 0,
        limit: 100,
      };

      // Second page - fewer items than limit indicates last page
      const response2: PaginatedResponse<{ id: string; title: string }> = {
        data: page2Items,
        total: 150,
        skip: 100,
        limit: 100,
      };

      vi.mocked(mockClient.request)
        .mockResolvedValueOnce({ data: response1 })
        .mockResolvedValueOnce({ data: response2 });

      const result = await service.testGetAllPaginated<{
        id: string;
        title: string;
      }>("/api/items");

      expect(result).toEqual([...page1Items, ...page2Items]);
      // Should make two requests
      expect(vi.mocked(mockClient.request).mock.calls.length).toBe(2);
    });

    it("should throw error when max iterations exceeded to prevent infinite loops", async () => {
      const mockItems = Array.from({ length: 100 }, (_, i) => ({
        id: String(i),
        title: `Item ${i}`,
      }));

      // Mock server returning same page repeatedly (returns offset=0 every time)
      const response: PaginatedResponse<{ id: string; title: string }> = {
        data: mockItems,
        total: 999999, // Very large total to prevent early exit
        skip: 0,
        limit: 100,
      };

      // Mock all requests to return the same page
      vi.mocked(mockClient.request).mockResolvedValue({ data: response });

      await expect(
        service.testGetAllPaginated<{ id: string; title: string }>(
          "/api/items",
        ),
      ).rejects.toThrow("exceeded maximum iterations");
    });

    it("should stop when allItems.length >= total", async () => {
      const page1Items = Array.from({ length: 100 }, (_, i) => ({
        id: String(i + 1),
        title: `Item ${i + 1}`,
      }));

      const response: PaginatedResponse<{ id: string; title: string }> = {
        data: page1Items,
        total: 100, // Exactly 100 items total
        skip: 0,
        limit: 100,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.testGetAllPaginated<{
        id: string;
        title: string;
      }>("/api/items");

      expect(result).toEqual(page1Items);
      // Should only make one request
      expect(vi.mocked(mockClient.request).mock.calls.length).toBe(1);
    });

    it("should not throw error when exactly maxIterations pages are needed and last page completes successfully", async () => {
      const maxIterations = 1000;
      const itemsPerPage = 100;
      const totalItems = maxIterations * itemsPerPage; // Exactly 100,000 items

      // Create a mock function that returns different pages based on offset
      let callCount = 0;
      vi.mocked(mockClient.request).mockImplementation(async () => {
        const offset = callCount * itemsPerPage;
        const pageItems = Array.from({ length: itemsPerPage }, (_, i) => ({
          id: String(offset + i),
          title: `Item ${offset + i}`,
        }));

        const response: PaginatedResponse<{ id: string; title: string }> = {
          data: pageItems,
          total: totalItems,
          skip: offset,
          limit: itemsPerPage,
        };

        callCount++;
        return { data: response };
      });

      // Should not throw and should return all items successfully
      const result = await service.testGetAllPaginated<{
        id: string;
        title: string;
      }>("/api/items");

      expect(result.length).toBe(totalItems);
      // Should make exactly maxIterations requests
      expect(callCount).toBe(maxIterations);
    });
  });

  describe("getPage", () => {
    it("should propagate extractItems error when response format is invalid", async () => {
      // Mock client to return invalid response format
      const invalidResponse = { results: [] }; // Neither 'items' nor 'data'
      vi.mocked(mockClient.request).mockResolvedValueOnce({
        data: invalidResponse,
      });

      await expect(
        service.testGetPage<{ id: string; title: string }>("/api/items"),
      ).rejects.toThrow(
        "Response format did not match ListResponse or PaginatedResponse",
      );
    });

    it("should return extracted items from valid paginated response", async () => {
      const mockItems = [
        { id: "1", title: "Item 1" },
        { id: "2", title: "Item 2" },
      ];
      const response: PaginatedResponse<{ id: string; title: string }> = {
        data: mockItems,
        total: 10,
        skip: 0,
        limit: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.testGetPage<{
        id: string;
        title: string;
      }>("/api/items");
      expect(result).toEqual(mockItems);
    });

    it("should return extracted items from valid ListResponse", async () => {
      const mockItems = [
        { id: "1", title: "Item 1" },
        { id: "2", title: "Item 2" },
      ];
      const response: ListResponse<{ id: string; title: string }> = {
        items: mockItems,
        total: 2,
        limit: 50,
        offset: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValueOnce({ data: response });

      const result = await service.testGetPage<{
        id: string;
        title: string;
      }>("/api/items");
      expect(result).toEqual(mockItems);
    });
  });

  describe("withErrorContext", () => {
    it("should add service and operation context to error messages", async () => {
      const testError = new Error("Network failed");

      // Create a simple async operation that throws
      const operation = async () => {
        throw testError;
      };

      // Service name is "Test" because "Service" suffix is removed from "TestService"
      await expect(
        service.testWithErrorContext(operation, "test operation"),
      ).rejects.toThrow("Test test operation: Network failed");
    });

    it("should re-throw non-Error objects unchanged", async () => {
      const testError = "String error";

      const operation = async () => {
        throw testError;
      };

      // Non-Error objects should be re-thrown unchanged
      await expect(
        service.testWithErrorContext(operation, "test"),
      ).rejects.toEqual(testError);
    });

    it("should return successful operation result", async () => {
      const expectedResult = { success: true };

      const operation = async () => {
        return expectedResult;
      };

      const result = await service.testWithErrorContext(
        operation,
        "test operation",
      );
      expect(result).toEqual(expectedResult);
    });
  });
});
