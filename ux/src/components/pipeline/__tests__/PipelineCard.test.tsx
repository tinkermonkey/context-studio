import { render, screen } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import { PipelineCard } from "../PipelineCard";
import * as pipelineHooks from "@/api/hooks/pipeline";
import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("@/api/hooks/pipeline");

describe("PipelineCard", () => {
  const mockPipeline = {
    id: "pipeline-1",
    pipeline: "test-pipeline",
    title: "Test Pipeline",
    provider: "openai",
    model: "gpt-4",
    config: {},
    system_prompt: "You are helpful",
    user_prompt: "Process: {text}",
    version: 1,
    enabled: true,
    created_at: "2026-05-11T00:00:00Z",
    last_updated: "2026-05-11T00:00:00Z",
  };

  const mockExecution = {
    id: "exec-1",
    pipeline_config_id: "pipeline-1",
    output_text: "Result",
    provider: "openai",
    model: "gpt-4",
    tokens_in: 100,
    tokens_out: 50,
    duration_ms: 2000,
    status: "success" as const,
    error_message: null,
    timestamp: "2026-05-11T00:05:00Z",
  };

  beforeEach(() => {
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [mockExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);
  });

  it("renders pipeline title", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>
    );
    expect(screen.getByText("Test Pipeline")).toBeInTheDocument();
  });

  it("renders provider and model", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>
    );
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
  });

  it("renders success status chip", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>
    );
    const chip = screen.getByTestId("pipeline-status-chip");
    expect(chip).toHaveTextContent("success");
  });

  it("renders footer stats with last run time", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>
    );
    expect(screen.getByText(/ago/)).toBeInTheDocument();
    expect(screen.getByText(/tokens/)).toBeInTheDocument();
  });

  it("renders 'No runs yet' when no executions", () => {
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>
    );
    expect(screen.getByText("No runs yet")).toBeInTheDocument();
  });

  it("renders failed status for error executions", () => {
    const failedExecution = { ...mockExecution, status: "error" as const };
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [failedExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>
    );
    const chip = screen.getByTestId("pipeline-status-chip");
    expect(chip).toHaveTextContent("failed");
  });

  it("has correct data-testid attributes", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>
    );
    expect(screen.getByTestId("pipeline-card-pipeline-1")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline-status-chip")).toBeInTheDocument();
  });
});
