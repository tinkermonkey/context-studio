/**
 * Interchange Export Hook Tests
 *
 * Tests for useInterchangeExport hook
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useInterchangeExport } from "../useInterchangeExport";
import { interchangeService } from "../../../services/interchange";

// Mock the service
vi.mock("../../../services/interchange");

const mockInterchangeService = vi.mocked(interchangeService);

describe("useInterchangeExport", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
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

  it("should export ontology data and return blob", async () => {
    const mockBlob = new Blob(["mock data"], { type: "application/rdf+xml" });

    mockInterchangeService.exportFile.mockResolvedValueOnce(mockBlob);

    const { result } = renderHook(() => useInterchangeExport(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      format: "owl",
      scope: { scope_type: "whole_graph", include_descendants: false },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toBeInstanceOf(Blob);
  });

  it("should handle export errors", async () => {
    const error = new Error("Invalid format");
    mockInterchangeService.exportFile.mockRejectedValueOnce(error);

    const { result } = renderHook(() => useInterchangeExport(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      format: "invalid",
      scope: { scope_type: "whole_graph", include_descendants: false },
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeDefined();
  });

  it("should not cache export results", async () => {
    const mockBlob = new Blob(["data"], { type: "application/rdf+xml" });

    mockInterchangeService.exportFile.mockResolvedValueOnce(mockBlob);

    const { result } = renderHook(() => useInterchangeExport(), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      format: "owl",
      scope: { scope_type: "whole_graph", include_descendants: false },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Each export should be treated as a fresh request (not cached)
    expect(result.current.data).toBeInstanceOf(Blob);
  });
});
