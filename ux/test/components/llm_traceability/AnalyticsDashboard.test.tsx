/**
 * AnalyticsDashboard Component Tests
 *
 * Unit tests for the AnalyticsDashboard component with mock data
 * Tests different states, error scenarios, and user interactions
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { AnalyticsDashboard } from "@/components/llm_traceability/AnalyticsDashboard";

// Mock the hooks
vi.mock("@/api/hooks/llm/useLLMTraceability", () => ({
  useAnalyticsForTimeRange: vi.fn(),
  useAnalyticsWithRefresh: vi.fn(),
  useLLMTraceabilityHealth: vi.fn(),
  useFlavorAnalytics: vi.fn(),
  useFlavorAnalyticsWithRefresh: vi.fn(),
}));

import {
  useAnalyticsForTimeRange,
  useAnalyticsWithRefresh,
  useLLMTraceabilityHealth,
  useFlavorAnalytics,
  useFlavorAnalyticsWithRefresh,
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
    <div data-testid="test-wrapper">
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </div>
  );
};

describe("AnalyticsDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Clean up DOM state between tests
    document.body.innerHTML = "";
    const root = document.createElement("div");
    root.setAttribute("id", "root");
    document.body.appendChild(root);

    // Default successful responses
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (useAnalyticsForTimeRange as any).mockReturnValue({
      data: mockAnalyticsData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (useAnalyticsWithRefresh as any).mockReturnValue({
      data: mockAnalyticsData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (useLLMTraceabilityHealth as any).mockReturnValue({
      data: mockHealthData,
      isLoading: false,
      error: null,
    });

    // Add missing flavor analytics mocks
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (useFlavorAnalytics as any).mockReturnValue({
      data: mockAnalyticsData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (useFlavorAnalyticsWithRefresh as any).mockReturnValue({
      data: mockAnalyticsData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
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

      expect(screen.getAllByText("Success Rate")[0]).toBeInTheDocument();
      expect(screen.getAllByText("95.0%")[0]).toBeInTheDocument();

      expect(screen.getByText("Avg Response Time")).toBeInTheDocument();
      expect(screen.getByText("1200ms")).toBeInTheDocument();

      expect(screen.getByText("Total Selections")).toBeInTheDocument();
      expect(screen.getByText("800")).toBeInTheDocument();

      expect(screen.getAllByText("Selection Rate")[0]).toBeInTheDocument();
      expect(screen.getAllByText("84.0%")[0]).toBeInTheDocument();

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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      global.Blob = mockBlob as any;
      global.URL = {
        createObjectURL: mockCreateObjectURL,
        revokeObjectURL: mockRevokeObjectURL,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } as any;

      // Mock only anchor element creation specifically
      const originalCreateElement = document.createElement;
      const mockClick = vi.fn();
      const mockLink = {
        href: "",
        download: "",
        click: mockClick,
        nodeName: "A",
        nodeType: 1,
      };

      vi.spyOn(document, "createElement").mockImplementation((tagName) => {
        if (tagName === "a") {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          return mockLink as any;
        }
        return originalCreateElement.call(document, tagName);
      });

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
      render(
        <TestWrapper>
          <AnalyticsDashboard className="custom-dashboard" />
        </TestWrapper>,
      );

      // The className should be applied to the dashboard component itself
      const dashboard = screen
        .getByText("LLM Analytics Dashboard")
        .closest('[class*="custom-dashboard"]');
      expect(dashboard).toBeInTheDocument();
    });
  });

  describe("No Data State", () => {
    it("should show no data message when analytics data is empty", () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

      // Check for success rate and selection rate percentages in performance overview
      expect(screen.getAllByText("95.0%").length).toBeGreaterThan(0);
      expect(screen.getAllByText("84.0%").length).toBeGreaterThan(0);
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
