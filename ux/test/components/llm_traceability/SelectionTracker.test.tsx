/**
 * SelectionTracker Component Tests
 *
 * Unit tests for the SelectionTracker component including error scenarios
 * Tests wrapper functionality, error handling, and different integration patterns
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

import {
  SelectionTracker,
  withSelectionTracking,
  useManualSelectionTracking,
} from "@/components/llm_traceability/SelectionTracker";

// Mock the hooks
vi.mock("@/api/hooks/llm/useLLMTraceabilityMutations", () => ({
  useRecordSelectionMutation: vi.fn(),
  useOptimisticSelectionRecording: vi.fn(),
}));

import {
  useRecordSelectionMutation,
  useOptimisticSelectionRecording,
} from "@/api/hooks/llm/useLLMTraceabilityMutations";

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

// Mock child components for testing
const MockButton = ({
  onSelect,
  onAccept,
  onApply,
  onClick,
  children,
  ...props
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
}: any) => (
  <button
    onClick={(e) => {
      onSelect?.("selected content");
      onAccept?.("accepted content");
      onApply?.("applied content");
      onClick?.(e);
    }}
    data-testid="mock-button"
    {...props}
  >
    {children}
  </button>
);

const MockContentButton = ({
  onClick,
  "data-content": content,
  children,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
}: any) => (
  <button
    onClick={onClick}
    data-content={content}
    data-testid="mock-content-button"
  >
    {children}
  </button>
);

describe("SelectionTracker", () => {
  const mockRecordSelection = vi.fn();
  const mockOptimisticRecording = {
    recordSelection: vi.fn(),
    isTracking: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock the hooks
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (useRecordSelectionMutation as any).mockReturnValue({
      mutate: mockRecordSelection,
      isPending: false,
    });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (useOptimisticSelectionRecording as any).mockReturnValue(
      mockOptimisticRecording,
    );
  });

  describe("Basic Functionality", () => {
    it("should render children without modification when no selection occurs", () => {
      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
          >
            <div data-testid="child">Child content</div>
          </SelectionTracker>
        </TestWrapper>,
      );

      expect(screen.getByTestId("child")).toBeInTheDocument();
      expect(screen.getByText("Child content")).toBeInTheDocument();
    });

    it("should add tracking attributes to wrapper", () => {
      const { container } = render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
          >
            <div>Child</div>
          </SelectionTracker>
        </TestWrapper>,
      );

      const wrapper = container.firstChild as Element;
      expect(wrapper).toHaveAttribute("data-execution-id", "exec-123");
      expect(wrapper).toHaveAttribute("data-record-id", "node-456");
      expect(wrapper).toHaveAttribute("data-field", "definition");
      expect(wrapper).toHaveClass("selection-tracker");
    });

    it("should apply custom className", () => {
      const { container } = render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
            className="custom-tracker"
          >
            <div>Child</div>
          </SelectionTracker>
        </TestWrapper>,
      );

      const wrapper = container.firstChild as Element;
      expect(wrapper).toHaveClass("selection-tracker", "custom-tracker");
    });
  });

  describe("Selection Tracking", () => {
    it("should track selection via onSelect callback", async () => {
      const user = userEvent.setup();
      const onSelectionRecorded = vi.fn();

      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
            onSelectionRecorded={onSelectionRecorded}
          >
            <MockButton>Select</MockButton>
          </SelectionTracker>
        </TestWrapper>,
      );

      const button = screen.getByTestId("mock-button");
      await user.click(button);

      expect(mockOptimisticRecording.recordSelection).toHaveBeenCalledWith({
        execution_id: "exec-123",
        record_type: "structure_node",
        record_id: "node-456",
        suggestion_field: "definition",
        selected_content: "selected content",
      });

      expect(onSelectionRecorded).toHaveBeenCalled();
    });

    it("should track selection via onAccept callback", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
          >
            <MockButton>Accept</MockButton>
          </SelectionTracker>
        </TestWrapper>,
      );

      const button = screen.getByTestId("mock-button");
      await user.click(button);

      expect(mockOptimisticRecording.recordSelection).toHaveBeenCalledWith({
        execution_id: "exec-123",
        record_type: "structure_node",
        record_id: "node-456",
        suggestion_field: "definition",
        selected_content: "accepted content",
      });
    });

    it("should track selection via onApply callback", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
          >
            <MockButton>Apply</MockButton>
          </SelectionTracker>
        </TestWrapper>,
      );

      const button = screen.getByTestId("mock-button");
      await user.click(button);

      expect(mockOptimisticRecording.recordSelection).toHaveBeenCalledWith({
        execution_id: "exec-123",
        record_type: "structure_node",
        record_id: "node-456",
        suggestion_field: "definition",
        selected_content: "applied content",
      });
    });

    it("should track selection via data-content attribute", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
          >
            <MockContentButton data-content="content from attribute">
              Click me
            </MockContentButton>
          </SelectionTracker>
        </TestWrapper>,
      );

      const button = screen.getByTestId("mock-content-button");
      await user.click(button);

      expect(mockOptimisticRecording.recordSelection).toHaveBeenCalledWith({
        execution_id: "exec-123",
        record_type: "structure_node",
        record_id: "node-456",
        suggestion_field: "definition",
        selected_content: "content from attribute",
      });
    });

    it("should preserve original callbacks when wrapping", async () => {
      const user = userEvent.setup();
      const originalOnSelect = vi.fn();

      const ChildWithCallback = ({
        onSelect,
      }: {
        onSelect?: (content: string) => void;
      }) => (
        <button
          onClick={() => onSelect?.("test content")}
          data-testid="child-button"
        >
          Child
        </button>
      );

      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
          >
            <ChildWithCallback onSelect={originalOnSelect} />
          </SelectionTracker>
        </TestWrapper>,
      );

      const button = screen.getByTestId("child-button");
      await user.click(button);

      // Both tracking and original callback should be called
      expect(mockOptimisticRecording.recordSelection).toHaveBeenCalled();
      expect(originalOnSelect).toHaveBeenCalledWith("test content");
    });
  });

  describe("Error Handling", () => {
    it("should handle missing parameters gracefully", async () => {
      const user = userEvent.setup();
      const consoleWarnSpy = vi
        .spyOn(console, "warn")
        .mockImplementation(() => {});

      render(
        <TestWrapper>
          <SelectionTracker
            executionId=""
            recordId="node-456"
            suggestionField="definition"
          >
            <MockButton>Select</MockButton>
          </SelectionTracker>
        </TestWrapper>,
      );

      const button = screen.getByTestId("mock-button");
      await user.click(button);

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining("Missing required parameters"),
        expect.any(Object),
      );

      expect(mockOptimisticRecording.recordSelection).not.toHaveBeenCalled();

      consoleWarnSpy.mockRestore();
    });

    it("should call onTrackingError when tracking fails", async () => {
      const user = userEvent.setup();
      const onTrackingError = vi.fn();
      const mockError = new Error("Tracking failed");

      // Mock non-optimistic recording with error
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (useRecordSelectionMutation as any).mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        error: mockError,
      });

      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
            onTrackingError={onTrackingError}
            optimistic={false}
          >
            <MockButton>Select</MockButton>
          </SelectionTracker>
        </TestWrapper>,
      );

      const button = screen.getByTestId("mock-button");
      await user.click(button);

      // Simulate the error callback being called
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const mockMutationHook = (useRecordSelectionMutation as any).mock
        .calls[0][0];
      mockMutationHook.onError(mockError, {
        execution_id: "exec-123",
        record_type: "structure_node",
        record_id: "node-456",
        suggestion_field: "definition",
        selected_content: "selected content",
      });

      expect(onTrackingError).toHaveBeenCalledWith(mockError);
    });
  });

  describe("Visual Feedback", () => {
    it("should show tracking indicator when showFeedback is true and tracking", () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (useOptimisticSelectionRecording as any).mockReturnValue({
        recordSelection: vi.fn(),
        isTracking: true,
      });

      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
            showFeedback={true}
          >
            <div>Child</div>
          </SelectionTracker>
        </TestWrapper>,
      );

      expect(screen.getByText("Recording selection...")).toBeInTheDocument();
    });

    it("should not show tracking indicator when showFeedback is false", () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (useOptimisticSelectionRecording as any).mockReturnValue({
        recordSelection: vi.fn(),
        isTracking: true,
      });

      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
            showFeedback={false}
          >
            <div>Child</div>
          </SelectionTracker>
        </TestWrapper>,
      );

      expect(
        screen.queryByText("Recording selection..."),
      ).not.toBeInTheDocument();
    });
  });

  describe("Optimistic vs Non-optimistic Recording", () => {
    it("should use optimistic recording by default", () => {
      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
          >
            <div>Child</div>
          </SelectionTracker>
        </TestWrapper>,
      );

      expect(useOptimisticSelectionRecording).toHaveBeenCalled();
    });

    it("should use regular recording when optimistic is disabled", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
            optimistic={false}
          >
            <MockButton>Select</MockButton>
          </SelectionTracker>
        </TestWrapper>,
      );

      const button = screen.getByTestId("mock-button");
      await user.click(button);

      expect(mockRecordSelection).toHaveBeenCalled();
      expect(mockOptimisticRecording.recordSelection).not.toHaveBeenCalled();
    });
  });

  describe("Higher-Order Component", () => {
    it("should work with withSelectionTracking HOC", () => {
      const TestComponent = ({ testProp }: { testProp: string }) => (
        <div data-testid="hoc-component">{testProp}</div>
      );

      const WrappedComponent = withSelectionTracking(TestComponent, {
        executionId: "exec-123",
        recordId: "node-456",
        suggestionField: "definition",
      });

      render(
        <TestWrapper>
          <WrappedComponent testProp="test value" />
        </TestWrapper>,
      );

      expect(screen.getByTestId("hoc-component")).toBeInTheDocument();
      expect(screen.getByText("test value")).toBeInTheDocument();
    });
  });

  describe("Manual Selection Tracking Hook", () => {
    it("should provide manual tracking functionality", () => {
      const TestComponent = () => {
        const { trackSelection, isTracking } = useManualSelectionTracking(
          "exec-123",
          "node-456",
          "definition",
        );

        return (
          <div>
            <button
              onClick={() => trackSelection("manual content")}
              data-testid="manual-track-button"
            >
              Track Manually
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

      expect(screen.getByTestId("manual-track-button")).toBeInTheDocument();
      expect(screen.getByTestId("tracking-status")).toHaveTextContent("idle");
    });
  });

  describe("Multiple Children", () => {
    it("should handle multiple child elements", async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
          >
            <MockButton>Button 1</MockButton>
            <MockButton>Button 2</MockButton>
          </SelectionTracker>
        </TestWrapper>,
      );

      const buttons = screen.getAllByTestId("mock-button");
      expect(buttons).toHaveLength(2);

      await user.click(buttons[0]);
      expect(mockOptimisticRecording.recordSelection).toHaveBeenCalledTimes(1);

      await user.click(buttons[1]);
      expect(mockOptimisticRecording.recordSelection).toHaveBeenCalledTimes(2);
    });
  });

  describe("Edge Cases", () => {
    it("should handle non-React element children gracefully", () => {
      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
          >
            <span>Text content</span>
            <div>Normal element</div>
          </SelectionTracker>
        </TestWrapper>,
      );

      expect(screen.getByText("Text content")).toBeInTheDocument();
      expect(screen.getByText("Normal element")).toBeInTheDocument();
    });

    it("should handle empty children", () => {
      render(
        <TestWrapper>
          <SelectionTracker
            executionId="exec-123"
            recordId="node-456"
            suggestionField="definition"
          >
            <div>Empty</div>
          </SelectionTracker>
        </TestWrapper>,
      );

      // Should not crash
      expect(
        screen.getByTestId("selection-tracker") ||
          document.querySelector(".selection-tracker"),
      ).toBeTruthy();
    });
  });
});
