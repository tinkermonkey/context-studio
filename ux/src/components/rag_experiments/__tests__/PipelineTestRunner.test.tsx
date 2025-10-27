/**
 * PipelineTestRunner Component Tests
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PipelineTestRunner } from "../PipelineTestRunner";

// Mock the hooks
jest.mock("@/api/hooks/ragExperiments", () => ({
  useTestParagraphs: () => ({
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
  }),
  useRunPipelineTest: () => ({
    mutateAsync: jest.fn(),
    isPending: false,
    isSuccess: false,
    error: null,
    data: null,
  }),
}));

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
});
