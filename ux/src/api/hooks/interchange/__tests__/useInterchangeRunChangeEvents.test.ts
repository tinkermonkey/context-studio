/**
 * Interchange Run Change Events Hook Tests
 *
 * Tests for useInterchangeRunChangeEvents hook
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useInterchangeRunChangeEvents } from "../useInterchangeRunChangeEvents";
import { interchangeService } from "../../../services/interchange";

// Mock the service
vi.mock("../../../services/interchange");

const mockInterchangeService = vi.mocked(interchangeService);

describe("useInterchangeRunChangeEvents", () => {
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

  it("should fetch change events for a run", async () => {
    const mockEvents = [
      {
        id: "event-1",
        timestamp: "2024-01-01T00:00:00Z",
        entity_id: "entity-1",
        entity_type: "Class",
        change_type: "created",
        import_run_id: "run-123",
        details: { title: "New Class" },
      },
    ];

    mockInterchangeService.getRunChangeEvents.mockResolvedValueOnce(
      mockEvents,
    );

    const { result } = renderHook(
      () =>
        useInterchangeRunChangeEvents("run-123", {
          limit: 50,
          offset: 0,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].id).toBe("event-1");
  });

  it("should filter change events by entity type", async () => {
    const mockEvents = [
      {
        id: "event-1",
        timestamp: "2024-01-01T00:00:00Z",
        entity_id: "entity-1",
        entity_type: "Class",
        change_type: "created",
        import_run_id: "run-123",
        details: { title: "New Class" },
      },
    ];

    mockInterchangeService.getRunChangeEvents.mockResolvedValueOnce(
      mockEvents,
    );

    const { result } = renderHook(
      () =>
        useInterchangeRunChangeEvents("run-123", {
          entity_type: "Class",
          limit: 50,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].entity_type).toBe("Class");
  });

  it("should filter change events by change type", async () => {
    const mockEvents = [
      {
        id: "event-1",
        timestamp: "2024-01-01T00:00:00Z",
        entity_id: "entity-1",
        entity_type: "Class",
        change_type: "created",
        import_run_id: "run-123",
        details: {},
      },
    ];

    mockInterchangeService.getRunChangeEvents.mockResolvedValueOnce(
      mockEvents,
    );

    const { result } = renderHook(
      () =>
        useInterchangeRunChangeEvents("run-123", {
          change_type: "created",
          limit: 50,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].change_type).toBe("created");
  });

  it("should not fetch when run ID is empty", () => {
    const { result } = renderHook(
      () => useInterchangeRunChangeEvents(""),
      { wrapper: createWrapper() },
    );

    expect(result.current.isLoading).toBe(false);
  });

  it("should handle error when fetching change events fails", async () => {
    const error = new Error("Not found");
    mockInterchangeService.getRunChangeEvents.mockRejectedValueOnce(error);

    const { result } = renderHook(
      () => useInterchangeRunChangeEvents("run-123"),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
  });
});
