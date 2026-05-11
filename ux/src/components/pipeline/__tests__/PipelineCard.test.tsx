import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import { PipelineCard } from "../PipelineCard";
import * as pipelineHooks from "@/api/hooks/pipeline";
import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("@/api/hooks/pipeline");
vi.mock("@/stores/executionStore", () => ({
  useExecutionStore: vi.fn(() => ({
    inFlightPipelineIds: new Set(),
    startExecution: vi.fn(),
    endExecution: vi.fn(),
    hasRunningExecutions: vi.fn(() => false),
  })),
}));
const mockToast = vi.fn();
vi.mock("@/components/ui/Toast", () => ({
  useToasts: () => ({
    toast: mockToast,
  }),
}));

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
    vi.clearAllMocks();

    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [mockExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue(mockExecution),
      isPending: false,
      status: "idle",
    } as any);
  });

  it("renders pipeline title", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("Test Pipeline")).toBeInTheDocument();
  });

  it("renders provider and model", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
  });

  it("renders success status chip with emerald class", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );
    const chip = screen.getByTestId("pipeline-status-chip");
    expect(chip).toHaveTextContent("success");
    expect(chip).toHaveClass("chip", "emerald");
  });

  it("renders footer stats with last run time", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
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
      </QueryClientProvider>,
    );
    expect(screen.getByText("No runs yet")).toBeInTheDocument();
  });

  it("renders failed status with rose class for error executions", () => {
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
      </QueryClientProvider>,
    );
    const chip = screen.getByTestId("pipeline-status-chip");
    expect(chip).toHaveTextContent("failed");
    expect(chip).toHaveClass("chip", "rose");
  });

  it("renders idle status with gray class when no executions", () => {
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
      </QueryClientProvider>,
    );
    const chip = screen.getByTestId("pipeline-status-chip");
    expect(chip).toHaveTextContent("idle");
    expect(chip).toHaveClass("chip", "gray");
  });

  it("renders disabled status with gray class when pipeline is disabled", () => {
    const disabledPipeline = { ...mockPipeline, enabled: false };
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={disabledPipeline} />
      </QueryClientProvider>,
    );
    const chip = screen.getByTestId("pipeline-status-chip");
    expect(chip).toHaveTextContent("disabled");
    expect(chip).toHaveClass("chip", "gray");
  });

  it("has correct data-testid attributes", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );
    expect(screen.getByTestId("pipeline-card-pipeline-1")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline-status-chip")).toBeInTheDocument();
  });

  it("has ARIA status role and label on chip", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );
    const chip = screen.getByTestId("pipeline-status-chip");
    expect(chip).toHaveAttribute("role", "status");
    expect(chip).toHaveAttribute("aria-label", "Pipeline status: success");
  });

  it("renders run button with correct testid and aria-label", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );
    const runButton = screen.getByTestId("run-pipeline-btn");
    expect(runButton).toBeInTheDocument();
    expect(runButton).toHaveAttribute("aria-label", "Run pipeline");
    expect(runButton).toHaveAttribute("title", "Run pipeline");
  });

  it("calls mutation when run button is clicked", async () => {
    const user = userEvent.setup();
    const mockMutate = vi.fn().mockResolvedValue(mockExecution);
    vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
      mutateAsync: mockMutate,
      isPending: false,
      status: "idle",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );

    const runButton = screen.getByTestId("run-pipeline-btn");
    await user.click(runButton);

    expect(mockMutate).toHaveBeenCalledWith({
      id: mockPipeline.id,
      inputText: "",
    });
  });

  it("shows spinner when mutation is pending", () => {
    vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: true,
      status: "pending",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );

    const runButton = screen.getByTestId("run-pipeline-btn");
    const spinner = runButton.querySelector("svg");
    expect(spinner).toHaveClass("spin");
  });

  it("disables run button when mutation is pending", () => {
    vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: true,
      status: "pending",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );

    const runButton = screen.getByTestId("run-pipeline-btn") as HTMLButtonElement;
    expect(runButton.disabled).toBe(true);
  });

  it("calls mutation with success status execution", async () => {
    const user = userEvent.setup();
    const mockMutate = vi.fn().mockResolvedValue({
      ...mockExecution,
      status: "success",
    });
    vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
      mutateAsync: mockMutate,
      isPending: false,
      status: "idle",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );

    const runButton = screen.getByTestId("run-pipeline-btn");
    await user.click(runButton);

    expect(mockMutate).toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith("success", "Pipeline 'Test Pipeline' completed");
  });

  it("calls mutation with error status execution", async () => {
    const user = userEvent.setup();
    const mockMutate = vi.fn().mockResolvedValue({
      ...mockExecution,
      status: "error",
    });
    vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
      mutateAsync: mockMutate,
      isPending: false,
      status: "idle",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );

    const runButton = screen.getByTestId("run-pipeline-btn");
    await user.click(runButton);

    expect(mockMutate).toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith("error", "Pipeline 'Test Pipeline' failed");
  });

  it("calls toast on mutation failure", async () => {
    const user = userEvent.setup();
    const mockMutate = vi.fn().mockRejectedValue(new Error("Execution failed"));
    vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
      mutateAsync: mockMutate,
      isPending: false,
      status: "idle",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={mockPipeline} />
      </QueryClientProvider>,
    );

    const runButton = screen.getByTestId("run-pipeline-btn");
    await user.click(runButton);

    expect(mockMutate).toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith("error", "Execution failed");
  });
});
