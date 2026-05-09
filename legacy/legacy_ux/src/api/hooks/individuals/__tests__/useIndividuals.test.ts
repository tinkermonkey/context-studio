/**
 * Individual Hooks Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import {
  useIndividuals,
  useIndividual,
  useCreateIndividual,
  useUpdateIndividual,
  useDeleteIndividual,
  useAddIndividualClass,
  useRemoveIndividualClass,
  useSetIndividualClasses,
  useIndividualInheritedProperties,
} from "../useIndividuals";
import { individualService } from "../../../services/individual";
import type { components } from "../../../client/types";

type IndividualResponse = components["schemas"]["IndividualResponse"];
type IndividualCreateRequest = components["schemas"]["IndividualCreateRequest"];
type IndividualUpdateRequest = components["schemas"]["IndividualUpdateRequest"];
type DataPropertyValueResponse =
  components["schemas"]["DataPropertyValueResponse"];

// Mock the service
vi.mock("../../../services/individual");

const mockIndividualService = vi.mocked(individualService);

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
};

describe("Individual Hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe("useIndividuals", () => {
    it("should fetch all individuals", async () => {
      const mockIndividuals: IndividualResponse[] = [
        {
          id: "ind-1",
          class_ids: ["class-1"],
          title: "Individual 1",
          version: 1,
        },
      ];

      mockIndividualService.list.mockResolvedValueOnce(mockIndividuals);

      const { result } = renderHook(() => useIndividuals(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockIndividuals);
    });

    it("should pass parameters to service", async () => {
      mockIndividualService.list.mockResolvedValueOnce([]);

      renderHook(() => useIndividuals({ offset: 0, limit: 10 }), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(mockIndividualService.list).toHaveBeenCalledWith({
          offset: 0,
          limit: 10,
        });
      });
    });
  });

  describe("useIndividual", () => {
    it("should fetch a specific individual", async () => {
      const mockIndividual: IndividualResponse = {
        id: "ind-1",
        class_ids: ["class-1"],
        title: "Individual 1",
        version: 1,
      };

      mockIndividualService.get.mockResolvedValueOnce(mockIndividual);

      const { result } = renderHook(() => useIndividual("ind-1"), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockIndividual);
    });

    it("should not fetch when ID is empty", async () => {
      const { result } = renderHook(() => useIndividual(""), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(mockIndividualService.get).not.toHaveBeenCalled();
    });
  });

  describe("useCreateIndividual", () => {
    it("should create an individual and invalidate list", async () => {
      const newIndividual: IndividualCreateRequest = {
        title: "New Individual",
        class_ids: ["class-1"],
      };
      const response: IndividualResponse = {
        id: "ind-1",
        title: "New Individual",
        class_ids: ["class-1"],
        version: 1,
      };

      mockIndividualService.create.mockResolvedValueOnce(response);

      const { result } = renderHook(() => useCreateIndividual(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(newIndividual);

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(response);
      expect(mockIndividualService.create).toHaveBeenCalledWith(newIndividual);
    });
  });

  describe("useUpdateIndividual", () => {
    it("should update an individual and invalidate caches", async () => {
      const update: IndividualUpdateRequest = { title: "Updated" };
      const response: IndividualResponse = {
        id: "ind-1",
        class_ids: ["class-1"],
        title: "Updated",
        version: 2,
      };

      mockIndividualService.update.mockResolvedValueOnce(response);

      const { result } = renderHook(() => useUpdateIndividual(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ id: "ind-1", data: update });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(response);
      expect(mockIndividualService.update).toHaveBeenCalledWith(
        "ind-1",
        update,
      );
    });
  });

  describe("useDeleteIndividual", () => {
    it("should delete an individual", async () => {
      mockIndividualService.delete.mockResolvedValueOnce(undefined);

      const { result } = renderHook(() => useDeleteIndividual(), {
        wrapper: createWrapper(),
      });

      result.current.mutate("ind-1");

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(mockIndividualService.delete).toHaveBeenCalledWith("ind-1");
    });
  });

  describe("useAddIndividualClass", () => {
    it("should add a class and invalidate caches", async () => {
      const response: IndividualResponse = {
        id: "ind-1",
        class_ids: ["class-1", "class-2"],
        title: "Individual 1",
        version: 2,
      };

      mockIndividualService.addClass.mockResolvedValueOnce(response);

      const { result } = renderHook(() => useAddIndividualClass(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ id: "ind-1", classId: "class-2" });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(response);
      expect(mockIndividualService.addClass).toHaveBeenCalledWith(
        "ind-1",
        "class-2",
      );
    });
  });

  describe("useRemoveIndividualClass", () => {
    it("should remove a class and invalidate caches", async () => {
      mockIndividualService.removeClass.mockResolvedValueOnce(undefined);

      const { result } = renderHook(() => useRemoveIndividualClass(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ id: "ind-1", classId: "class-2" });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toBeUndefined();
      expect(mockIndividualService.removeClass).toHaveBeenCalledWith(
        "ind-1",
        "class-2",
      );
    });
  });

  describe("useSetIndividualClasses", () => {
    it("should set class order and invalidate caches", async () => {
      const classIds = ["class-2", "class-1"];
      const response: IndividualResponse = {
        id: "ind-1",
        class_ids: classIds,
        title: "Individual 1",
        version: 2,
      };

      mockIndividualService.setClassOrder.mockResolvedValueOnce(response);

      const { result } = renderHook(() => useSetIndividualClasses(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ id: "ind-1", classIds });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(response);
      expect(mockIndividualService.setClassOrder).toHaveBeenCalledWith(
        "ind-1",
        classIds,
      );
    });
  });

  describe("useIndividualInheritedProperties", () => {
    it("should fetch inherited properties", async () => {
      const mockProperties: DataPropertyValueResponse[] = [
        {
          property_identifier: "prop-1",
          value: "value1",
          datatype: "string",
        },
      ];

      mockIndividualService.getInheritedProperties.mockResolvedValueOnce(
        mockProperties,
      );

      const { result } = renderHook(
        () => useIndividualInheritedProperties("ind-1"),
        {
          wrapper: createWrapper(),
        },
      );

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockProperties);
      expect(mockIndividualService.getInheritedProperties).toHaveBeenCalledWith(
        "ind-1",
      );
    });

    it("should not fetch when ID is empty", async () => {
      const { result } = renderHook(
        () => useIndividualInheritedProperties(""),
        {
          wrapper: createWrapper(),
        },
      );

      expect(result.current.isLoading).toBe(false);
      expect(
        mockIndividualService.getInheritedProperties,
      ).not.toHaveBeenCalled();
    });
  });
});
