import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LlmPipelineRun } from "@/components/llm_pipelines/LlmPipelineRun";
import { vi, describe, it, expect, beforeEach } from "vitest";

// Mock the API hooks
vi.mock("@/api/hooks/pipelineFlavors", () => ({
  usePipelineFlavors: vi.fn(),
  usePipelineFlavor: vi.fn(),
}));

vi.mock("@/api/hooks/llm", () => ({
  useSuggestTermDefinitionMutation: vi.fn(),
  useSuggestDomainDefinitionMutation: vi.fn(),
  useSuggestLayerDefinitionMutation: vi.fn(),
}));

import {
  usePipelineFlavors,
  usePipelineFlavor,
} from "@/api/hooks/pipelineFlavors";
import {
  useSuggestTermDefinitionMutation,
} from "@/api/hooks/llm";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockUsePipelineFlavors = usePipelineFlavors as any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockUsePipelineFlavor = usePipelineFlavor as any;
 
const mockUseSuggestTermDefinitionMutation =
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  useSuggestTermDefinitionMutation as any;
 
 

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("LlmPipelineRun", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock for usePipelineFlavor (not used in most tests)
    mockUsePipelineFlavor.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
    });
  });

  it("renders loading state when fetching flavors", () => {
    mockUsePipelineFlavors.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    render(
      <LlmPipelineRun
        pipelineType="suggest_term_definition"
        context={{ term: "test" }}
      />,
      { wrapper: createWrapper() },
    );

    expect(screen.getByText(/Loading pipeline flavors/)).toBeInTheDocument();
  });

  it("renders error state when flavor loading fails", () => {
    mockUsePipelineFlavors.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("Failed to load flavors"),
    });

    render(
      <LlmPipelineRun
        pipelineType="suggest_term_definition"
        context={{ term: "test" }}
      />,
      { wrapper: createWrapper() },
    );

    expect(
      screen.getByText(/Failed to Load Pipeline Flavors/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Failed to load flavors/)).toBeInTheDocument();
  });

  it("renders no flavors message when no enabled flavors exist", () => {
    mockUsePipelineFlavors.mockReturnValue({
      data: {
        flavors: [{ id: "1", title: "Disabled Flavor", enabled: false }],
        total_count: 1,
      },
      isLoading: false,
      error: null,
    });

    render(
      <LlmPipelineRun
        pipelineType="suggest_term_definition"
        context={{ term: "test" }}
      />,
      { wrapper: createWrapper() },
    );

    expect(screen.getByText(/No Enabled Flavors/)).toBeInTheDocument();
    expect(
      screen.getByText(
        /No enabled flavors found for pipeline type: suggest_term_definition/,
      ),
    ).toBeInTheDocument();
  });

  it("renders pipeline interface with enabled flavors", () => {
    mockUsePipelineFlavors.mockReturnValue({
      data: {
        flavors: [
          { id: "1", title: "GPT-4 Flavor", enabled: true },
          { id: "2", title: "Claude Flavor", enabled: true },
        ],
        total_count: 2,
      },
      isLoading: false,
      error: null,
    });

    mockUseSuggestTermDefinitionMutation.mockReturnValue({
      mutateAsync: vi.fn(),
    });

    render(
      <LlmPipelineRun
        pipelineType="suggest_term_definition"
        context={{ term: "artificial intelligence" }}
      />,
      { wrapper: createWrapper() },
    );

    expect(screen.getByText(/Suggest Term Definition/)).toBeInTheDocument();
    expect(screen.getByText(/2 enabled flavors/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Execute Pipeline/ }),
    ).toBeInTheDocument();
  });

  it("executes pipeline when button is clicked", async () => {
    const mockMutateAsync = vi.fn().mockResolvedValue({
      definition: "Test definition",
      reasoning: "Test reasoning",
    });

    mockUsePipelineFlavors.mockReturnValue({
      data: {
        flavors: [{ id: "1", title: "Test Flavor", enabled: true }],
        total_count: 1,
      },
      isLoading: false,
      error: null,
    });

    mockUseSuggestTermDefinitionMutation.mockReturnValue({
      mutateAsync: mockMutateAsync,
    });

    const onExecutionStart = vi.fn();
    const onExecutionComplete = vi.fn();

    render(
      <LlmPipelineRun
        pipelineType="suggest_term_definition"
        context={{ term: "test" }}
        onExecutionStart={onExecutionStart}
        onExecutionComplete={onExecutionComplete}
      />,
      { wrapper: createWrapper() },
    );

    const executeButton = screen.getByRole("button", {
      name: /Execute Pipeline/,
    });

    await userEvent.click(executeButton);

    await waitFor(() => {
      expect(onExecutionStart).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        pipeline_type: "suggest_term_definition",
        flavor_id: "1",
        context_data: { term: "test" },
      });
    });

    await waitFor(() => {
      expect(onExecutionComplete).toHaveBeenCalled();
    });
  });

  it("displays custom result template when provided", async () => {
    mockUsePipelineFlavors.mockReturnValue({
      data: {
        flavors: [{ id: "1", title: "Test Flavor", enabled: true }],
        total_count: 1,
      },
      isLoading: false,
      error: null,
    });

    mockUseSuggestTermDefinitionMutation.mockReturnValue({
      mutateAsync: vi.fn(),
    });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const customTemplate = (result: any) => (
      <div data-testid="custom-template">
        Custom: {result.flavorTitle} - {result.status}
      </div>
    );

    render(
      <LlmPipelineRun
        pipelineType="suggest_term_definition"
        context={{ term: "test" }}
        resultTemplate={customTemplate}
      />,
      { wrapper: createWrapper() },
    );

    const executeButton = screen.getByRole("button", {
      name: /Execute Pipeline/,
    });

    await userEvent.click(executeButton);

    // Should show custom template for running results (execution starts immediately)
    await waitFor(() => {
      expect(screen.getByTestId("custom-template")).toBeInTheDocument();
    });

    // The status might be "success" or "running" depending on timing
    expect(
      screen.getByText(/Custom: Test Flavor - (running|success)/),
    ).toBeInTheDocument();
  });
});
