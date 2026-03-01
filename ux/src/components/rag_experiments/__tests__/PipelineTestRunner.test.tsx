/**
 * PipelineTestRunner Component Tests
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PipelineTestRunner } from "../PipelineTestRunner";
import { vi, describe, it, expect, beforeEach } from "vitest";
import * as ragExperimentsHooks from "@/api/hooks/ragExperiments";

// Mock the hooks module
vi.mock("@/api/hooks/ragExperiments");

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

describe("PipelineTestRunner", () => {
  beforeEach(() => {
    // Reset mocks before each test
    vi.clearAllMocks();

    // Default mock implementations
    vi.mocked(ragExperimentsHooks.useTestParagraphs).mockReturnValue({
      data: {
        paragraphs: [
          {
            id: "para-1",
            text: "Test paragraph 1",
            notes: "Notes 1",
            created_at: new Date().toISOString(),
            annotations: [],
          },
          {
            id: "para-2",
            text: "Test paragraph 2",
            notes: "Notes 2",
            created_at: new Date().toISOString(),
            annotations: [],
          },
        ],
        total_count: 2,
        limit: 100,
        offset: 0,
      },
      isLoading: false,
      error: null,
    } as any);

    vi.mocked(ragExperimentsHooks.useRunPipelineTest).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isSuccess: false,
      error: null,
      data: null,
    } as any);
  });

  it("renders pipeline selection", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    expect(screen.getByText(/Select Pipelines/i)).toBeInTheDocument();
    expect(screen.getByText(/StandardRAGPipeline/i)).toBeInTheDocument();
  });

  it("renders test paragraph selection", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    expect(screen.getByText(/Select Test Paragraphs/i)).toBeInTheDocument();
    expect(screen.getByText(/Test paragraph 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Test paragraph 2/i)).toBeInTheDocument();
  });

  it("allows selecting paragraphs", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    const checkbox = screen.getByLabelText(/Test paragraph 1/i, {
      selector: 'input[type="checkbox"]',
    });

    expect(checkbox).not.toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  it("shows select all button", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    expect(screen.getByText(/Select All/i)).toBeInTheDocument();
  });

  it("displays total test count", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    // Initially 0 (no paragraphs selected)
    expect(screen.getByText(/Total Tests: 0/i)).toBeInTheDocument();
  });

  it("shows options for trace and LLM layer", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    expect(screen.getByText(/Enable Detailed Tracing/i)).toBeInTheDocument();
    expect(screen.getByText(/Enable LLM Layer/i)).toBeInTheDocument();
  });

  it("disables run button when no paragraphs selected", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    const runButton = screen.getByText(/Run Tests/i);
    expect(runButton).toBeDisabled();
  });

  it("shows loading state when fetching paragraphs", () => {
    vi.mocked(ragExperimentsHooks.useTestParagraphs).mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
    } as any);

    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    expect(screen.getByText(/Loading test paragraphs/i)).toBeInTheDocument();
  });

  it("shows error state when fetching paragraphs fails", () => {
    vi.mocked(ragExperimentsHooks.useTestParagraphs).mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error("Failed to fetch paragraphs"),
    } as any);

    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    // Component should still render, showing no paragraphs available
    expect(screen.getByText(/Select Test Paragraphs/i)).toBeInTheDocument();
  });

  it("enables run button when paragraphs are selected", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    const checkbox = screen.getByLabelText(/Test paragraph 1/i, {
      selector: 'input[type="checkbox"]',
    });
    fireEvent.click(checkbox);

    const runButton = screen.getByText(/Run Tests/i);
    expect(runButton).not.toBeDisabled();
  });

  it("calculates total tests correctly", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    const checkbox1 = screen.getByLabelText(/Test paragraph 1/i, {
      selector: 'input[type="checkbox"]',
    });
    const checkbox2 = screen.getByLabelText(/Test paragraph 2/i, {
      selector: 'input[type="checkbox"]',
    });

    fireEvent.click(checkbox1);
    expect(screen.getByText(/Total Tests: 1/i)).toBeInTheDocument();

    fireEvent.click(checkbox2);
    expect(screen.getByText(/Total Tests: 2/i)).toBeInTheDocument();
  });

  it("shows progress during test execution", () => {
    vi.mocked(ragExperimentsHooks.useRunPipelineTest).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: true,
      isSuccess: false,
      error: null,
      data: null,
    } as any);

    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    expect(screen.getByText(/Running Tests/i)).toBeInTheDocument();
  });

  it("shows success message after test completion", () => {
    vi.mocked(ragExperimentsHooks.useRunPipelineTest).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isSuccess: true,
      error: null,
      data: {
        total_runs: 2,
        successful_runs: 2,
        failed_runs: 0,
        results: [],
      },
    } as any);

    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    expect(screen.getByText(/Tests Completed/i)).toBeInTheDocument();
    expect(screen.getByText(/Successful: 2/i)).toBeInTheDocument();
  });

  it("shows error message on test failure", () => {
    vi.mocked(ragExperimentsHooks.useRunPipelineTest).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isSuccess: false,
      error: new Error("Test execution failed"),
      data: null,
    } as any);

    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    expect(screen.getByText(/Error Running Tests/i)).toBeInTheDocument();
    expect(screen.getByText(/Test execution failed/i)).toBeInTheDocument();
  });

  it("toggles LLM layer option", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    const llmCheckbox = screen.getByLabelText(/Enable LLM Layer/i, {
      selector: 'input[type="checkbox"]',
    });

    // Should be checked by default
    expect(llmCheckbox).toBeChecked();

    fireEvent.click(llmCheckbox);
    expect(llmCheckbox).not.toBeChecked();
  });

  it("handles select all paragraphs", () => {
    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    const selectAllButton = screen.getByText(/Select All/i);
    fireEvent.click(selectAllButton);

    // Both paragraphs should be selected
    expect(screen.getByText(/2 paragraph\(s\) selected/i)).toBeInTheDocument();
  });

  it("shows empty state when no paragraphs available", () => {
    vi.mocked(ragExperimentsHooks.useTestParagraphs).mockReturnValue({
      data: { paragraphs: [], total_count: 0, limit: 100, offset: 0 },
      isLoading: false,
      error: null,
    } as any);

    render(<PipelineTestRunner />, { wrapper: createWrapper() });

    expect(
      screen.getByText(/No test paragraphs available/i),
    ).toBeInTheDocument();
  });
});
