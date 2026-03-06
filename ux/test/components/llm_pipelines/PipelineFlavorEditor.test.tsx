import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PipelineFlavorEditor } from "@/components/llm_pipelines/PipelineFlavorEditor";

// Mock the pipeline flavors hooks - use simpler approach
vi.mock("@/api/hooks/pipelineFlavors");

// Mock the model capabilities hooks
vi.mock("@/api/hooks/modelCapabilities");

// Mock data
const mockExistingFlavor = {
  id: "existing-flavor-1",
  pipeline: "suggest_term_definition" as const,
  title: "Default Term Flavor",
  llm_provider: "openai",
  llm_model: "gpt-4o",
  system_prompt:
    "You are an expert at creating precise, informative definitions for technical terms.",
  user_prompt:
    'Create a definition for the term "{title}" in the context of {domain_context}.',
  llm_config: {
    temperature: 0.5,
    max_tokens: 500,
    top_p: 0.9,
    frequency_penalty: 0.1,
    presence_penalty: 0.2,
  },
  enabled: true,
  version: 1,
  created_at: "2025-09-01T10:00:00Z",
  updated_at: "2025-09-02T10:00:00Z",
};

describe("PipelineFlavorEditor - Default Population", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();

    // Create a fresh QueryClient for each test
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
        mutations: {
          retry: false,
        },
      },
    });
  });

  afterEach(() => {
    queryClient.clear();
  });

  it("populates default values from existing flavor when creating new", async () => {
    const {
      usePipelineFlavors,
      useCreatePipelineFlavor,
      useUpdatePipelineFlavor,
    } = await import("@/api/hooks/pipelineFlavors");

    const { useTypedModelCapabilities, useValidateLLMConfig } = await import(
      "@/api/hooks/modelCapabilities"
    );

    vi.mocked(usePipelineFlavors).mockReturnValue({
      data: {
        flavors: [mockExistingFlavor],
        total_count: 1,
      },
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useCreatePipelineFlavor).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useUpdatePipelineFlavor).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useTypedModelCapabilities).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useValidateLLMConfig).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const mockOnClose = vi.fn();

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineFlavorEditor
          pipeline="suggest_term_definition"
          flavor={null}
          onClose={mockOnClose}
        />
      </QueryClientProvider>,
    );

    // Should show the "Defaults populated" alert
    await waitFor(
      () => {
        expect(screen.getByText(/Defaults populated/)).toBeInTheDocument();
      },
      { timeout: 1000 },
    );
  });

  it("does not fetch defaults when editing existing flavor", async () => {
    const {
      usePipelineFlavors,
      useCreatePipelineFlavor,
      useUpdatePipelineFlavor,
    } = await import("@/api/hooks/pipelineFlavors");

    const { useTypedModelCapabilities, useValidateLLMConfig } = await import(
      "@/api/hooks/modelCapabilities"
    );

    vi.mocked(usePipelineFlavors).mockReturnValue({
      data: {
        flavors: [mockExistingFlavor],
        total_count: 1,
      },
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useCreatePipelineFlavor).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useUpdatePipelineFlavor).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useTypedModelCapabilities).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useValidateLLMConfig).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const mockOnClose = vi.fn();

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineFlavorEditor
          pipeline="suggest_term_definition"
          flavor={mockExistingFlavor}
          onClose={mockOnClose}
        />
      </QueryClientProvider>,
    );

    // Should not show the "Defaults populated" alert
    expect(screen.queryByText(/Defaults populated/)).not.toBeInTheDocument();
  });

  it("shows loading state when fetching defaults", async () => {
    const {
      usePipelineFlavors,
      useCreatePipelineFlavor,
      useUpdatePipelineFlavor,
    } = await import("@/api/hooks/pipelineFlavors");

    const { useTypedModelCapabilities, useValidateLLMConfig } = await import(
      "@/api/hooks/modelCapabilities"
    );

    vi.mocked(usePipelineFlavors).mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useCreatePipelineFlavor).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useUpdatePipelineFlavor).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useTypedModelCapabilities).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useValidateLLMConfig).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const mockOnClose = vi.fn();

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineFlavorEditor
          pipeline="suggest_term_definition"
          flavor={null}
          onClose={mockOnClose}
        />
      </QueryClientProvider>,
    );

    // Should show loading message
    expect(screen.getByText(/Loading default values/)).toBeInTheDocument();
  });

  it("handles case when no existing flavors exist", async () => {
    const {
      usePipelineFlavors,
      useCreatePipelineFlavor,
      useUpdatePipelineFlavor,
    } = await import("@/api/hooks/pipelineFlavors");

    const { useTypedModelCapabilities, useValidateLLMConfig } = await import(
      "@/api/hooks/modelCapabilities"
    );

    vi.mocked(usePipelineFlavors).mockReturnValue({
      data: {
        flavors: [],
        total_count: 0,
      },
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useCreatePipelineFlavor).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useUpdatePipelineFlavor).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useTypedModelCapabilities).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    vi.mocked(useValidateLLMConfig).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    const mockOnClose = vi.fn();

    render(
      <QueryClientProvider client={queryClient}>
        <PipelineFlavorEditor
          pipeline="suggest_term_definition"
          flavor={null}
          onClose={mockOnClose}
        />
      </QueryClientProvider>,
    );

    // Should not show defaults populated alert
    expect(screen.queryByText(/Defaults populated/)).not.toBeInTheDocument();
  });
});
