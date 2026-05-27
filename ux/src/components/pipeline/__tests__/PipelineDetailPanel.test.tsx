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
const mockToast = vi.fn();
vi.mock("@/components/ui/Toast", () => ({
  useToasts: () => ({
    toast: mockToast,
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

  function renderPanel(pipeline = mockPipeline) {
    return render(
      <QueryClientProvider client={queryClient}>
        <PipelineDetailPanel pipeline={pipeline} />
      </QueryClientProvider>,
    );
  }

  async function openTab(user: ReturnType<typeof userEvent.setup>, label: RegExp) {
    await user.click(screen.getByRole("tab", { name: label }));
  }

  describe("tabs", () => {
    it("defaults to the Prompts tab showing both prompt editors", () => {
      renderPanel();
      expect(screen.getByTestId("pipeline-system-prompt")).toBeInTheDocument();
      expect(screen.getByTestId("pipeline-user-prompt")).toBeInTheDocument();
    });

    it("renders all four tabs", () => {
      renderPanel();
      expect(screen.getByRole("tab", { name: /prompts/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /config/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /test/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /history/i })).toBeInTheDocument();
    });
  });

  describe("config tab", () => {
    it("renders the KeyValueEditor seeded from the pipeline config", async () => {
      const user = userEvent.setup();
      renderPanel();
      await openTab(user, /config/i);

      // KeyValueEditor root carries the testid passed by the component
      expect(screen.getByTestId("pipeline-config-editor")).toBeInTheDocument();

      // pipeline.config = { key: "value" } seeds a single row with id "0"
      expect(screen.getByTestId("key-input-0")).toHaveValue("key");
      expect(screen.getByTestId("value-input-0")).toHaveValue("value");
    });

    it("reflects pipeline.enabled in the enabled toggle", async () => {
      const user = userEvent.setup();
      renderPanel();
      await openTab(user, /config/i);

      const toggle = screen.getByTestId("pipeline-enabled-toggle") as HTMLInputElement;
      expect(toggle.checked).toBe(true);
    });

    it("disables the save button initially when config is not dirty", async () => {
      const user = userEvent.setup();
      renderPanel();
      await openTab(user, /config/i);

      const saveButton = screen.getByTestId("pipeline-save-config-button") as HTMLButtonElement;
      expect(saveButton.disabled).toBe(true);
    });

    it("enables the save button after editing a config value", async () => {
      const user = userEvent.setup();
      renderPanel();
      await openTab(user, /config/i);

      const saveButton = screen.getByTestId("pipeline-save-config-button") as HTMLButtonElement;
      expect(saveButton.disabled).toBe(true);

      await user.clear(screen.getByTestId("value-input-0"));
      await user.type(screen.getByTestId("value-input-0"), "updated");

      expect(screen.getByTestId("value-input-0")).toHaveValue("updated");
      expect(saveButton.disabled).toBe(false);
    });

    it("enables the save button after toggling enabled", async () => {
      const user = userEvent.setup();
      renderPanel();
      await openTab(user, /config/i);

      const saveButton = screen.getByTestId("pipeline-save-config-button") as HTMLButtonElement;
      expect(saveButton.disabled).toBe(true);

      await user.click(screen.getByTestId("pipeline-enabled-toggle"));

      const toggle = screen.getByTestId("pipeline-enabled-toggle") as HTMLInputElement;
      expect(toggle.checked).toBe(false);
      expect(saveButton.disabled).toBe(false);
    });

    it("saves the updated config via the update mutation with the edited payload", async () => {
      const user = userEvent.setup();
      const mockMutate = vi.fn().mockResolvedValue({});
      vi.mocked(pipelineHooks.useUpdatePipeline).mockReturnValue({
        mutateAsync: mockMutate,
        isPending: false,
        status: "idle",
      } as any);

      renderPanel();
      await openTab(user, /config/i);

      await user.clear(screen.getByTestId("value-input-0"));
      await user.type(screen.getByTestId("value-input-0"), "updated");
      await user.click(screen.getByTestId("pipeline-save-config-button"));

      expect(mockMutate).toHaveBeenCalledWith({
        id: mockPipeline.id,
        data: {
          provider: mockPipeline.provider,
          model: mockPipeline.model,
          enabled: mockPipeline.enabled,
          config: { key: "updated" },
        },
      });
      expect(mockToast).toHaveBeenCalledWith("success", "Configuration saved");
    });

    it("saves the new enabled flag via the update mutation", async () => {
      const user = userEvent.setup();
      const mockMutate = vi.fn().mockResolvedValue({});
      vi.mocked(pipelineHooks.useUpdatePipeline).mockReturnValue({
        mutateAsync: mockMutate,
        isPending: false,
        status: "idle",
      } as any);

      renderPanel();
      await openTab(user, /config/i);

      // TriState cycles from its current `true` state on click; the save
      // payload carries whatever new enabled value the toggle reports.
      await user.click(screen.getByTestId("pipeline-enabled-toggle"));
      await user.click(screen.getByTestId("pipeline-save-config-button"));

      expect(mockMutate).toHaveBeenCalledTimes(1);
      const payload = mockMutate.mock.calls[0][0];
      expect(payload.id).toBe(mockPipeline.id);
      expect(payload.data.provider).toBe(mockPipeline.provider);
      expect(payload.data.model).toBe(mockPipeline.model);
      expect(payload.data.config).toEqual({ key: "value" });
      // enabled changed away from the pipeline's original `true`
      expect(payload.data.enabled).not.toBe(true);
    });

    it("toasts an error when saving config fails", async () => {
      const user = userEvent.setup();
      const mockMutate = vi.fn().mockRejectedValue(new Error("Save boom"));
      vi.mocked(pipelineHooks.useUpdatePipeline).mockReturnValue({
        mutateAsync: mockMutate,
        isPending: false,
        status: "idle",
      } as any);

      renderPanel();
      await openTab(user, /config/i);

      await user.clear(screen.getByTestId("value-input-0"));
      await user.type(screen.getByTestId("value-input-0"), "updated");
      await user.click(screen.getByTestId("pipeline-save-config-button"));

      expect(mockMutate).toHaveBeenCalled();
      expect(mockToast).toHaveBeenCalledWith("error", "Save boom");
    });
  });

  describe("history tab", () => {
    it("renders the runs table", async () => {
      const user = userEvent.setup();
      renderPanel();
      await openTab(user, /history/i);

      expect(screen.getByTestId("pipeline-runs-table")).toBeInTheDocument();
    });

    it("renders the 'no runs' empty state when there are no executions", async () => {
      const user = userEvent.setup();
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      renderPanel();
      await openTab(user, /history/i);

      const empty = screen.getByTestId("pipeline-no-runs");
      expect(empty).toBeInTheDocument();
      expect(empty).toHaveClass("pipeline-empty-state");
    });

    it("renders the view-log button only for executions with an error message", async () => {
      const user = userEvent.setup();
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [mockFailedExecution],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      renderPanel();
      await openTab(user, /history/i);

      expect(
        screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`),
      ).toBeInTheDocument();
    });

    it("expands the error log when the view-log button is clicked", async () => {
      const user = userEvent.setup();
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [mockFailedExecution],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      renderPanel();
      await openTab(user, /history/i);
      await user.click(screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`));

      const errorLog = screen.getByTestId("pipeline-error-log");
      expect(errorLog).toBeInTheDocument();
      expect(errorLog).toHaveClass("pipeline-error-log");
      expect(errorLog).toHaveTextContent("Test error message");
    });

    it("renders the error message in the pipeline-error-message element", async () => {
      const user = userEvent.setup();
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [mockFailedExecution],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      renderPanel();
      await openTab(user, /history/i);
      await user.click(screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`));

      expect(screen.getByText("Test error message")).toHaveClass("pipeline-error-message");
    });

    it("gives the copy-error button the correct aria-label", async () => {
      const user = userEvent.setup();
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [mockFailedExecution],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      renderPanel();
      await openTab(user, /history/i);
      await user.click(screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`));

      expect(screen.getByTestId("pipeline-copy-error-button")).toHaveAttribute(
        "aria-label",
        "Copy error to clipboard",
      );
    });

    it("toggles aria-expanded on the view-log button", async () => {
      const user = userEvent.setup();
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [mockFailedExecution],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      renderPanel();
      await openTab(user, /history/i);

      const viewLogButton = screen.getByTestId(`pipeline-view-log-${mockFailedExecution.id}`);
      expect(viewLogButton).toHaveAttribute("aria-expanded", "false");

      await user.click(viewLogButton);

      expect(viewLogButton).toHaveAttribute("aria-expanded", "true");
    });

    it("renders a success execution status chip with the emerald variant", async () => {
      const user = userEvent.setup();
      renderPanel();
      await openTab(user, /history/i);

      const chip = screen.getByText("success");
      expect(chip.closest("[class*='chip']")).toHaveClass("chip--emerald");
    });

    it("renders an error execution status chip with the rose variant", async () => {
      const user = userEvent.setup();
      vi.mocked(pipelineHooks.usePipelineExecutions).mockReturnValue({
        data: [mockFailedExecution],
        isLoading: false,
        error: null,
        isFetching: false,
        status: "success",
      } as any);

      renderPanel();
      await openTab(user, /history/i);

      const chip = screen.getByText("error");
      expect(chip.closest("[class*='chip']")).toHaveClass("chip--rose");
    });
  });

  describe("run button", () => {
    it("renders with the correct testid and aria-label", () => {
      renderPanel();

      const runButton = screen.getByTestId("run-pipeline-btn");
      expect(runButton).toBeInTheDocument();
      expect(runButton).toHaveAttribute("aria-label", "Run pipeline");
      expect(runButton).toHaveAttribute("title", "Run pipeline");
    });

    it("executes the pipeline with the current test input when clicked", async () => {
      const user = userEvent.setup();
      const mockMutate = vi.fn().mockResolvedValue(mockExecution);
      vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
        mutateAsync: mockMutate,
        isPending: false,
        status: "idle",
      } as any);

      renderPanel();
      await user.click(screen.getByTestId("run-pipeline-btn"));

      expect(mockMutate).toHaveBeenCalledWith({
        id: mockPipeline.id,
        inputText: "",
      });
    });

    it("shows a spinner on the run button while the mutation is pending", () => {
      vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: true,
        status: "pending",
      } as any);

      renderPanel();

      const runButton = screen.getByTestId("run-pipeline-btn");
      expect(runButton.querySelector("svg")).toHaveClass("spin");
    });

    it("disables the run button while the mutation is pending", () => {
      vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: true,
        status: "pending",
      } as any);

      renderPanel();

      const runButton = screen.getByTestId("run-pipeline-btn") as HTMLButtonElement;
      expect(runButton.disabled).toBe(true);
    });

    it("toasts when the executed pipeline returns a non-success status", async () => {
      const user = userEvent.setup();
      const mockMutate = vi.fn().mockResolvedValue({ ...mockExecution, status: "error" });
      vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
        mutateAsync: mockMutate,
        isPending: false,
        status: "idle",
      } as any);

      renderPanel();
      await user.click(screen.getByTestId("run-pipeline-btn"));

      expect(mockMutate).toHaveBeenCalled();
      expect(mockToast).toHaveBeenCalledWith("error", "Pipeline 'Test Pipeline' failed");
    });

    it("toasts the error message when the execution rejects", async () => {
      const user = userEvent.setup();
      const mockMutate = vi.fn().mockRejectedValue(new Error("Execution failed"));
      vi.mocked(pipelineHooks.useExecutePipeline).mockReturnValue({
        mutateAsync: mockMutate,
        isPending: false,
        status: "idle",
      } as any);

      renderPanel();
      await user.click(screen.getByTestId("run-pipeline-btn"));

      expect(mockToast).toHaveBeenCalledWith("error", "Execution failed");
    });
  });
});
