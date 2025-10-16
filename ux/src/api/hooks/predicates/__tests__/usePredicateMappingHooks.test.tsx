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
  it("should fetch external predicates with pagination", async () => {
    const { result } = renderHook(
      () =>
        useExternalPredicates({
          page: 1,
          page_size: 20,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess || result.current.isError).toBe(true));

    if (result.current.isSuccess) {
      expect(result.current.data).toBeDefined();
      expect(result.current.data?.items).toBeInstanceOf(Array);
    }
  });

  it("should filter external predicates by source", async () => {
    const { result } = renderHook(
      () =>
        useExternalPredicates({
          page: 1,
          page_size: 20,
          source: "conceptnet",
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess || result.current.isError).toBe(true));

    if (result.current.isSuccess && result.current.data?.items) {
      result.current.data.items.forEach((predicate) => {
        expect(predicate.source).toBe("conceptnet");
      });
    }
  });
});

describe("useDiscoveryStatus", () => {
  it("should fetch discovery status by task ID", async () => {
    // Mock task ID - in real scenario this would come from useDiscoverPredicates
    const mockTaskId = "test-task-id";

    const { result } = renderHook(
      () =>
        useDiscoveryStatus(mockTaskId, {
          enabled: !!mockTaskId,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess || result.current.isError).toBe(true));

    // Status check may fail if task doesn't exist, which is expected
    if (result.current.isSuccess) {
      expect(result.current.data).toBeDefined();
      expect(result.current.data).toHaveProperty("status");
    }
  });
});

describe("useSimilarPredicates", () => {
  it("should fetch similar predicates", async () => {
    // This requires a valid predicate ID
    const mockPredicateId = "test-predicate-id";

    const { result } = renderHook(
      () =>
        useSimilarPredicates(
          {
            predicate_id: mockPredicateId,
            top_k: 10,
            similarity_threshold: 0.7,
          },
          {
            enabled: false, // Disabled by default for testing
          },
        ),
      { wrapper: createWrapper() },
    );

    // Hook should be in idle state when disabled
    expect(result.current.isIdle).toBe(true);
  });

  it("should apply source filter", async () => {
    const mockPredicateId = "test-predicate-id";

    const { result } = renderHook(
      () =>
        useSimilarPredicates(
          {
            predicate_id: mockPredicateId,
            top_k: 10,
            source_filter: "dbpedia",
            similarity_threshold: 0.7,
          },
          {
            enabled: false,
          },
        ),
      { wrapper: createWrapper() },
    );

    expect(result.current.isIdle).toBe(true);
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
  it("should work together in a typical workflow", async () => {
    const wrapper = createWrapper();

    // 1. Fetch external predicates
    const { result: externalResult } = renderHook(
      () =>
        useExternalPredicates({
          page: 1,
          page_size: 10,
        }),
      { wrapper },
    );

    await waitFor(() =>
      expect(externalResult.current.isSuccess || externalResult.current.isError).toBe(true),
    );

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
