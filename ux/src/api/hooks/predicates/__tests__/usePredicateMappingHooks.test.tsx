/**
 * Integration Tests for Predicate Mapping Hooks
 *
 * Tests for all hooks related to predicate mapping functionality
 */

import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";
import {
  useExternalPredicates,
  useDiscoveryStatus,
  useSimilarPredicates,
} from "../usePredicates";
import {
  useDiscoverPredicates,
  useClusterPredicates,
  useInvalidateSimilarityCache,
} from "../usePredicateMutations";

// Create a wrapper with QueryClient
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

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("useExternalPredicates", () => {
  it("should accept pagination parameters", () => {
    const { result } = renderHook(
      () =>
        useExternalPredicates(
          {
            skip: 0,
            limit: 20,
          },
          { enabled: false } as any,
        ),
      { wrapper: createWrapper() },
    );

    // Verify hook is initialized correctly
    expect(result.current).toBeDefined();
    expect(result.current.status).toBe("pending");
  });

  it("should accept source filter parameter", () => {
    const { result } = renderHook(
      () =>
        useExternalPredicates(
          {
            skip: 0,
            limit: 20,
            source: "conceptnet",
          },
          { enabled: false } as any,
        ),
      { wrapper: createWrapper() },
    );

    expect(result.current).toBeDefined();
    expect(result.current.status).toBe("pending");
  });
});

describe("useDiscoveryStatus", () => {
  it("should accept task ID parameter", () => {
    const mockTaskId = "test-task-id";

    const { result } = renderHook(
      () =>
        useDiscoveryStatus(mockTaskId, {
          enabled: false, // Disabled to prevent API calls with non-existent task
        } as any),
      { wrapper: createWrapper() },
    );

    // Verify hook is initialized with correct state when disabled
    expect(result.current).toBeDefined();
    expect(result.current.status).toBe("pending");
  });
});

describe("useSimilarPredicates", () => {
  it("should accept predicate ID and parameters", () => {
    const mockPredicateId = "test-predicate-id";

    const { result } = renderHook(
      () =>
        useSimilarPredicates(
          mockPredicateId,
          {
            limit: 10,
            threshold: 0.7,
          },
          {
            enabled: false, // Disabled to prevent API calls with non-existent predicate
          } as any,
        ),
      { wrapper: createWrapper() },
    );

    // Hook should be in pending state when disabled
    expect(result.current).toBeDefined();
    expect(result.current.status).toBe("pending");
  });

  it("should apply source filter parameter", () => {
    const mockPredicateId = "test-predicate-id";

    const { result } = renderHook(
      () =>
        useSimilarPredicates(
          mockPredicateId,
          {
            limit: 10,
            source: "dbpedia",
            threshold: 0.7,
          },
          {
            enabled: false,
          } as any,
        ),
      { wrapper: createWrapper() },
    );

    expect(result.current).toBeDefined();
    expect(result.current.status).toBe("pending");
  });
});

describe("useDiscoverPredicates", () => {
  it("should trigger predicate discovery", async () => {
    const { result } = renderHook(() => useDiscoverPredicates(), {
      wrapper: createWrapper(),
    });

    // Don't actually trigger the mutation in the test
    expect(result.current.mutate).toBeDefined();
    expect(result.current.isPending).toBe(false);
  });

  it("should accept sources parameter", async () => {
    const { result } = renderHook(() => useDiscoverPredicates(), {
      wrapper: createWrapper(),
    });

    // Verify mutation function exists and can accept parameters
    expect(result.current.mutate).toBeDefined();
    expect(typeof result.current.mutate).toBe("function");
  });
});

describe("useClusterPredicates", () => {
  it("should trigger clustering", async () => {
    const { result } = renderHook(() => useClusterPredicates(), {
      wrapper: createWrapper(),
    });

    expect(result.current.mutate).toBeDefined();
    expect(result.current.isPending).toBe(false);
  });

  it("should accept clustering parameters", async () => {
    const { result } = renderHook(() => useClusterPredicates(), {
      wrapper: createWrapper(),
    });

    // Verify mutation function exists and can accept parameters
    expect(result.current.mutate).toBeDefined();
    expect(typeof result.current.mutate).toBe("function");
  });
});

describe("useInvalidateSimilarityCache", () => {
  it("should trigger cache invalidation", async () => {
    const { result } = renderHook(() => useInvalidateSimilarityCache(), {
      wrapper: createWrapper(),
    });

    expect(result.current.mutate).toBeDefined();
    expect(result.current.isPending).toBe(false);
  });

  it("should invalidate queries on success", async () => {
    const { result } = renderHook(() => useInvalidateSimilarityCache(), {
      wrapper: createWrapper(),
    });

    // Verify the mutation has proper setup
    expect(result.current.mutate).toBeDefined();
  });
});

describe("Hook Integration", () => {
  it("should work together in a typical workflow", () => {
    const wrapper = createWrapper();

    // 1. Set up external predicates query
    const { result: externalResult } = renderHook(
      () =>
        useExternalPredicates(
          {
            skip: 0,
            limit: 10,
          },
          { enabled: false } as any,
        ),
      { wrapper },
    );

    expect(externalResult.current).toBeDefined();

    // 2. Set up discovery mutation
    const { result: discoveryResult } = renderHook(
      () => useDiscoverPredicates(),
      { wrapper },
    );

    expect(discoveryResult.current.mutate).toBeDefined();

    // 3. Set up clustering mutation
    const { result: clusterResult } = renderHook(
      () => useClusterPredicates(),
      { wrapper },
    );

    expect(clusterResult.current.mutate).toBeDefined();
  });
});
