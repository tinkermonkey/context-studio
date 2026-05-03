/**
 * Interchange Runs Hook Tests
 *
 * Tests for useInterchangeRuns and useInterchangeRun hooks
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useInterchangeRuns } from "../useInterchangeRuns";
import { useInterchangeRun } from "../useInterchangeRun";
import { interchangeService } from "../../../services/interchange";

// Mock the service
vi.mock("../../../services/interchange");

const mockInterchangeService = vi.mocked(interchangeService);

describe("useInterchangeRuns", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const createWrapper = () => {
    return ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
  };

  it("should fetch paginated list of runs", async () => {
    const mockRuns: any[] = [
      {
        id: "run-1",
        created_at: "2024-01-01T00:00:00Z",
        created_by: "user-1",
        format: "owl",
        source_uri: "test.owl",
        source_hash: "hash1",
        scope: { scope_type: "whole_graph" as const },
        resolutions: [],
        affected_entity_ids: [],
        status: "committed" as const,
      },
    ];

    mockInterchangeService.listRuns.mockResolvedValueOnce(mockRuns);

    const { result } = renderHook(
      () => useInterchangeRuns({ limit: 50, offset: 0 }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].id).toBe("run-1");
  });

  it("should filter runs by status", async () => {
    const mockRuns: any[] = [
      {
        id: "run-1",
        created_at: "2024-01-01T00:00:00Z",
        created_by: "user-1",
        format: "owl",
        source_uri: "test.owl",
        source_hash: "hash1",
        scope: { scope_type: "whole_graph" as const },
        resolutions: [],
        affected_entity_ids: [],
        status: "pending" as const,
      },
    ];

    mockInterchangeService.listRuns.mockResolvedValueOnce(mockRuns);

    const { result } = renderHook(
      () => useInterchangeRuns({ status: "pending", limit: 50 }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].status).toBe("pending");
  });

  it("should handle error when fetching runs fails", async () => {
    const error = new Error("Internal server error");
    mockInterchangeService.listRuns.mockRejectedValueOnce(error);

    const { result } = renderHook(() => useInterchangeRuns(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
  });
});

describe("useInterchangeRun", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const createWrapper = () => {
    return ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
  };

  it("should fetch a specific run by ID", async () => {
    const mockRun: any = {
      id: "run-123",
      created_at: "2024-01-01T00:00:00Z",
      created_by: "user-1",
      format: "owl",
      source_uri: "test.owl",
      source_hash: "abc123",
      scope: { scope_type: "whole_graph" as const },
      resolutions: [],
      affected_entity_ids: ["entity-1"],
      status: "committed" as const,
    };

    mockInterchangeService.getRun.mockResolvedValueOnce(mockRun);

    const { result } = renderHook(() => useInterchangeRun("run-123"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockRun);
    expect(result.current.data?.id).toBe("run-123");
  });

  it("should not fetch when ID is empty", () => {
    const { result } = renderHook(() => useInterchangeRun(""), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
  });

  it("should handle error when fetching run fails", async () => {
    const error = new Error("Not found");
    mockInterchangeService.getRun.mockRejectedValueOnce(error);

    const { result } = renderHook(() => useInterchangeRun("run-123"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
  });
});
