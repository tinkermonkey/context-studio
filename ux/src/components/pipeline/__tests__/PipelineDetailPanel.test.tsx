import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import { PipelineDetailPanel } from "../PipelineDetailPanel";
import * as pipelineHooks from "@/api/hooks/pipeline";
import { useAutosave } from "@/hooks/useAutosave";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

vi.mock("@/api/hooks/pipeline");
vi.mock("@/hooks/useAutosave");
vi.mock("@/stores/executionStore", () => ({
  useExecutionStore: vi.fn(() => ({
    inFlightPipelineIds: new Set(),
    startExecution: vi.fn(),
    endExecution: vi.fn(),
    hasRunningExecutions: vi.fn(() => false),
  })),
}));
vi.mock("@/components/ui/Toast", () => ({
  useToasts: () => ({
    toast: vi.fn(),
  }),
}));

describe("PipelineDetailPanel", () => {
  const mockPipeline = {
    id: "pipeline-1",
    pipeline: "test-pipeline",
    title: "Test Pipeline",
    provider: "openai",
    model: "gpt-4",
    config: { key: "value" },
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

  const mockFailedExecution = {
    id: "exec-2",
    pipeline_config_id: "pipeline-1",
    output_text: null,
    provider: "openai",
    model: "gpt-4",
    tokens_in: 100,
    tokens_out: 0,
    duration_ms: 1000,
    status: "error" as const,
    error_message: "Test error message",
    timestamp: "2026-05-11T00:10:00Z",
  };

  beforeEach(() => {
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [mockExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    vi.mocked(pipelineHooks.useUpdatePipeline).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({}),
      isPending: false,
      status: "idle",
    } as any);

    vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({}),
      isPending: false,
      status: "idle",
    } as any);

    vi.mocked(useAutosave).mockReturnValue({
      status: "idle",
      lastSavedAt: null,
      lastError: null,
      save: vi.fn(),
      isLoading: false,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders configuration in code block with correct CSS class", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const preElement = screen.getByTestId("pipeline-config-pre");
    expect(preElement).toHaveClass("pipeline-code-block");
    expect(preElement).toHaveTextContent('"key": "value"');
  });

  it("renders edit button and switches to edit mode", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const editButton = screen.getByTestId("pipeline-edit-config-button");
    expect(editButton).toBeInTheDocument();

    await user.click(editButton);

    const textarea = screen.getByTestId("pipeline-config-textarea");
    expect(textarea).toBeInTheDocument();
    expect(screen.queryByTestId("pipeline-config-pre")).not.toBeInTheDocument();
  });

  it("renders textarea with correct styling in edit mode", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const editButton = screen.getByTestId("pipeline-edit-config-button");
    await user.click(editButton);

    const textarea = screen.getByTestId("pipeline-config-textarea");
    expect(textarea).toHaveAttribute("rows", "10");
  });

  it("shows save and cancel buttons in edit mode", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const editButton = screen.getByTestId("pipeline-edit-config-button");
    await user.click(editButton);

    expect(screen.getByTestId("pipeline-save-config-button")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline-revert-config-button")).toBeInTheDocument();
  });

  it("reverts changes when cancel button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const editButton = screen.getByTestId("pipeline-edit-config-button");
    await user.click(editButton);

    const textarea = screen.getByTestId("pipeline-config-textarea") as HTMLTextAreaElement;
    await user.clear(textarea);
    await user.type(textarea, "changed config");

    const cancelButton = screen.getByTestId("pipeline-revert-config-button");
    await user.click(cancelButton);

    const preElement = screen.getByTestId("pipeline-config-pre");
    expect(preElement).toBeInTheDocument();
    expect(preElement).not.toHaveTextContent("changed config");
  });

  it("renders runs table with correct testid", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    expect(screen.getByTestId("pipeline-runs-table")).toBeInTheDocument();
  });

  it("renders 'no runs' message when no executions", () => {
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    expect(screen.getByTestId("pipeline-no-runs")).toBeInTheDocument();
    expect(screen.getByTestId("pipeline-no-runs")).toHaveClass("pipeline-empty-state");
  });

  it("renders view log button for failed executions", () => {
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [mockFailedExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    expect(screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`)).toBeInTheDocument();
  });

  it("shows error log panel when view log is clicked", async () => {
    const user = userEvent.setup();
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [mockFailedExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const viewLogButton = screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`);
    await user.click(viewLogButton);

    const errorLog = screen.getByTestId("pipeline-error-log");
    expect(errorLog).toBeInTheDocument();
    expect(errorLog).toHaveClass("pipeline-error-log");
    expect(errorLog).toHaveTextContent("Test error message");
  });

  it("renders error message in correct CSS class", async () => {
    const user = userEvent.setup();
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [mockFailedExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const viewLogButton = screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`);
    await user.click(viewLogButton);

    const errorMessage = screen.getByText("Test error message");
    expect(errorMessage).toHaveClass("pipeline-error-message");
  });

  it("copy error button has correct aria-label", async () => {
    const user = userEvent.setup();
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [mockFailedExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const viewLogButton = screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`);
    await user.click(viewLogButton);

    const copyButton = screen.getByTestId("pipeline-copy-error-button");
    expect(copyButton).toHaveAttribute("aria-label", "Copy error to clipboard");
  });

  it("view log button has aria-expanded attribute", async () => {
    const user = userEvent.setup();
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [mockFailedExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const viewLogButton = screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`);
    expect(viewLogButton).toHaveAttribute("aria-expanded", "false");

    await user.click(viewLogButton);

    expect(viewLogButton).toHaveAttribute("aria-expanded", "true");
  });

  it("shows error details for correct execution when expanding log", async () => {
    const user = userEvent.setup();
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [mockFailedExecution, mockExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const viewLogButton = screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`);
    await user.click(viewLogButton);

    expect(screen.getByText("Test error message")).toBeInTheDocument();
  });

  it("renders success status chips with emerald class", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const chip = screen.getByText("success");
    expect(chip.closest("[class*='chip']")).toHaveClass("emerald");
  });

  it("renders error status chips with rose class", () => {
    vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
      data: [mockFailedExecution],
      isLoading: false,
      error: null,
      isFetching: false,
      status: "success",
    } as any);

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const chip = screen.getByText("error");
    expect(chip.closest("[class*='chip']")).toHaveClass("rose");
  });

  it("disables save button when no changes are made", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const editButton = screen.getByTestId("pipeline-edit-config-button");
    await user.click(editButton);

    const saveButton = screen.getByTestId("pipeline-save-config-button") as HTMLButtonElement;
    expect(saveButton.disabled).toBe(true);
  });

  it("enables save button when config is changed", async () => {
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={mockPipeline} onClose={vi.fn()} />
      </QueryClientProvider>,
    );

    const editButton = screen.getByTestId("pipeline-edit-config-button");
    await user.click(editButton);

    const textarea = screen.getByTestId("pipeline-config-textarea");
    await user.clear(textarea);
    await user.type(textarea, "new config");

    const saveButton = screen.getByTestId("pipeline-save-config-button") as HTMLButtonElement;
    expect(saveButton.disabled).toBe(false);
  });
});
