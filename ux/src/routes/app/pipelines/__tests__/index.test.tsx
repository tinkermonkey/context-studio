import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import { PipelinesContent } from "../index";
import * as pipelineHooks from "@/api/hooks/pipeline";

vi.mock("@/api/hooks/pipeline");
vi.mock("@/components/ui/Toast", () => ({
  useToasts: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock("@/stores/executionStore", () => ({
  useExecutionStore: vi.fn((selector) => {
    const state = {
      inFlightPipelineIds: new Set(),
      startExecution: vi.fn(),
      endExecution: vi.fn(),
      hasRunningExecutions: vi.fn(() => false),
    };
    return selector ? selector(state) : state;
  }),
}));

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

  const mockPipeline2 = {
    id: "pipeline-2",
    pipeline: "enrichment",
    title: "Knowledge Enrichment Pipeline",
    provider: "anthropic",
    model: "claude-opus",
    config: {},
    system_prompt: "Enrich knowledge",
    user_prompt: "Data: {data}",
    version: 1,
    enabled: false,
    created_at: "2026-05-10T00:00:00Z",
    last_updated: "2026-05-10T10:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    } as any);

    vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      status: "idle",
    } as any);

    vi.mocked(pipelineHooks.useAllPipelineExecutions).mockReturnValue({
      data: { items: [], total: 0 },
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    vi.mocked(pipelineHooks.useCreatePipeline).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      status: "idle",
    } as any);
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

    it("renders page title when pipelines are loaded", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1],
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

      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  describe("loading state", () => {
    it("renders skeleton loaders during loading", () => {
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
      expect(screen.queryByTestId("pipelines-grid")).not.toBeInTheDocument();
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

  describe("error state", () => {
    it("renders error banner when pipeline fetch fails", () => {
      const error = new Error("Failed to load pipelines");
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [],
        isLoading: false,
        error,
        refetch: vi.fn(),
        isFetching: false,
        status: "error",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <PipelinesContent />
        </QueryClientProvider>,
      );

      expect(screen.getByTestId("pipelines-page")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });

  describe("populated state", () => {
    it("renders pipelines grid when data is available", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1, mockPipeline2],
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

      expect(screen.getByTestId("pipelines-grid")).toBeInTheDocument();
    });

    it("renders pipeline cards for each pipeline", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1, mockPipeline2],
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

      expect(screen.getByTestId("pipelines-grid")).toBeInTheDocument();
      expect(screen.getByTestId(`pipeline-card-${mockPipeline1.id}`)).toBeInTheDocument();
      expect(screen.getByTestId(`pipeline-card-${mockPipeline2.id}`)).toBeInTheDocument();
    });
  });

  describe("search and filtering", () => {
    it("renders search input", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1, mockPipeline2],
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

      expect(screen.getByTestId("pipelines-search-input")).toBeInTheDocument();
    });

    it("renders status filter buttons with ARIA roles", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1, mockPipeline2],
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

      const filterButtons = screen.getAllByRole("radio");
      expect(filterButtons.length).toBeGreaterThan(0);
      filterButtons.forEach((button) => {
        expect(button).toHaveAttribute("aria-checked");
      });
    });
  });

  describe("accessibility and styling", () => {
    it("pipelines grid uses proper grid layout class", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1, mockPipeline2],
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

      const grid = screen.getByTestId("pipelines-grid");
      expect(grid).toHaveClass("grid-2");
    });

    it("status filter renders as a labeled group of radio options", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1],
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

      const group = screen.getByRole("group", { name: /filter pipelines by status/i });
      expect(group).toBeInTheDocument();
      const radios = screen.getAllByRole("radio");
      expect(radios.length).toBe(5);
    });

    it("page title renders as heading level 1 when pipelines exist", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1],
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

      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  describe("failed pipeline sorting", () => {
    it("pins failed pipelines to top of the list", () => {
      const failedExecution = {
        id: "exec-failed",
        pipeline_config_id: "pipeline-1",
        output_text: "Error",
        provider: "openai",
        model: "gpt-4",
        tokens_in: 100,
        tokens_out: 50,
        duration_ms: 2000,
        status: "error" as const,
        error_message: "Execution failed",
        timestamp: "2026-05-11T10:00:00Z",
      };

      const successExecution = {
        id: "exec-success",
        pipeline_config_id: "pipeline-2",
        output_text: "Result",
        provider: "anthropic",
        model: "claude-opus",
        tokens_in: 100,
        tokens_out: 50,
        duration_ms: 2000,
        status: "success" as const,
        error_message: null,
        timestamp: "2026-05-11T12:00:00Z",
      };

      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1, mockPipeline2],
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
        status: "success",
      } as any);

      vi.mocked(pipelineHooks.useAllPipelineExecutions).mockReturnValue({
        data: {
          items: [failedExecution, successExecution],
          total: 2,
        },
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <PipelinesContent />
        </QueryClientProvider>,
      );

      const grid = screen.getByTestId("pipelines-grid");
      const cards = grid.querySelectorAll("[data-testid^='pipeline-card-']");
      expect(cards.length).toBe(2);
      expect(cards[0]).toHaveAttribute("data-testid", "pipeline-card-pipeline-1");
      expect(cards[1]).toHaveAttribute("data-testid", "pipeline-card-pipeline-2");
    });

    it("handles timeout status as failed for sorting purposes", () => {
      const timeoutExecution = {
        id: "exec-timeout",
        pipeline_config_id: "pipeline-2",
        output_text: "",
        provider: "openai",
        model: "gpt-4",
        tokens_in: 100,
        tokens_out: 0,
        duration_ms: 60000,
        status: "timeout" as const,
        error_message: "Execution timed out",
        timestamp: "2026-05-11T10:00:00Z",
      };

      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1, mockPipeline2],
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
        status: "success",
      } as any);

      vi.mocked(pipelineHooks.useAllPipelineExecutions).mockReturnValue({
        data: {
          items: [timeoutExecution],
          total: 1,
        },
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <PipelinesContent />
        </QueryClientProvider>,
      );

      const grid = screen.getByTestId("pipelines-grid");
      const cards = grid.querySelectorAll("[data-testid^='pipeline-card-']");
      expect(cards.length).toBe(2);
      expect(cards[0]).toHaveAttribute("data-testid", "pipeline-card-pipeline-2");
    });
  });

  describe("running state with pulse dot", () => {
    it("displays idle status when pipeline is not executing and has no executions", () => {
      vi.mocked(pipelineHooks.usePipelines).mockReturnValue({
        data: [mockPipeline1],
        isLoading: false,
        error: null,
        refetch: vi.fn(),
        isFetching: false,
        status: "success",
      } as any);

      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      vi.mocked(pipelineHooks.useAllPipelineExecutions).mockReturnValue({
        data: { items: [], total: 0 },
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      render(
        <QueryClientProvider client={queryClient}>
          <PipelinesContent />
        </QueryClientProvider>,
      );

      const card = screen.getByTestId("pipeline-card-pipeline-1");
      const status = card.querySelector(".pipeline-card__status");
      expect(status).toHaveTextContent("idle");
      expect(status).toHaveAttribute("data-status", "idle");
    });
  });
});
