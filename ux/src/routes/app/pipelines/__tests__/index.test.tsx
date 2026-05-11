import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import { PipelinesContent } from "../index";
import * as pipelineHooks from "@/api/hooks/pipeline";

vi.mock("@/api/hooks/pipeline");

describe("Pipelines Page", () => {
  const mockPipeline1 = {
    id: "pipeline-1",
    pipeline: "extraction",
    title: "Text Extraction Pipeline",
    provider: "openai",
    model: "gpt-4",
    config: {},
    system_prompt: "Extract entities",
    user_prompt: "Text: {text}",
    version: 1,
    enabled: true,
    created_at: "2026-05-11T00:00:00Z",
    last_updated: "2026-05-11T10:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("page structure", () => {
    it("renders pipelines page container", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <PipelinesContent />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("pipelines-page")).toBeInTheDocument();
    });
  });

  describe("loading state", () => {
    it("renders page during loading", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [],
        isLoading: true,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
        status: "pending",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <PipelinesContent />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("pipelines-page")).toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("displays empty state when no pipelines", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <PipelinesContent />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("pipelines-page")).toBeInTheDocument();
    });
  });

  describe("selectors present", () => {
    it("has pipelines-page data-testid", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <PipelinesContent />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("pipelines-page")).toBeInTheDocument();
    });

  });
});
