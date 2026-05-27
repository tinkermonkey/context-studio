import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import { PipelineCard } from "../PipelineCard";
import * as pipelineHooks from "@/api/hooks/pipeline";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { useExecutionStore } from "@/stores/executionStore";

vi.mock("@/api/hooks/pipeline");
vi.mock("@/stores/executionStore", () => ({
  useExecutionStore: vi.fn(),
}));

function setExecutionStore(inFlight: string[] = []) {
  vi.mocked(useExecutionStore).mockImplementation((selector: any) => {
    const state = {
      inFlightPipelineIds: new Set(inFlight),
      startExecution: vi.fn(),
      endExecution: vi.fn(),
      hasRunningExecutions: vi.fn(() => inFlight.length > 0),
    };
    return selector ? selector(state) : state;
  });
}
const mockToast = vi.fn();
vi.mock("@/components/ui/Toast", () => ({
  useToasts: () => ({
    toast: mockToast,
  }),
}));

function getStatus() {
  return document.querySelector(".pipeline-card__status") as HTMLElement | null;
}

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
    setExecutionStore([]);

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

  function renderCard(pipeline = mockPipeline) {
    return render(
      <QueryClientProvider client={queryClient}>
        <PipelineCard pipeline={pipeline} />
      </QueryClientProvider>,
    );
  }

  it("passes the pipeline title as the card name", () => {
    renderCard();
    expect(screen.getByText("Test Pipeline")).toBeInTheDocument();
  });

  it("renders the combined provider · model description", () => {
    renderCard();
    expect(screen.getByText("openai · gpt-4")).toBeInTheDocument();
  });

  it("passes the card data-testid through to the Heimdall card", () => {
    renderCard();
    expect(screen.getByTestId("pipeline-card-pipeline-1")).toBeInTheDocument();
  });

  describe("status mapping", () => {
    it("maps a successful last execution to 'success'", () => {
      renderCard();
      const status = getStatus();
      expect(status).toHaveTextContent("success");
      expect(status).toHaveAttribute("data-status", "success");
    });

    it("maps an error execution to 'failed'", () => {
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [{ ...mockExecution, status: "error" as const }],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);
      renderCard();
      const status = getStatus();
      expect(status).toHaveTextContent("failed");
      expect(status).toHaveAttribute("data-status", "failed");
    });

    it("maps a timeout execution to 'failed'", () => {
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [{ ...mockExecution, status: "timeout" as const }],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);
      renderCard();
      expect(getStatus()).toHaveTextContent("failed");
    });

    it("maps no executions to 'idle'", () => {
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);
      renderCard();
      expect(getStatus()).toHaveTextContent("idle");
    });

    it("maps a disabled pipeline to 'idle' (not 'disabled')", () => {
      renderCard({ ...mockPipeline, enabled: false });
      const status = getStatus();
      expect(status).toHaveTextContent("idle");
      expect(status).toHaveAttribute("data-status", "idle");
    });

    it("maps an in-flight pipeline to 'running'", () => {
      setExecutionStore(["pipeline-1"]);
      renderCard();
      expect(getStatus()).toHaveTextContent("running");
    });
  });

  describe("footer", () => {
    it("shows relative time and token counts when an execution exists", () => {
      renderCard();
      const footer = document.querySelector(".pipeline-card__foot") as HTMLElement;
      expect(footer).toHaveTextContent(/ago/);
      expect(footer).toHaveTextContent(/tokens/);
    });

    it("shows 'No runs yet' when there are no executions", () => {
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);
      renderCard();
      expect(screen.getByText("No runs yet")).toBeInTheDocument();
    });
  });

  describe("run button", () => {
    it("calls executeMutation.mutateAsync with the pipeline id and empty input", async () => {
      const user = userEvent.setup();
      const mockMutate = vi.fn().mockResolvedValue(mockExecution);
      vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
        mutateAsync: mockMutate,
        isPending: false,
        status: "idle",
      } as any);

      renderCard();
      await user.click(screen.getByTestId("pipeline-run-btn"));

      expect(mockMutate).toHaveBeenCalledWith({ id: "pipeline-1", inputText: "" });
    });

    it("toasts success when the run completes with success status", async () => {
      const user = userEvent.setup();
      const mockMutate = vi.fn().mockResolvedValue({ ...mockExecution, status: "success" });
      vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
        mutateAsync: mockMutate,
        isPending: false,
        status: "idle",
      } as any);

      renderCard();
      await user.click(screen.getByTestId("pipeline-run-btn"));

      expect(mockToast).toHaveBeenCalledWith("success", "Pipeline 'Test Pipeline' completed");
    });

    it("toasts an error when the run completes with error status", async () => {
      const user = userEvent.setup();
      const mockMutate = vi.fn().mockResolvedValue({ ...mockExecution, status: "error" });
      vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
        mutateAsync: mockMutate,
        isPending: false,
        status: "idle",
      } as any);

      renderCard();
      await user.click(screen.getByTestId("pipeline-run-btn"));

      expect(mockToast).toHaveBeenCalledWith("error", "Pipeline 'Test Pipeline' failed");
    });

    it("toasts the error message when the mutation rejects", async () => {
      const user = userEvent.setup();
      const mockMutate = vi.fn().mockRejectedValue(new Error("Execution failed"));
      vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
        mutateAsync: mockMutate,
        isPending: false,
        status: "idle",
      } as any);

      renderCard();
      await user.click(screen.getByTestId("pipeline-run-btn"));

      expect(mockToast).toHaveBeenCalledWith("error", "Execution failed");
    });

    it("does not render the run button when the pipeline is running", () => {
      setExecutionStore(["pipeline-1"]);
      renderCard();
      expect(screen.queryByTestId("pipeline-run-btn")).not.toBeInTheDocument();
    });
  });
});
