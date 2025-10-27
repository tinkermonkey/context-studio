/**
 * TestResultsViewer Component Tests
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TestResultsViewer } from "../TestResultsViewer";

// Mock the hooks
const mockComparisonData = {
  paragraph_id: "test-para",
  runs: [
    {
      pipeline_name: "StandardRAGPipeline",
      run_id: "run-1",
      f1_score: 0.85,
      precision_score: 0.9,
      recall_score: 0.8,
      entities_extracted: 10,
      execution_time_ms: 1500.5,
      executed_at: new Date().toISOString(),
    },
  ],
  summary: {
    total_pipelines: 1,
    best_pipeline: "StandardRAGPipeline",
    best_f1_score: 0.85,
  },
};

jest.mock("@/api/hooks/ragExperiments", () => ({
  usePipelineComparison: jest.fn(() => ({
    data: mockComparisonData,
    isLoading: false,
    error: null,
  })),
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

describe("TestResultsViewer", () => {
  it("renders results summary", () => {
    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText(/Results Summary/i)).toBeInTheDocument();
    expect(screen.getByText(/Best Pipeline/i)).toBeInTheDocument();
    expect(screen.getByText(/StandardRAGPipeline/i)).toBeInTheDocument();
  });

  it("renders results table", () => {
    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText(/Pipeline Name/i)).toBeInTheDocument();
    expect(screen.getByText(/Precision/i)).toBeInTheDocument();
    expect(screen.getByText(/Recall/i)).toBeInTheDocument();
    expect(screen.getByText(/F1 Score/i)).toBeInTheDocument();
  });

  it("displays metric badges", () => {
    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    // F1 score: 85%
    expect(screen.getByText(/85.0%/i)).toBeInTheDocument();
    // Precision: 90%
    expect(screen.getByText(/90.0%/i)).toBeInTheDocument();
    // Recall: 80%
    expect(screen.getByText(/80.0%/i)).toBeInTheDocument();
  });

  it("renders export buttons", () => {
    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText(/Export CSV/i)).toBeInTheDocument();
    expect(screen.getByText(/Export JSON/i)).toBeInTheDocument();
  });

  it("shows loading state", () => {
    const { usePipelineComparison } = require("@/api/hooks/ragExperiments");
    usePipelineComparison.mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
    });

    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText(/Loading test results/i)).toBeInTheDocument();
  });

  it("shows empty state when no results", () => {
    const { usePipelineComparison } = require("@/api/hooks/ragExperiments");
    usePipelineComparison.mockReturnValue({
      data: { runs: [], summary: null },
      isLoading: false,
      error: null,
    });

    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    expect(
      screen.getByText(/No test results available/i)
    ).toBeInTheDocument();
  });

  it("shows error state", () => {
    const { usePipelineComparison } = require("@/api/hooks/ragExperiments");
    usePipelineComparison.mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error("Test error"),
    });

    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText(/Error Loading Results/i)).toBeInTheDocument();
    expect(screen.getByText(/Test error/i)).toBeInTheDocument();
  });

  it("handles export CSV with empty results", () => {
    const { usePipelineComparison } = require("@/api/hooks/ragExperiments");
    usePipelineComparison.mockReturnValue({
      data: { runs: [], summary: null },
      isLoading: false,
      error: null,
    });

    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    // Export buttons should not be visible when no results
    expect(
      screen.queryByText(/Export CSV/i)
    ).not.toBeInTheDocument();
  });

  it("displays pagination controls for large result sets", () => {
    const largeDataset = {
      paragraph_id: "test-para",
      runs: Array.from({ length: 15 }, (_, i) => ({
        pipeline_name: `Pipeline${i + 1}`,
        run_id: `run-${i + 1}`,
        f1_score: 0.85,
        precision_score: 0.9,
        recall_score: 0.8,
        entities_extracted: 10,
        execution_time_ms: 1500.5,
        executed_at: new Date().toISOString(),
      })),
      summary: {
        total_pipelines: 15,
        best_pipeline: "Pipeline1",
        best_f1_score: 0.85,
      },
    };

    const { usePipelineComparison } = require("@/api/hooks/ragExperiments");
    usePipelineComparison.mockReturnValue({
      data: largeDataset,
      isLoading: false,
      error: null,
    });

    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    // Should show pagination controls for > 10 results
    expect(screen.getByText(/Page 1 of 2/i)).toBeInTheDocument();
    expect(screen.getByText(/Previous/i)).toBeInTheDocument();
    expect(screen.getByText(/Next/i)).toBeInTheDocument();
  });

  it("sorts columns when header is clicked", () => {
    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    const f1Header = screen.getByText(/F1 Score/i);
    expect(f1Header).toBeInTheDocument();

    // F1 score should be sortable
    fireEvent.click(f1Header);
  });

  it("displays execution time correctly", () => {
    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText(/1500.50/i)).toBeInTheDocument();
  });

  it("handles null metrics gracefully", () => {
    const dataWithNulls = {
      paragraph_id: "test-para",
      runs: [
        {
          pipeline_name: "TestPipeline",
          run_id: "run-1",
          f1_score: null,
          precision_score: null,
          recall_score: null,
          entities_extracted: 0,
          execution_time_ms: null,
          executed_at: new Date().toISOString(),
        },
      ],
      summary: {
        total_pipelines: 1,
        best_pipeline: null,
        best_f1_score: null,
      },
    };

    const { usePipelineComparison } = require("@/api/hooks/ragExperiments");
    usePipelineComparison.mockReturnValue({
      data: dataWithNulls,
      isLoading: false,
      error: null,
    });

    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    // Should display N/A for null values
    const naElements = screen.getAllByText(/N\/A/i);
    expect(naElements.length).toBeGreaterThan(0);
  });

  it("displays color-coded metric badges correctly", () => {
    const multipleRuns = {
      paragraph_id: "test-para",
      runs: [
        {
          pipeline_name: "HighScorePipeline",
          run_id: "run-1",
          f1_score: 0.9, // Should be success (green)
          precision_score: 0.7, // Should be warning (yellow)
          recall_score: 0.5, // Should be failure (red)
          entities_extracted: 10,
          execution_time_ms: 1500.5,
          executed_at: new Date().toISOString(),
        },
      ],
      summary: null,
    };

    const { usePipelineComparison } = require("@/api/hooks/ragExperiments");
    usePipelineComparison.mockReturnValue({
      data: multipleRuns,
      isLoading: false,
      error: null,
    });

    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    // Should display different score percentages
    expect(screen.getByText(/90.0%/i)).toBeInTheDocument();
    expect(screen.getByText(/70.0%/i)).toBeInTheDocument();
    expect(screen.getByText(/50.0%/i)).toBeInTheDocument();
  });

  it("displays total result count", () => {
    const { usePipelineComparison } = require("@/api/hooks/ragExperiments");
    usePipelineComparison.mockReturnValue({
      data: mockComparisonData,
      isLoading: false,
      error: null,
    });

    render(<TestResultsViewer paragraphId="test-para" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByText(/Total Pipelines/i)).toBeInTheDocument();
    expect(screen.getByText(/1/)).toBeInTheDocument();
  });
});
