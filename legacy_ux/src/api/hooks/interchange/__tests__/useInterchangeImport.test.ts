/**
 * Interchange Import Hook Tests
 *
 * Tests for useInterchangeImport hook with cache invalidation behavior
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useInterchangeImport } from "../useInterchangeImport";
import { QUERY_KEYS } from "../../../config";
import { interchangeService } from "../../../services/interchange";

// Mock the service
vi.mock("../../../services/interchange");

const mockInterchangeService = vi.mocked(interchangeService);

describe("useInterchangeImport", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    vi.clearAllMocks();
  });

  const createWrapper = () => {
    return ({ children }: { children: React.ReactNode }) =>
      React.createElement(
        QueryClientProvider,
        { client: queryClient },
        children,
      );
  };

  it("should execute import mutation", async () => {
    const mockPlan = {
      conflicts: [],
      new_entity_count: 5,
      import_run_id: undefined,
      warnings: [],
      source_hash: "abc123",
    };

    mockInterchangeService.importFile.mockResolvedValueOnce(mockPlan);

    const { result } = renderHook(() => useInterchangeImport(), {
      wrapper: createWrapper(),
    });

    const file = new File(["test"], "test.owl");

    result.current.mutate({ format: "owl", file, dry_run: true });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockPlan);
  });

  it("should invalidate entity caches on commit (dry_run=false)", async () => {
    const mockRun: any = {
      id: "run-123",
      created_at: "2024-01-01T00:00:00Z",
      created_by: "user-1",
      format: "owl",
      source_uri: "test.owl",
      source_hash: "abc123",
      scope: { scope_type: "whole_graph" as const },
      resolutions: [],
      affected_entity_ids: [],
      status: "committed" as const,
    };

    mockInterchangeService.importFile.mockResolvedValueOnce(mockRun);

    // Spy on queryClient methods
    const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useInterchangeImport(), {
      wrapper: createWrapper(),
    });

    const file = new File(["test"], "test.owl");

    result.current.mutate({ format: "owl", file, dry_run: false });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Verify that invalidateQueries was called for all entity keys
    const entityKeys = [
      QUERY_KEYS.TAXONOMIES,
      QUERY_KEYS.CONCEPT_SCHEMES,
      QUERY_KEYS.ONTOLOGY_CLASSES,
      QUERY_KEYS.INDIVIDUALS,
      QUERY_KEYS.RELATIONSHIPS,
      QUERY_KEYS.PROPERTY_DEFINITIONS,
      QUERY_KEYS.INTERCHANGE_RUNS,
    ];

    for (const key of entityKeys) {
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: [key],
      });
    }

    expect(invalidateQueriesSpy).toHaveBeenCalledTimes(7);
  });

  it("should not invalidate entity caches on dry_run", async () => {
    const mockPlan = {
      conflicts: [],
      new_entity_count: 5,
      import_run_id: undefined,
      warnings: [],
      source_hash: "abc123",
    };

    mockInterchangeService.importFile.mockResolvedValueOnce(mockPlan);

    // Spy on queryClient methods
    const invalidateQueriesSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useInterchangeImport(), {
      wrapper: createWrapper(),
    });

    const file = new File(["test"], "test.owl");

    result.current.mutate({ format: "owl", file, dry_run: true });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Verify that invalidateQueries was NOT called during dry_run
    expect(invalidateQueriesSpy).not.toHaveBeenCalled();
  });

  it("should handle import errors", async () => {
    const error = new Error("Invalid file format");
    mockInterchangeService.importFile.mockRejectedValueOnce(error);

    const { result } = renderHook(() => useInterchangeImport(), {
      wrapper: createWrapper(),
    });

    const file = new File(["test"], "test.owl");

    result.current.mutate({ format: "owl", file, dry_run: true });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
  });
});
