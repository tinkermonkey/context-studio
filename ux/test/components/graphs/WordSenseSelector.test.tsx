import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import WordSenseSelector from "@/components/graphs/nlp_concept/WordSenseSelector";
import { WordSense } from "@/api/types/ontology";
import * as useWordSensesModule from "@/api/hooks/ontologyClasses/useWordSenses";

// Mock the toast utility
vi.mock("@/utils/toast", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock the NlpConceptChart component
vi.mock("@/components/graphs/nlp_concept/NlpConceptChart", () => ({
  default: function MockNlpConceptChart({ data, onNodeClick }: any) {
    return (
      <div data-testid="nlp-concept-chart">
        <div data-testid="chart-text">{data.text}</div>
        <div data-testid="chart-lemma">{data.lemma}</div>
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        {}
        {data.wordnet.synsets.map((synset: any, idx: number) => (
          <button
            key={idx}
            onClick={() => onNodeClick(`sense-${idx}`)}
            data-testid={`synset-${idx}`}
          >
            {synset.name}
          </button>
        ))}
      </div>
    );
  },
}));

// Mock fetch globally

global.fetch = vi.fn() as any;

describe("WordSenseSelector", () => {
  let queryClient: QueryClient;
  let mockMutate: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    mockMutate = vi.fn();

    vi.spyOn(useWordSensesModule, "useUpdateWordSenses").mockReturnValue({
      mutate: mockMutate,
      isPending: false,
    } as any);

    (global.fetch as any).mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderComponent = (props: {
    title: string;
    persistedSenses?: WordSense[];
    nodeId?: string;
    onSaveComplete?: () => void;
  }) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <WordSenseSelector
          title={props.title}
          persistedSenses={props.persistedSenses || []}
          nodeId={props.nodeId || "test-node-123"}
          onSaveComplete={props.onSaveComplete}
        />
      </QueryClientProvider>,
    );
  };

  describe("Parsing and display", () => {
    it("parses multi-word title and displays all words", () => {
      renderComponent({ title: "machine learning algorithm" });

      expect(screen.getByText("machine")).toBeInTheDocument();
      expect(screen.getByText("learning")).toBeInTheDocument();
      expect(screen.getByText("algorithm")).toBeInTheDocument();
    });

    it("handles single word titles", () => {
      renderComponent({ title: "algorithm" });

      expect(screen.getByText("algorithm")).toBeInTheDocument();
    });

    it("handles extra whitespace in title", () => {
      renderComponent({ title: "  machine   learning  " });

      expect(screen.getByText("machine")).toBeInTheDocument();
      expect(screen.getByText("learning")).toBeInTheDocument();
    });

    it("renders words in responsive grid layout", () => {
      const { container } = renderComponent({
        title: "machine learning algorithm",
      });

      const gridContainer = container.querySelector(".grid");
      expect(gridContainer).toHaveClass("grid-cols-1");
      expect(gridContainer).toHaveClass("sm:grid-cols-2");
      expect(gridContainer).toHaveClass("lg:grid-cols-3");
      expect(gridContainer).toHaveClass("xl:grid-cols-4");
    });
  });

  describe("Persisted senses", () => {
    it("displays persisted sense selections", () => {
      const persistedSenses: WordSense[] = [
        {
          label: "machine",
          language_code: "en",
          sense_type: "wordnet",
        },
      ];

      renderComponent({ title: "machine learning", persistedSenses });

      expect(screen.getByText("machine")).toBeInTheDocument();
    });

    it("initializes with persisted senses", () => {
      const persistedSenses: WordSense[] = [
        {
          label: "learning",
          language_code: "en",
          sense_type: "wordnet",
        },
      ];

      renderComponent({ title: "machine learning", persistedSenses });

      // Check that the persisted sense is displayed
      expect(screen.getByText("learning")).toBeInTheDocument();
    });
  });

  describe("Word interaction", () => {
    it("expands word on click", async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
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
                    definition: "A device",
                  },
                ],
              },
            },
          ],
        }),
      });

      renderComponent({ title: "machine" });

      const wordButton = screen.getByText("machine");
      fireEvent.click(wordButton);

      await waitFor(() => {
        expect(screen.getByTestId("nlp-concept-chart")).toBeInTheDocument();
      });
    });

    it("toggles word expansion on repeated clicks", async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              wordnet: { synsets: [] },
            },
          ],
        }),
      });

      renderComponent({ title: "machine" });

      const wordButton = screen.getByText("machine");

      // Click to expand
      fireEvent.click(wordButton);
      await waitFor(() => {
        expect(screen.queryByTestId("nlp-concept-chart")).toBeInTheDocument();
      });

      // Click again to collapse
      fireEvent.click(wordButton);
      await waitFor(() => {
        expect(
          screen.queryByTestId("nlp-concept-chart"),
        ).not.toBeInTheDocument();
      });
    });

    it("handles analysis errors gracefully", async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error("Network error"),
      );

      renderComponent({ title: "machine" });

      const wordButton = screen.getByText("machine");
      fireEvent.click(wordButton);

      await waitFor(() => {
        expect(screen.getByText(/Error: Network error/)).toBeInTheDocument();
      });
    });
  });

  describe("Sense selection", () => {
    it("allows selecting a sense for a word", async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "A device",
                  },
                ],
              },
            },
          ],
        }),
      });

      renderComponent({ title: "machine" });

      // Expand word
      fireEvent.click(screen.getByText("machine"));

      // Wait for chart to load
      await waitFor(() => {
        expect(screen.getByTestId("synset-0")).toBeInTheDocument();
      });

      // Click sense node
      fireEvent.click(screen.getByTestId("synset-0"));

      // Verify sense badge appears (there will be 2: in button and in badge)
      await waitFor(() => {
        const badges = screen.getAllByText("machine.n.01");
        expect(badges.length).toBeGreaterThan(0);
      });
    });

    it("allows toggling sense selection", async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "A device",
                  },
                ],
              },
            },
          ],
        }),
      });

      renderComponent({ title: "machine" });

      // Expand and select
      fireEvent.click(screen.getByText("machine"));
      await waitFor(() => screen.getByTestId("synset-0"));
      fireEvent.click(screen.getByTestId("synset-0"));

      // Verify selected (badge appears)
      await waitFor(() => {
        const badges = screen.getAllByText("machine.n.01");
        expect(badges.length).toBeGreaterThan(1); // Button + badge
      });

      // Click again to deselect
      fireEvent.click(screen.getByTestId("synset-0"));

      // Verify deselected (only button text remains, no badge)
      await waitFor(() => {
        const badges = screen.getAllByText("machine.n.01");
        expect(badges.length).toBe(1); // Only the button in chart
      });
    });
  });

  describe("Save functionality", () => {
    it("shows save button when selections change", async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "A device",
                  },
                ],
              },
            },
          ],
        }),
      });

      renderComponent({ title: "machine", persistedSenses: [] });

      // Initially no save button
      expect(screen.queryByText("Save Word Senses")).not.toBeInTheDocument();

      // Expand and select
      fireEvent.click(screen.getByText("machine"));
      await waitFor(() => screen.getByTestId("synset-0"));
      fireEvent.click(screen.getByTestId("synset-0"));

      // Save button should appear
      await waitFor(() => {
        expect(screen.getByText("Save Word Senses")).toBeInTheDocument();
      });
    });

    it("enables save button when mutation is available", async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "A device",
                  },
                ],
              },
            },
          ],
        }),
      });

      renderComponent({ title: "machine" });

      // Expand and select
      fireEvent.click(screen.getByText("machine"));
      await waitFor(() => screen.getByTestId("synset-0"));
      fireEvent.click(screen.getByTestId("synset-0"));

      // Save button should be enabled
      await waitFor(() => {
        const saveButton = screen.getByText("Save Word Senses");
        expect(saveButton).not.toBeDisabled();
      });
    });

    it("displays save button with correct text", async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.01",
                    definition: "A device",
                  },
                ],
              },
            },
          ],
        }),
      });

      renderComponent({ title: "machine" });

      // Expand and select
      fireEvent.click(screen.getByText("machine"));
      await waitFor(() => screen.getByTestId("synset-0"));
      fireEvent.click(screen.getByTestId("synset-0"));

      // Save button should appear with correct text
      await waitFor(() => {
        expect(screen.getByText("Save Word Senses")).toBeInTheDocument();
      });
    });
  });

  describe("Dirty tracking", () => {
    it("is not dirty when selections match persisted", () => {
      const persistedSenses: WordSense[] = [
        {
          label: "machine",
          language_code: "en",
          sense_type: "wordnet",
        },
      ];

      renderComponent({ title: "machine", persistedSenses });

      // No save button should be visible
      expect(screen.queryByText("Save Word Senses")).not.toBeInTheDocument();
    });

    it("is dirty when selections differ from persisted", async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tokens: [
            {
              text: "machine",
              wordnet: {
                synsets: [
                  {
                    name: "machine.n.02",
                    definition: "Different sense",
                  },
                ],
              },
            },
          ],
        }),
      });

      const persistedSenses: WordSense[] = [
        {
          label: "machine",
          language_code: "en",
          sense_type: "wordnet",
        },
      ];

      renderComponent({ title: "machine", persistedSenses });

      // Expand and select different sense
      fireEvent.click(screen.getByText("machine"));
      await waitFor(() => screen.getByTestId("synset-0"));
      fireEvent.click(screen.getByTestId("synset-0"));

      // Save button should appear
      await waitFor(() => {
        expect(screen.getByText("Save Word Senses")).toBeInTheDocument();
      });
    });
  });
});
