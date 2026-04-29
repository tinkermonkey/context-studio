import React, { useState, useCallback, useMemo, useEffect } from "react";
import { Spinner } from "flowbite-react";
import { Save } from "lucide-react";
import { useUpdateWordSenses } from "@/api/hooks/ontologyClasss/useWordSenses";
import { WordSense } from "@/api/types/ontologyClasss";
import { toast } from "@/utils/toast";
import NlpConceptChart from "./NlpConceptChart";

interface WordSenseSelectorProps {
  /** Structure node title to parse into words */
  title: string;
  /** Initial selected senses from persisted data */
  persistedSenses: WordSense[];
  /** Structure node ID for save operations */
  nodeId: string;
  /** Optional callback when save completes */
  onSaveComplete?: () => void;
}

/** Type definition for NLP analysis results */
interface WordAnalysisResult {
  text: string;
  lemma?: string;
  pos?: string;
  tag?: string;
  concepcy?: {
     
    related_terms: any[];
  };
  wordnet?: {
     
    synsets: any[];
  };
}

/** Combined state for each word containing all word-specific data */
interface WordState {
  word: string;
  analysis: WordAnalysisResult | null;
  isAnalyzing: boolean;
  error: Error | null;
  selectedSense: WordSense | null;
  isExpanded: boolean;
}

/**
 * WordSenseSelector displays NLP concept charts for all words in a title.
 * Supports interactive sense selection per word with persistent storage.
 */
