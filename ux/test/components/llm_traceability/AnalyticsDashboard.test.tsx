/**
 * AnalyticsDashboard Component Tests
 *
 * Unit tests for the AnalyticsDashboard component with mock data
 * Tests different states, error scenarios, and user interactions
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { AnalyticsDashboard } from "@/components/llm_traceability/AnalyticsDashboard";

// Mock the hooks
vi.mock("@/api/hooks/llm/useLLMTraceability", () => ({
  useAnalyticsForTimeRange: vi.fn(),
  useAnalyticsWithRefresh: vi.fn(),
  useLLMTraceabilityHealth: vi.fn(),
}));

import {
  useAnalyticsForTimeRange,
  useAnalyticsWithRefresh,
  useLLMTraceabilityHealth,
} from "@/api/hooks/llm/useLLMTraceability";

const mockAnalyticsData = {
  success: true,
  data: {
    total_executions: 1000,
    successful_executions: 950,
    success_rate: 0.95,
    avg_execution_time: 1200,
    total_tokens_used: 75000,
    total_selections: 800,
    selection_rate: 0.84,
  },
  filters: {
    pipeline_type: "term_definition",
    days_back: 30,
  },
};

const mockHealthData = {
  status: "healthy" as const,
  database_connection: true,
  api_version: "1.0.0",
  timestamp: "2024-01-01T00:00:00Z",
  uptime_seconds: 3600,
};

const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("AnalyticsDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default successful responses
    (useAnalyticsForTimeRange as any).mockReturnValue({
      data: mockAnalyticsData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    (useAnalyticsWithRefresh as any).mockReturnValue({
      data: mockAnalyticsData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    (useLLMTraceabilityHealth as any).mockReturnValue({
      data: mockHealthData,
      isLoading: false,
      error: null,
    });
  });

  describe("Rendering", () => {
    it("should render dashboard with title and description", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      expect(screen.getByText("LLM Analytics Dashboard")).toBeInTheDocument();
      expect(
        screen.getByText("Track AI suggestion usage and performance metrics"),
      ).toBeInTheDocument();
    });

    it("should render all metric cards with data", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      // Check for key metrics
      expect(screen.getByText("Total Executions")).toBeInTheDocument();
      expect(screen.getByText("1,000")).toBeInTheDocument();

      expect(screen.getByText("Success Rate")).toBeInTheDocument();
      expect(screen.getByText("95.0%")).toBeInTheDocument();

      expect(screen.getByText("Avg Response Time")).toBeInTheDocument();
      expect(screen.getByText("1200ms")).toBeInTheDocument();

      expect(screen.getByText("Total Selections")).toBeInTheDocument();
      expect(screen.getByText("800")).toBeInTheDocument();

      expect(screen.getByText("Selection Rate")).toBeInTheDocument();
      expect(screen.getByText("84.0%")).toBeInTheDocument();

      expect(screen.getByText("Tokens Used")).toBeInTheDocument();
      expect(screen.getByText("75,000")).toBeInTheDocument();
    });

    it("should render health status indicator", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard showHealthStatus={true} />
        </TestWrapper>,
      );

      expect(screen.getByText("healthy")).toBeInTheDocument();
    });

    it("should render time range selector", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      const select = screen.getByDisplayValue("Last 30 Days");
      expect(select).toBeInTheDocument();
    });

    it("should render refresh button", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      expect(screen.getByText("Refresh")).toBeInTheDocument();
    });
  });

  describe("Loading States", () => {
    it("should show loading spinner when analytics are loading", () => {
      (useAnalyticsForTimeRange as any).mockReturnValue({
        data: null,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      });

      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      expect(screen.getByText("Loading analytics data...")).toBeInTheDocument();
    });

    it("should show loading spinner in refresh button when refreshing", () => {
      const mockRefetch = vi.fn();
      (useAnalyticsForTimeRange as any).mockReturnValue({
        data: mockAnalyticsData,
        isLoading: true,
        error: null,
        refetch: mockRefetch,
      });

      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      // Should have spinner in refresh button
      const refreshButton = screen.getByRole("button");
      expect(refreshButton).toBeDisabled();
    });

    it("should show health loading state", () => {
      (useLLMTraceabilityHealth as any).mockReturnValue({
        data: null,
        isLoading: true,
        error: null,
      });

      render(
        <TestWrapper>
          <AnalyticsDashboard showHealthStatus={true} />
        </TestWrapper>,
      );

      // Should show spinner for health status
      expect(screen.getByRole("status")).toBeInTheDocument();
    });
  });

  describe("Error States", () => {
    it("should show error alert when analytics fail to load", () => {
      (useAnalyticsForTimeRange as any).mockReturnValue({
        data: null,
        isLoading: false,
        error: new Error("Failed to fetch analytics"),
        refetch: vi.fn(),
      });

      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      expect(screen.getByText("Failed to load analytics:")).toBeInTheDocument();
      expect(screen.getByText("Failed to fetch analytics")).toBeInTheDocument();
    });

    it("should show degraded health status", () => {
      (useLLMTraceabilityHealth as any).mockReturnValue({
        data: { ...mockHealthData, status: "degraded" },
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <AnalyticsDashboard showHealthStatus={true} />
        </TestWrapper>,
      );

      expect(screen.getByText("degraded")).toBeInTheDocument();
    });

    it("should show unhealthy status with red indicator", () => {
      (useLLMTraceabilityHealth as any).mockReturnValue({
        data: { ...mockHealthData, status: "unhealthy" },
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <AnalyticsDashboard showHealthStatus={true} />
        </TestWrapper>,
      );

      expect(screen.getByText("unhealthy")).toBeInTheDocument();
    });
  });

  describe("User Interactions", () => {
    it("should change time range when selector is used", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      const select = screen.getByDisplayValue("Last 30 Days");
      await user.selectOptions(select, "7");

      expect(select).toHaveValue("7");
    });

    it("should call refetch when refresh button is clicked", async () => {
      const user = userEvent.setup();
      const mockRefetch = vi.fn();

      (useAnalyticsForTimeRange as any).mockReturnValue({
        data: mockAnalyticsData,
        isLoading: false,
        error: null,
        refetch: mockRefetch,
      });

      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      const refreshButton = screen.getByText("Refresh");
      await user.click(refreshButton);

      expect(mockRefetch).toHaveBeenCalledTimes(1);
    });

    it("should show export button when configured", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard config={{ showExportButton: true }} />
        </TestWrapper>,
      );

      expect(screen.getByText("Export")).toBeInTheDocument();
    });

    it("should handle export functionality", async () => {
      const user = userEvent.setup();

      // Mock the blob and URL APIs
      const mockBlob = vi.fn();
      const mockCreateObjectURL = vi.fn(() => "mock-url");
      const mockRevokeObjectURL = vi.fn();

      global.Blob = mockBlob as any;
      global.URL = {
        createObjectURL: mockCreateObjectURL,
        revokeObjectURL: mockRevokeObjectURL,
      } as any;

      // Mock document.createElement to return a mock link
      const mockClick = vi.fn();
      const mockLink = {
        href: "",
        download: "",
        click: mockClick,
      };
      vi.spyOn(document, "createElement").mockReturnValue(mockLink as any);

      render(
        <TestWrapper>
          <AnalyticsDashboard config={{ showExportButton: true }} />
        </TestWrapper>,
      );

      const exportButton = screen.getByText("Export");
      await user.click(exportButton);

      expect(mockBlob).toHaveBeenCalled();
      expect(mockCreateObjectURL).toHaveBeenCalled();
      expect(mockClick).toHaveBeenCalled();
    });
  });

  describe("Configuration Options", () => {
    it("should handle auto-refresh configuration", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard
            config={{
              autoRefresh: true,
              refreshInterval: 10000,
            }}
          />
        </TestWrapper>,
      );

      // Should use the auto-refresh hook
      expect(useAnalyticsWithRefresh).toHaveBeenCalled();
    });

    it("should handle custom default time range", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard config={{ defaultTimeRange: 7 }} />
        </TestWrapper>,
      );

      const select = screen.getByDisplayValue("Last 7 Days");
      expect(select).toBeInTheDocument();
    });

    it("should hide health status when configured", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard showHealthStatus={false} />
        </TestWrapper>,
      );

      expect(screen.queryByText("healthy")).not.toBeInTheDocument();
    });

    it("should call onDataUpdate callback when data changes", () => {
      const onDataUpdate = vi.fn();

      render(
        <TestWrapper>
          <AnalyticsDashboard onDataUpdate={onDataUpdate} />
        </TestWrapper>,
      );

      expect(onDataUpdate).toHaveBeenCalledWith(mockAnalyticsData.data);
    });

    it("should apply custom className", () => {
      const { container } = render(
        <TestWrapper>
          <AnalyticsDashboard className="custom-dashboard" />
        </TestWrapper>,
      );

      expect(container.firstChild).toHaveClass("custom-dashboard");
    });
  });

  describe("No Data State", () => {
    it("should show no data message when analytics data is empty", () => {
      (useAnalyticsForTimeRange as any).mockReturnValue({
        data: null,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      expect(screen.getByText("No Analytics Data")).toBeInTheDocument();
      expect(
        screen.getByText(
          "No LLM executions found for the selected time period.",
        ),
      ).toBeInTheDocument();
    });
  });

  describe("Performance Overview", () => {
    it("should render performance overview card with progress bars", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      expect(screen.getByText("Performance Overview")).toBeInTheDocument();

      // Should have progress bars for success rate and selection rate
      const progressBars = screen.getAllByRole("progressbar");
      expect(progressBars).toHaveLength(2);
    });
  });

  describe("Usage Summary", () => {
    it("should render usage summary card with execution details", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      expect(screen.getByText("Usage Summary")).toBeInTheDocument();
      expect(screen.getByText("950")).toBeInTheDocument(); // Successful executions
      expect(screen.getByText("50")).toBeInTheDocument(); // Failed executions (1000 - 950)
    });

    it("should show pipeline type in usage summary when filtered", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard pipelineTypeFilter="term_definition" />
        </TestWrapper>,
      );

      expect(screen.getByText("Pipeline Type")).toBeInTheDocument();
      expect(screen.getByText("term_definition")).toBeInTheDocument();
    });
  });
});
