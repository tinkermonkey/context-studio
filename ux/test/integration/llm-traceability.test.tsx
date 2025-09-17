/**
 * LLM Traceability Integration Test
 *
 * Tests the complete flow of LLM traceability features including selection recording,
 * analytics data fetching, and error handling with graceful degradation
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import { llmTraceabilityService } from "@/api/services/llmTraceability";
import {
  useLLMTraceabilityHealth,
  useExecutionAnalytics,
  useExecutionHistory,
  useRecordSelectionMutation,
  SelectionTracker,
  AnalyticsDashboard,
  ExecutionHistory,
  useSelectionTracking,
} from "@/api";

// Mock the traceability service
vi.mock("@/api/services/llmTraceability", () => ({
  llmTraceabilityService: {
    healthCheck: vi.fn(),
    getExecutionAnalytics: vi.fn(),
    getExecutionHistory: vi.fn(),
    recordSelection: vi.fn(),
    recordSuggestionSelection: vi.fn(),
  },
}));

// Test wrapper component
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        retryOnMount: false,
        refetchOnWindowFocus: false,
        refetchOnMount: false,
        refetchOnReconnect: false,
        staleTime: 0,
        gcTime: 0,
      },
      mutations: {
        retry: false,
        retryOnMount: false,
      },
    },
    logger: {
      log: () => {},
      warn: () => {},
      error: () => {},
    },
  });

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

// Mock data
const mockHealthResponse = {
  status: "healthy" as const,
  database_connection: true,
  api_version: "1.0.0",
  timestamp: "2024-01-01T00:00:00Z",
  uptime_seconds: 3600,
};

const mockAnalyticsResponse = {
  success: true,
  data: {
    total_executions: 100,
    successful_executions: 95,
    success_rate: 0.95,
    avg_execution_time: 1500,
    total_tokens_used: 50000,
    total_selections: 75,
    selection_rate: 0.75,
  },
  filters: {
    pipeline_type: "term_definition",
    days_back: 30,
  },
};

const mockExecutionHistoryResponse = {
  success: true,
  data: {
    execution: {
      execution_id: "exec-123",
      pipeline_type: "term_definition",
      status: "completed" as const,
      execution_time: 1200,
      tokens_used: 500,
      timestamp: "2024-01-01T12:00:00Z",
      input_data: { term: "machine learning" },
      output_data: { definition: "A subset of AI..." },
    },
    selections: [
      {
        selection_id: "sel-456",
        record_type: "structure_node",
        record_id: "node-789",
        suggestion_field: "definition",
        selected_content: "A subset of AI...",
        timestamp: "2024-01-01T12:01:00Z",
      },
    ],
  },
};

const mockSelectionResponse = {
  success: true,
  message: "Selection recorded successfully",
  selection_id: "sel-new-123",
};

describe("LLM Traceability Integration", () => {
  let mockService: any;

  beforeEach(() => {
    mockService = llmTraceabilityService;

    // Reset all mocks
    vi.clearAllMocks();

    // Clean up DOM between tests
    document.body.innerHTML = '<div id="root"></div>';

    // Set up default successful responses
    mockService.healthCheck.mockResolvedValue(mockHealthResponse);
    mockService.getExecutionAnalytics.mockResolvedValue(mockAnalyticsResponse);
    mockService.getExecutionHistory.mockResolvedValue(
      mockExecutionHistoryResponse,
    );
    mockService.recordSelection.mockResolvedValue(mockSelectionResponse);
    mockService.recordSuggestionSelection.mockResolvedValue(
      mockSelectionResponse,
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Service Integration", () => {
    it("should export traceability service with all methods", () => {
      expect(llmTraceabilityService).toBeDefined();
      expect(llmTraceabilityService.healthCheck).toBeInstanceOf(Function);
      expect(llmTraceabilityService.getExecutionAnalytics).toBeInstanceOf(
        Function,
      );
      expect(llmTraceabilityService.getExecutionHistory).toBeInstanceOf(
        Function,
      );
      expect(llmTraceabilityService.recordSelection).toBeInstanceOf(Function);
      expect(llmTraceabilityService.recordSuggestionSelection).toBeInstanceOf(
        Function,
      );
    });

    it("should handle health check correctly", async () => {
      const result = await llmTraceabilityService.healthCheck();
      expect(result).toEqual(mockHealthResponse);
      expect(mockService.healthCheck).toHaveBeenCalledTimes(1);
    });

    it("should handle analytics fetching correctly", async () => {
      const filters = { days_back: 30, pipeline_type: "term_definition" };
      const result =
        await llmTraceabilityService.getExecutionAnalytics(filters);
      expect(result).toEqual(mockAnalyticsResponse);
      expect(mockService.getExecutionAnalytics).toHaveBeenCalledWith(filters);
    });

    it("should handle execution history fetching correctly", async () => {
      const executionId = "exec-123";
      const result =
        await llmTraceabilityService.getExecutionHistory(executionId);
      expect(result).toEqual(mockExecutionHistoryResponse);
      expect(mockService.getExecutionHistory).toHaveBeenCalledWith(executionId);
    });
  });

  describe("Hook Integration", () => {
    it("should export all traceability hooks", () => {
      expect(useLLMTraceabilityHealth).toBeInstanceOf(Function);
      expect(useExecutionAnalytics).toBeInstanceOf(Function);
      expect(useExecutionHistory).toBeInstanceOf(Function);
      expect(useRecordSelectionMutation).toBeInstanceOf(Function);
      expect(useSelectionTracking).toBeInstanceOf(Function);
    });

    it("should handle health check hook correctly", async () => {
      const TestComponent = () => {
        const { data, isLoading, error } = useLLMTraceabilityHealth();

        if (isLoading) return <div>Loading...</div>;
        if (error) return <div>Error: {error.message}</div>;
        if (!data) return <div>No data</div>;

        return <div data-testid="health-status">{data.status}</div>;
      };

      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>,
      );

      // Initially loading
      expect(screen.getByText("Loading...")).toBeInTheDocument();

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByTestId("health-status")).toBeInTheDocument();
      });

      expect(screen.getByTestId("health-status")).toHaveTextContent("healthy");
      expect(mockService.healthCheck).toHaveBeenCalledTimes(1);
    });

    it("should handle analytics hook correctly", async () => {
      const TestComponent = () => {
        const { data, isLoading } = useExecutionAnalytics({ days_back: 30 });

        if (isLoading) return <div>Loading analytics...</div>;
        if (!data) return <div>No analytics data</div>;

        return (
          <div>
            <div data-testid="total-executions">
              {data.data.total_executions}
            </div>
            <div data-testid="success-rate">{data.data.success_rate}</div>
          </div>
        );
      };

      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByTestId("total-executions")).toBeInTheDocument();
      });

      expect(screen.getByTestId("total-executions")).toHaveTextContent("100");
      expect(screen.getByTestId("success-rate")).toHaveTextContent("0.95");
    });
  });

  describe("Selection Recording", () => {
    it("should record selections without blocking user workflow", async () => {
      const user = userEvent.setup();
      const onSelectionRecorded = vi.fn();

      const MockSuggestion = ({
        onSelect,
        onAccept,
      }: {
        onSelect?: (content: string) => void;
        onAccept?: (content: string) => void;
      }) => {
        const handleClick = () => {
          const content = "Selected content";
          onSelect?.(content);
          onAccept?.(content);
        };

        return (
          <button onClick={handleClick} data-testid="suggestion-button">
            Accept Suggestion
          </button>
        );
      };

      const TestComponent = () => (
        <SelectionTracker
          executionId="exec-123"
          recordId="node-456"
          suggestionField="definition"
          onSelectionRecorded={onSelectionRecorded}
        >
          <MockSuggestion />
        </SelectionTracker>
      );

      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>,
      );

      const button = screen.getByTestId("suggestion-button");
      await user.click(button);

      // Selection should be recorded (optimistically)
      expect(onSelectionRecorded).toHaveBeenCalled();

      // API call should happen in background
      await waitFor(() => {
        expect(mockService.recordSelection).toHaveBeenCalledWith({
          execution_id: "exec-123",
          record_type: "structure_node",
          record_id: "node-456",
          suggestion_field: "definition",
          selected_content: "Selected content",
        });
      });
    });

    it("should gracefully handle tracking failures without affecting UX", async () => {
      const user = userEvent.setup();
      const onSelectionRecorded = vi.fn();
      const consoleWarnSpy = vi
        .spyOn(console, "warn")
        .mockImplementation(() => {});

      // Mock failure
      mockService.recordSelection.mockRejectedValue(new Error("Network Error"));

      // Test using the hook directly to ensure the error handling works
      const TestComponent = () => {
        const { trackSelection, isTracking } = useSelectionTracking({
          onSuccess: onSelectionRecorded,
          debug: false,
        });

        return (
          <div>
            <button
              onClick={() =>
                trackSelection(
                  "exec-123",
                  "node-456",
                  "definition",
                  "Selected content",
                )
              }
              data-testid="track-button"
            >
              Track Selection
            </button>
            <div data-testid="tracking-status">
              {isTracking ? "tracking" : "idle"}
            </div>
          </div>
        );
      };

      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>,
      );

      const button = screen.getByTestId("track-button");
      await user.click(button);

      // Wait for the failure to be processed
      await waitFor(
        () => {
          expect(mockService.recordSelection).toHaveBeenCalled();
        },
        { timeout: 3000 },
      );

      // Wait a bit more for the error to be processed and logged
      await waitFor(
        () => {
          expect(consoleWarnSpy).toHaveBeenCalled();
        },
        { timeout: 3000 },
      );

      // Should have logged the error but not thrown
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining("Optimistic selection tracking failed"),
        expect.any(Object),
      );

      // User workflow should not be affected - no error thrown
      expect(button).toBeInTheDocument();

      consoleWarnSpy.mockRestore();
    });

    it("should handle custom selection tracking hook correctly", async () => {
      const TestComponent = () => {
        const { trackSelection, isTracking, getStats } = useSelectionTracking({
          onSuccess: () => {},
          debug: false,
        });

        return (
          <div>
            <button
              onClick={() =>
                trackSelection("exec-123", "node-456", "definition", "content")
              }
              data-testid="track-button"
            >
              Track Selection
            </button>
            <div data-testid="tracking-status">
              {isTracking ? "tracking" : "idle"}
            </div>
            <div data-testid="stats">{JSON.stringify(getStats())}</div>
          </div>
        );
      };

      const user = userEvent.setup();
      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>,
      );

      const button = screen.getByTestId("track-button");
      const status = screen.getByTestId("tracking-status");

      expect(status).toHaveTextContent("idle");

      await user.click(button);

      // Should eventually complete
      await waitFor(() => {
        expect(status).toHaveTextContent("idle");
      });

      expect(mockService.recordSelection).toHaveBeenCalled();
    });
  });

  describe("Component Integration", () => {
    it("should render AnalyticsDashboard without errors", () => {
      render(
        <TestWrapper>
          <AnalyticsDashboard />
        </TestWrapper>,
      );

      expect(screen.getByText("LLM Analytics Dashboard")).toBeInTheDocument();
    });

    it("should render ExecutionHistory without errors", () => {
      render(
        <TestWrapper>
          <ExecutionHistory />
        </TestWrapper>,
      );

      expect(screen.getByText("Execution History")).toBeInTheDocument();
    });

    it("should handle SelectionTracker with different child types", () => {
      const TestComponent = () => (
        <SelectionTracker
          executionId="exec-123"
          recordId="node-456"
          suggestionField="definition"
        >
          <div data-testid="child-element">Child content</div>
        </SelectionTracker>
      );

      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>,
      );

      expect(screen.getByTestId("child-element")).toBeInTheDocument();
      expect(screen.getByText("Child content")).toBeInTheDocument();
    });
  });

  describe("Error Handling and Graceful Degradation", () => {
    it("should handle network failures gracefully in analytics", async () => {
      mockService.getExecutionAnalytics.mockRejectedValue(
        new Error("Network Error"),
      );

      const TestComponent = () => {
        const { data, isLoading, error } = useExecutionAnalytics(null, {
          retry: false,
          retryDelay: 0,
        });

        if (isLoading) return <div>Loading...</div>;
        if (error) return <div data-testid="error">Analytics unavailable</div>;

        return <div>Analytics data</div>;
      };

      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>,
      );

      await waitFor(
        () => {
          expect(screen.getByTestId("error")).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      expect(screen.getByTestId("error")).toHaveTextContent(
        "Analytics unavailable",
      );
    });

    it("should handle service unavailable scenarios", async () => {
      mockService.healthCheck.mockRejectedValue(
        new Error("Service Unavailable"),
      );

      const TestComponent = () => {
        const { data, isLoading, error } = useLLMTraceabilityHealth({
          retry: false,
          retryDelay: 0,
        });

        if (isLoading) return <div>Checking health...</div>;
        if (error)
          return <div data-testid="service-error">Service unavailable</div>;

        return <div>Service healthy</div>;
      };

      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>,
      );

      await waitFor(
        () => {
          expect(screen.getByTestId("service-error")).toBeInTheDocument();
        },
        { timeout: 3000 },
      );

      expect(screen.getByTestId("service-error")).toHaveTextContent(
        "Service unavailable",
      );
    });
  });

  describe("Performance and Caching", () => {
    it("should cache analytics queries appropriately", async () => {
      const TestComponent = () => {
        const { data } = useExecutionAnalytics({ days_back: 30 });
        const { data: data2 } = useExecutionAnalytics({ days_back: 30 });

        return (
          <div>
            <div data-testid="data1">{data?.data.total_executions || 0}</div>
            <div data-testid="data2">{data2?.data.total_executions || 0}</div>
          </div>
        );
      };

      render(
        <TestWrapper>
          <TestComponent />
        </TestWrapper>,
      );

      await waitFor(() => {
        expect(screen.getByTestId("data1")).toBeInTheDocument();
        expect(screen.getByTestId("data2")).toBeInTheDocument();
      });

      // Should only call the service once due to caching
      expect(mockService.getExecutionAnalytics).toHaveBeenCalledTimes(1);
    });
  });
});