export const WordSenseSelector: React.FC<WordSenseSelectorProps> = ({
  title,
  persistedSenses,
  nodeId,
  onSaveComplete,
}) => {
  // Parse title into individual words (split on whitespace, remove empty strings)
  const words = useMemo(() => {
    return title
      .split(/\s+/)
      .filter((w) => w.length > 0)
      .map((w) => w.toLowerCase());
  }, [title]);

  // Ref for focus management
  const saveButtonRef = React.useRef<HTMLButtonElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);

  // Consolidated state: all word-specific data in a single Map
  const [wordStates, setWordStates] = useState<Map<string, WordState>>(() => {
    const initialMap = new Map<string, WordState>();

    words.forEach((word) => {
      // Find persisted sense for this word
      const persistedSense =
        persistedSenses.find((s) => s.term.toLowerCase() === word) || null;

      initialMap.set(word, {
        word,
        analysis: null,
        isAnalyzing: false,
        error: null,
        selectedSense: persistedSense,
        isExpanded: false,
      });
    });

    return initialMap;
  });

  // State: selected node IDs for chart interaction visual feedback
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(
    new Set(),
  );

  // Compute dirty flag by comparing current selections with persisted
  const isDirty = useMemo(() => {
    const currentSelections = Array.from(wordStates.values())
      .filter((state) => state.selectedSense !== null)
      .map((state) => state.selectedSense!);

    // Check if number of selections changed
    if (currentSelections.length !== persistedSenses.length) {
      return true;
    }

    // Check if any selection changed
    for (const currentSense of currentSelections) {
      const persistedSense = persistedSenses.find(
        (s) => s.term.toLowerCase() === currentSense.term.toLowerCase(),
      );

      if (
        !persistedSense ||
        persistedSense.sense_id !== currentSense.sense_id
      ) {
        return true;
      }
    }

    return false;
  }, [wordStates, persistedSenses]);

  // Mutation hook for saving word senses
  const updateWordSensesMutation = useUpdateWordSenses(nodeId, {
    onSuccess: () => {
      toast.success("Word senses saved successfully");

      // Return focus to container after save
      setTimeout(() => {
        containerRef.current?.focus();
      }, 100);

      onSaveComplete?.();
    },
    onError: (error: Error) => {
      toast.error(`Failed to save word senses: ${error.message}`);

      // Return focus to save button on error
      setTimeout(() => {
        saveButtonRef.current?.focus();
      }, 100);
    },
  });

  const isSaving = updateWordSensesMutation?.isPending ?? false;

  // Handle word click - toggle expand to show senses
  const handleWordClick = useCallback((word: string) => {
    setWordStates((prev) => {
      const next = new Map(prev);
      const state = next.get(word);

      if (!state) return prev;

      const isCurrentlyExpanded = state.isExpanded;

      // Toggle expansion
      next.set(word, {
        ...state,
        isExpanded: !isCurrentlyExpanded,
        // Trigger analysis if expanding and not yet analyzed
        isAnalyzing: !isCurrentlyExpanded && !state.analysis && !state.error,
      });

      return next;
    });
  }, []);

  // Handle node click in the chart (for sense selection)
  const handleNodeClick = useCallback((word: string, nodeId: string) => {
    // Parse node ID to determine if it's a sense node
    if (nodeId.startsWith("sense-")) {
      const senseIndex = parseInt(nodeId.replace("sense-", ""), 10);

      setWordStates((prev) => {
        const state = prev.get(word);
        if (!state?.analysis?.wordnet?.synsets?.[senseIndex]) {
          return prev;
        }

        const synset = state.analysis.wordnet.synsets[senseIndex];

        // Use handleSenseSelect to update the state
        const next = new Map(prev);
        const wordSense: WordSense = {
          term: word,
          sense_type: "wordnet",
          sense_id: synset.name,
          definition: synset.definition,
          domain: synset.domain || null,
        };

        const newSense =
          state.selectedSense?.sense_id === wordSense.sense_id
            ? null
            : wordSense;

        next.set(word, {
          ...state,
          selectedSense: newSense,
        });

        return next;
      });
    }

    // Update selected node IDs for visual feedback
    setSelectedNodeIds((prev) => {
      const next = new Set(prev);
      const fullNodeId = `${word}-${nodeId}`;

      if (next.has(fullNodeId)) {
        next.delete(fullNodeId);
      } else {
        next.add(fullNodeId);
      }

      return next;
    });
  }, []);

  // Handle save button click
  const handleSave = useCallback(() => {
    if (!updateWordSensesMutation) return;

    // Collect all selected senses (excluding null values)
    const sensesToSave: WordSense[] = Array.from(wordStates.values())
      .map((state) => state.selectedSense)
      .filter((sense): sense is WordSense => sense !== null);

    updateWordSensesMutation.mutate({
      selected_senses: sensesToSave,
    });
  }, [wordStates, updateWordSensesMutation]);

  // Effect: Perform NLP analysis for words that need it
  useEffect(() => {
    const analyzeWord = async (word: string) => {
      try {
        const response = await fetch(
          `/api/nlp/analyze?text=${encodeURIComponent(word)}`,
        );

        if (!response.ok) {
          throw new Error(`Analysis failed: ${response.statusText}`);
        }

        const result = await response.json();
        const tokenData = result.tokens?.[0]; // Get first token

        setWordStates((prev) => {
          const next = new Map(prev);
          const currentState = next.get(word);

          if (!currentState) return prev;

          next.set(word, {
            ...currentState,
            analysis: tokenData,
            isAnalyzing: false,
            error: null,
          });

          return next;
        });
      } catch (error) {
        setWordStates((prev) => {
          const next = new Map(prev);
          const currentState = next.get(word);

          if (!currentState) return prev;

          next.set(word, {
            ...currentState,
            analysis: null,
            isAnalyzing: false,
            error: error as Error,
          });

          return next;
        });

        // Show error toast to user
        toast.error(`Failed to analyze "${word}": ${(error as Error).message}`);
      }
    };

    // Check if any word needs analysis
    for (const [word, state] of wordStates.entries()) {
      if (state.isAnalyzing && !state.analysis) {
        analyzeWord(word);
      }
    }
  }, [wordStates]);

  // Render individual word chart
  const renderWordChart = (word: string) => {
    const state = wordStates.get(word);

    if (!state) return null;

    // Get selected node IDs for this word
    const wordSelectedNodeIds = useMemo(() => {
      const ids = new Set<string>();
      for (const id of selectedNodeIds) {
        if (id.startsWith(`${word}-`)) {
          ids.add(id.substring(word.length + 1));
        }
      }
      return ids;
    }, [selectedNodeIds, word]);

    // Determine border and background color based on state
    const borderColorClass = state.isExpanded
      ? "border-blue-500"
      : state.selectedSense
        ? "border-blue-300"
        : "border-gray-300";

    const bgColorClass = state.selectedSense ? "bg-blue-50" : "bg-gray-50";

    return (
      <div
        key={word}
        className={`rounded-lg border-2 p-3 transition-all duration-300 ease-in-out ${borderColorClass} ${bgColorClass}`}
        role="region"
        aria-label={`Word sense for ${word}`}
      >
        {/* Word header - clickable to expand */}
        <button
          onClick={() => handleWordClick(word)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              handleWordClick(word);
            }
          }}
          className="mb-2 w-full text-left font-semibold text-gray-800 transition-colors duration-200 hover:text-blue-600 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none"
          aria-expanded={state.isExpanded}
          aria-controls={`word-sense-${word}`}
          aria-label={`${state.isExpanded ? "Collapse" : "Expand"} sense options for ${word}${state.selectedSense ? `, currently selected: ${state.selectedSense.sense_id}` : ""}`}
        >
          {word}
          {state.selectedSense && (
            <span
              className="ml-2 rounded-full bg-blue-600 px-2 py-0.5 text-xs text-white"
              aria-label="Selected sense"
            >
              {state.selectedSense.sense_id}
            </span>
          )}
        </button>

        {/* Show analysis when expanded */}
        {state.isExpanded && (
          <div
            className="animate-fade-in mt-2"
            id={`word-sense-${word}`}
            role="region"
            aria-live="polite"
          >
            {state.isAnalyzing && (
              <div
                className="flex items-center gap-2"
                role="status"
                aria-label="Loading word sense analysis"
              >
                <Spinner size="sm" aria-hidden="true" />
                <span className="text-sm text-gray-600">Analyzing...</span>
              </div>
            )}

            {state.error && (
              <div
                className="text-sm text-red-600"
                role="alert"
                aria-live="assertive"
              >
                Error: {state.error.message}
              </div>
            )}

            {state.analysis && (
              <NlpConceptChart
                data={{
                  text: state.analysis.text,
                  lemma: state.analysis.lemma || state.analysis.text,
                  pos: state.analysis.pos || state.analysis.tag || "",
                  inputTerm: state.analysis.text,
                  wordnet: {
                    synsets: (state.analysis.wordnet?.synsets || []).map(
                       
                      (s: any) => ({
                        name: s.name || s.synset || s.id || s[0] || "unknown",
                        definition: s.definition || s.gloss || s.def || "",
                        lemmas: s.lemmas || [],
                        pos:
                          s.pos || s.partOfSpeech || state.analysis?.pos || "",
                        offset: s.offset || 0,
                        domain: s.domain || "general",
                      }),
                    ),
                  },
                }}
                onNodeClick={(nodeId) => handleNodeClick(word, nodeId)}
                selectedNodeIds={wordSelectedNodeIds}
              />
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      className="space-y-4"
      ref={containerRef}
      tabIndex={-1}
      aria-label="Word sense selector"
    >
      {/* Save button - only show when dirty */}
      {isDirty && (
        <div
          className="flex items-center justify-end"
          role="region"
          aria-label="Save actions"
        >
          <button
            ref={saveButtonRef}
            onClick={handleSave}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleSave();
              }
            }}
            disabled={isSaving || !updateWordSensesMutation}
            className="inline-flex items-center rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white transition-colors duration-200 hover:bg-blue-800 focus:ring-4 focus:ring-blue-300 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={isSaving ? "Saving word senses" : "Save word senses"}
            aria-busy={isSaving}
          >
            {isSaving ? (
              <>
                <Spinner size="sm" className="mr-2" aria-hidden="true" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" aria-hidden="true" />
                Save Word Senses
              </>
            )}
          </button>
        </div>
      )}

      {/* Multi-word chart display with responsive grid */}
      <div
        className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        role="list"
        aria-label={`Word senses for ${words.length} word${words.length > 1 ? "s" : ""}`}
      >
        {words.map(renderWordChart)}
      </div>

      {/* Helper text */}
      <div className="text-xs text-gray-500" role="status" aria-live="polite">
        Click a word to view and select its senses. Use Tab to navigate between
        words and Enter or Space to expand. Selected senses will be saved for
        this term.
      </div>
    </div>
  );
};

export default WordSenseSelector;
