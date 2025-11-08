/**
 * Unit tests for MultiWordNlpConceptChart component
 */

import { describe, it, expect, vi, beforeEach, Mock } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MultiWordNlpConceptChart } from "@/components/graphs/nlp_concept/MultiWordNlpConceptChart";
import { WordSense } from "@/api/types/structureNodes";
import * as useWordSensesHook from "@/api/hooks/structure_nodes/useWordSenses";

// Mock the hooks
vi.mock("@/api/hooks/structure_nodes/useWordSenses");
vi.mock("@/api/hooks/nlp/useNLPAnalysis");
vi.mock("@/utils/toast", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock NlpConceptChart component
vi.mock("@/components/graphs/nlp_concept/NlpConceptChart", () => ({
  default: ({ data, onNodeClick }: any) => (
    <div data-testid="nlp-concept-chart">
      <div>Word: {data.text}</div>
      <button onClick={() => onNodeClick("sense-0")}>Select Sense 0</button>
    </div>
  ),
}));

describe("MultiWordNlpConceptChart", () => {
  let queryClient: QueryClient;
  let mockUpdateWordSenses: Mock;

  const defaultProps = {
    title: "machine learning algorithm",
    persistedSenses: [] as WordSense[],
    nodeId: "test-node-id",
    onSaveComplete: vi.fn(),
  };

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    mockUpdateWordSenses = vi.fn();

    // Mock the useUpdateWordSenses hook
    vi.mocked(useWordSensesHook.useUpdateWordSenses).mockReturnValue({
      mutate: mockUpdateWordSenses,
      isPending: false,
      isError: false,
      isSuccess: false,
      error: null,
      data: undefined,
      variables: undefined,
      context: undefined,
      failureCount: 0,
      failureReason: null,
      isIdle: true,
      isPaused: false,
      mutateAsync: vi.fn(),
      reset: vi.fn(),
      status: "idle",
      submittedAt: 0,
    } as any);

    // Mock fetch for NLP analysis
    global.fetch = vi.fn();
  });

  const renderComponent = (props = {}) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <MultiWordNlpConceptChart {...defaultProps} {...props} />
      </QueryClientProvider>
    );
  };

  describe("Parsing and display", () => {
    it("should parse multi-word title correctly", () => {
      renderComponent();

      expect(screen.getByText("machine")).toBeInTheDocument();
      expect(screen.getByText("learning")).toBeInTheDocument();
      expect(screen.getByText("algorithm")).toBeInTheDocument();
    });

    it("should handle single word titles", () => {
      renderComponent({ title: "algorithm" });

      expect(screen.getByText("algorithm")).toBeInTheDocument();
      expect(screen.queryByText("learning")).not.toBeInTheDocument();
    });

    it("should handle titles with extra whitespace", () => {
      renderComponent({ title: "  machine   learning  " });

      expect(screen.getByText("machine")).toBeInTheDocument();
      expect(screen.getByText("learning")).toBeInTheDocument();
    });

    it("should display words in a grid layout", () => {
      const { container } = renderComponent();

      const grid = container.querySelector(".grid");
      expect(grid).toBeInTheDocument();
      expect(grid?.classList.contains("grid-cols-1")).toBe(true);
    });
  });

  describe("Persisted senses", () => {
    it("should display persisted sense selections", () => {
      const persistedSenses: WordSense[] = [
        {
          term: "machine",
          sense_type: "wordnet",
          sense_id: "machine.n.01",
          definition: "any mechanical or electrical device",
          domain: "engineering",
        },
      ];

      renderComponent({ persistedSenses });

      expect(screen.getByText(/machine.n.01/)).toBeInTheDocument();
    });

    it("should initialize selected senses from persisted data", () => {
      const persistedSenses: WordSense[] = [
        {
          term: "machine",
          sense_type: "wordnet",
          sense_id: "machine.n.01",
          definition: "any mechanical or electrical device",
          domain: "engineering",
        },
        {
          term: "learning",
          sense_type: "wordnet",
          sense_id: "learning.n.01",
          definition: "the cognitive process of acquiring skill",
          domain: "psychology",
        },
      ];

      renderComponent({ persistedSenses });

      expect(screen.getByText(/machine.n.01/)).toBeInTheDocument();
      expect(screen.getByText(/learning.n.01/)).toBeInTheDocument();
    });
  });

  describe("Word interaction", () => {
    it("should expand word chart when clicked", async () => {
      // Mock successful fetch response
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              lemma: "machine",
              pos: "NOUN",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "any mechanical device",
                    lemmas: ["machine"],
                    pos: "n",
                    offset: 123456,
                    domain: "engineering",
                  },
                ],
              },
              concepcy: {
                related_terms: [],
              },
            },
          ],
        }),
      });

      renderComponent();

      const machineButton = screen.getByText("machine");
      fireEvent.click(machineButton);

      // Should show loading state
      await waitFor(() => {
        expect(screen.getByText("Analyzing...")).toBeInTheDocument();
      });

      // Should show chart after loading
      await waitFor(() => {
        expect(screen.getByTestId("nlp-concept-chart")).toBeInTheDocument();
      });
    });

    it("should toggle expanded state when word clicked twice", async () => {
      renderComponent();

      const machineButton = screen.getByText("machine");

      // Click to expand
      fireEvent.click(machineButton);

      // Click again to collapse
      fireEvent.click(machineButton);

      // Should not show loading or chart
      expect(screen.queryByText("Analyzing...")).not.toBeInTheDocument();
    });

    it("should handle NLP analysis errors gracefully", async () => {
      (global.fetch as Mock).mockRejectedValueOnce(
        new Error("Network error")
      );

      renderComponent();

      const machineButton = screen.getByText("machine");
      fireEvent.click(machineButton);

      await waitFor(() => {
        expect(screen.getByText(/Error:/)).toBeInTheDocument();
      });
    });
  });

  describe("Sense selection", () => {
    it("should allow selecting a sense for a word", async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              lemma: "machine",
              pos: "NOUN",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "any mechanical device",
                    lemmas: ["machine"],
                    pos: "n",
                    offset: 123456,
                    domain: "engineering",
                  },
                ],
              },
              concepcy: { related_terms: [] },
            },
          ],
        }),
      });

      renderComponent();

      // Expand word
      const machineButton = screen.getByText("machine");
      fireEvent.click(machineButton);

      // Wait for chart to load
      await waitFor(() => {
        expect(screen.getByTestId("nlp-concept-chart")).toBeInTheDocument();
      });

      // Click sense selection button
      const senseButton = screen.getByText("Select Sense 0");
      fireEvent.click(senseButton);

      // Should show save button since we made a change
      await waitFor(() => {
        expect(screen.getByText("Save Word Senses")).toBeInTheDocument();
      });
    });

    it("should toggle sense selection when clicked twice", async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              lemma: "machine",
              pos: "NOUN",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "any mechanical device",
                    lemmas: ["machine"],
                    pos: "n",
                    offset: 123456,
                    domain: "engineering",
                  },
                ],
              },
              concepcy: { related_terms: [] },
            },
          ],
        }),
      });

      renderComponent();

      const machineButton = screen.getByText("machine");
      fireEvent.click(machineButton);

      await waitFor(() => {
        expect(screen.getByTestId("nlp-concept-chart")).toBeInTheDocument();
      });

      const senseButton = screen.getByText("Select Sense 0");

      // Select
      fireEvent.click(senseButton);
      await waitFor(() => {
        expect(screen.getByText("Save Word Senses")).toBeInTheDocument();
      });

      // Deselect
      fireEvent.click(senseButton);
      // Save button should disappear since we're back to original state
      await waitFor(() => {
        expect(screen.queryByText("Save Word Senses")).not.toBeInTheDocument();
      });
    });
  });

  describe("Save functionality", () => {
    it("should not show save button when no changes made", () => {
      renderComponent();

      expect(screen.queryByText("Save Word Senses")).not.toBeInTheDocument();
    });

    it("should show save button when selections differ from persisted", async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "device",
                    lemmas: [],
                    pos: "n",
                  },
                ],
              },
              concepcy: { related_terms: [] },
            },
          ],
        }),
      });

      renderComponent();

      const machineButton = screen.getByText("machine");
      fireEvent.click(machineButton);

      await waitFor(() => {
        expect(screen.getByTestId("nlp-concept-chart")).toBeInTheDocument();
      });

      const senseButton = screen.getByText("Select Sense 0");
      fireEvent.click(senseButton);

      await waitFor(() => {
        expect(screen.getByText("Save Word Senses")).toBeInTheDocument();
      });
    });

    it("should call save mutation with selected senses", async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              lemma: "machine",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "device",
                    lemmas: [],
                    pos: "n",
                    domain: "engineering",
                  },
                ],
              },
              concepcy: { related_terms: [] },
            },
          ],
        }),
      });

      renderComponent();

      const machineButton = screen.getByText("machine");
      fireEvent.click(machineButton);

      await waitFor(() => {
        expect(screen.getByTestId("nlp-concept-chart")).toBeInTheDocument();
      });

      const senseButton = screen.getByText("Select Sense 0");
      fireEvent.click(senseButton);

      await waitFor(() => {
        expect(screen.getByText("Save Word Senses")).toBeInTheDocument();
      });

      const saveButton = screen.getByText("Save Word Senses");
      fireEvent.click(saveButton);

      expect(mockUpdateWordSenses).toHaveBeenCalledWith({
        selected_senses: expect.arrayContaining([
          expect.objectContaining({
            term: "machine",
            sense_id: "machine.n.01",
          }),
        ]),
      });
    });

    it("should handle save errors", async () => {
      const { toast } = await import("@/utils/toast");

      // Create a new mock that will be used by the component instance
      const errorMockMutate = vi.fn();

      // Override the hook to return our custom mutation with onError handler
      vi.mocked(useWordSensesHook.useUpdateWordSenses).mockImplementation((nodeId, options) => {
        return {
          mutate: (variables: any) => {
            errorMockMutate(variables);
            // Trigger the error callback
            if (options?.onError) {
              options.onError(new Error("Save failed"), variables, undefined);
            }
          },
          isPending: false,
          isError: true,
          isSuccess: false,
          error: new Error("Save failed"),
          data: undefined,
          variables: undefined,
          context: undefined,
          failureCount: 1,
          failureReason: new Error("Save failed"),
          isIdle: false,
          isPaused: false,
          mutateAsync: vi.fn(),
          reset: vi.fn(),
          status: "error",
          submittedAt: Date.now(),
        } as any;
      });

      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "device",
                    lemmas: [],
                    pos: "n",
                  },
                ],
              },
              concepcy: { related_terms: [] },
            },
          ],
        }),
      });

      renderComponent();

      const machineButton = screen.getByText("machine");
      fireEvent.click(machineButton);

      await waitFor(() => {
        expect(screen.getByTestId("nlp-concept-chart")).toBeInTheDocument();
      });

      const senseButton = screen.getByText("Select Sense 0");
      fireEvent.click(senseButton);

      await waitFor(() => {
        expect(screen.getByText("Save Word Senses")).toBeInTheDocument();
      });

      const saveButton = screen.getByText("Save Word Senses");
      fireEvent.click(saveButton);

      // Error toast should be called
      await waitFor(() => {
        expect(toast.error).toHaveBeenCalled();
      });
    });
  });

  describe("Dirty tracking", () => {
    it("should not be dirty when initialized with persisted senses", () => {
      const persistedSenses: WordSense[] = [
        {
          term: "machine",
          sense_type: "wordnet",
          sense_id: "machine.n.01",
          definition: "device",
          domain: "engineering",
        },
      ];

      renderComponent({ persistedSenses });

      expect(screen.queryByText("Save Word Senses")).not.toBeInTheDocument();
    });

    it("should be dirty when number of selections changes", async () => {
      (global.fetch as Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "device",
                    lemmas: [],
                    pos: "n",
                  },
                ],
              },
              concepcy: { related_terms: [] },
            },
          ],
        }),
      });

      const persistedSenses: WordSense[] = [
        {
          term: "learning",
          sense_type: "wordnet",
          sense_id: "learning.n.01",
          definition: "acquiring knowledge",
          domain: null,
        },
      ];

      renderComponent({ persistedSenses });

      const machineButton = screen.getByText("machine");
      fireEvent.click(machineButton);

      await waitFor(() => {
        expect(screen.getByTestId("nlp-concept-chart")).toBeInTheDocument();
      });

      const senseButton = screen.getByText("Select Sense 0");
      fireEvent.click(senseButton);

      // Should be dirty since we added a new selection
      await waitFor(() => {
        expect(screen.getByText("Save Word Senses")).toBeInTheDocument();
      });
    });
  });
});
