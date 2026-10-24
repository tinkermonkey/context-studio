import { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { QUERY_KEYS } from "@/api/config";
import { pipelineService } from "@/api/services/pipeline";
import { useApplyRun, useRevertRun } from "../usePipelineMutations";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { wrapper, invalidateSpy };
}

describe("apply / revert run invalidation", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("useApplyRun invalidates the graph views so applied individuals appear", async () => {
    vi.spyOn(pipelineService, "applyRun").mockResolvedValue({} as never);
    const { wrapper, invalidateSpy } = createWrapper();
    const { result } = renderHook(() => useApplyRun(), { wrapper });

    result.current.mutate({ runId: "run-1", params: {} as never });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: QUERY_KEYS.graph });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: QUERY_KEYS.individuals() });
  });

  it("useRevertRun invalidates the graph views so reverted individuals disappear", async () => {
    vi.spyOn(pipelineService, "revertRun").mockResolvedValue({} as never);
    const { wrapper, invalidateSpy } = createWrapper();
    const { result } = renderHook(() => useRevertRun(), { wrapper });

    result.current.mutate("run-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: QUERY_KEYS.graph });
  });
});
