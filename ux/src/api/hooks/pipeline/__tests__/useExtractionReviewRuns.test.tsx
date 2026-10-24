import { ReactNode } from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { pipelineService } from "@/api/services/pipeline";
import {
  useExtractionReviewRuns,
  type ExtractionReviewRequest,
  type PipelineRunResponse,
} from "../useExtractionReviewRuns";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const run = (id: string, pipeline_type: string, status: string, failure_reason?: string) =>
  ({ id, pipeline_type, status, failure_reason: failure_reason ?? null }) as PipelineRunResponse;

const REQUEST: ExtractionReviewRequest = {
  text: "Context Studio is a local-first app.",
  taxonomy: { id: "tax-1", label: "Tax" },
  conceptScheme: { id: "scheme-1", label: "Scheme" },
  implementationId: "default",
  schemaConfigRef: "schema-default",
  individualConfigRef: "individual-default",
};

describe("useExtractionReviewRuns polling", () => {
  afterEach(() => vi.restoreAllMocks());

  it("polls a run returned as running until it completes or fails", async () => {
    vi.spyOn(pipelineService, "runPipeline").mockImplementation(async (type) =>
      type === "schema_extraction" ? run("run-s", type, "pending") : run("run-i", type, "running"),
    );
    const calls: Record<string, number> = {};
    vi.spyOn(pipelineService, "getRun").mockImplementation(async (id) => {
      calls[id] = (calls[id] ?? 0) + 1;
      // Each run is still running on the first poll, then finishes.
      if (calls[id] < 2) return run(id, "", "running");
      return id === "run-s"
        ? run(id, "schema_extraction", "completed")
        : run(id, "individual_extraction", "failed", "LLM timeout");
    });

    const { result } = renderHook(() => useExtractionReviewRuns({ pollIntervalMs: 20 }), {
      wrapper,
    });
    await act(async () => {
      await result.current.start(REQUEST);
    });
    expect(result.current.schema.status).toBe("running");
    expect(result.current.individual.status).toBe("running");

    await waitFor(() => expect(result.current.schema.status).toBe("completed"));
    await waitFor(() => expect(result.current.individual.status).toBe("failed"));
    expect(result.current.schema.run?.status).toBe("completed");
    expect(result.current.individual.error).toBe("LLM timeout");
    expect(calls["run-s"]).toBeGreaterThanOrEqual(2);

    // Terminal runs are no longer polled.
    const settled = { ...calls };
    await new Promise((r) => setTimeout(r, 100));
    expect(calls).toEqual(settled);
  });

  it("polls a running run opened by id", async () => {
    let polls = 0;
    vi.spyOn(pipelineService, "getRun").mockImplementation(async (id) => {
      polls += 1;
      return run(id, "schema_extraction", polls < 2 ? "running" : "completed");
    });
    const { result } = renderHook(() => useExtractionReviewRuns({ pollIntervalMs: 20 }), {
      wrapper,
    });

    act(() => result.current.open(run("run-s", "schema_extraction", "running")));
    expect(result.current.schema.status).toBe("running");
    await waitFor(() => expect(result.current.schema.status).toBe("completed"));
    expect(result.current.individual.status).toBe("idle");
  });
});
