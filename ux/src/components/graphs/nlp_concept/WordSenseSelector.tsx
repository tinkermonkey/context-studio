import React, { useState, useCallback, useMemo, useEffect } from "react";
import { Spinner } from "flowbite-react";
import { Save } from "lucide-react";
import { useUpdateWordSenses } from "@/api/hooks/structure_nodes/useWordSenses";
import { WordSense } from "@/api/types/structureNodes";
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

  // Consolidated state: all word-specific data in a single Map
  const [wordStates, setWordStates] = useState<Map<string, WordState>>(() => {
    const initialMap = new Map<string, WordState>();

    words.forEach((word) => {
      // Find persisted sense for this word
      const persistedSense = persistedSenses.find(
        (s) => s.term.toLowerCase() === word
      ) || null;

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
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());

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
        (s) => s.term.toLowerCase() === currentSense.term.toLowerCase()
      );

      if (!persistedSense || persistedSense.sense_id !== currentSense.sense_id) {
        return true;
      }
    }

    return false;
  }, [wordStates, persistedSenses]);

  // Mutation hook for saving word senses
  const updateWordSensesMutation = useUpdateWordSenses(nodeId, {
    onSuccess: () => {
      toast.success("Word senses saved successfully");
      onSaveComplete?.();
    },
    onError: (error) => {
      toast.error(`Failed to save word senses: ${error.message}`);
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

  // Handle sense selection for a word
  const handleSenseSelect = useCallback((word: string, synset: any) => {
    // Create WordSense from synset
    const wordSense: WordSense = {
      term: word,
      sense_type: "wordnet",
      sense_id: synset.name,
      definition: synset.definition,
      domain: synset.domain || null,
    };

    setWordStates((prev) => {
      const next = new Map(prev);
      const state = next.get(word);

      if (!state) return prev;

      // Toggle: if same sense clicked, deselect it
      const newSense =
        state.selectedSense?.sense_id === wordSense.sense_id ? null : wordSense;

      next.set(word, {
        ...state,
        selectedSense: newSense,
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
          state.selectedSense?.sense_id === wordSense.sense_id ? null : wordSense;

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
    const analyzeWord = async (word: string, state: WordState) => {
      try {
        const response = await fetch(
          `/api/nlp/analyze?text=${encodeURIComponent(word)}`
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
        analyzeWord(word, state);
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
        className={`rounded-lg border-2 p-3 transition-all ${borderColorClass} ${bgColorClass}`}
      >
        {/* Word header - clickable to expand */}
        <button
          onClick={() => handleWordClick(word)}
          className="mb-2 w-full text-left font-semibold text-gray-800 hover:text-blue-600"
        >
          {word}
          {state.selectedSense && (
            <span className="ml-2 rounded-full bg-blue-600 px-2 py-0.5 text-xs text-white">
              {state.selectedSense.sense_id}
            </span>
          )}
        </button>

        {/* Show analysis when expanded */}
        {state.isExpanded && (
          <div className="mt-2">
            {state.isAnalyzing && (
              <div className="flex items-center gap-2">
                <Spinner size="sm" />
                <span className="text-sm text-gray-600">Analyzing...</span>
              </div>
            )}

            {state.error && (
              <div className="text-sm text-red-600">
                Error: {state.error.message}
              </div>
            )}

            {state.analysis && (
              <NlpConceptChart
                data={{
                  text: state.analysis.text,
                  lemma: state.analysis.lemma || state.analysis.text,
                  pos: state.analysis.pos || state.analysis.tag || "",
                  concepcy: {
                    related_terms: state.analysis.concepcy?.related_terms || [],
                  },
                  wordnet: {
                    synsets: (state.analysis.wordnet?.synsets || []).map((s: any) => ({
                      name: s.name || s.synset || s.id || s[0] || "unknown",
                      definition: s.definition || s.gloss || s.def || "",
                      lemmas: s.lemmas || [],
                      pos: s.pos || s.partOfSpeech || state.analysis?.pos || "",
                      offset: s.offset || 0,
                      domain: s.domain || "general",
                    })),
                    definitions: (state.analysis.wordnet?.synsets || []).map(
                      (s: any) => s.definition || s.gloss || s.def || ""
                    ),
                  },
                }}
                config={{
                  RelatedTo: 2,
                  IsA: 3,
                  HasA: 2,
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
    <div className="space-y-4">
      {/* Save button - only show when dirty */}
      {isDirty && (
        <div className="flex items-center justify-end">
          <button
            onClick={handleSave}
            disabled={isSaving || !updateWordSensesMutation}
            className="inline-flex items-center rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? (
              <>
                <Spinner size="sm" className="mr-2" />
                Saving...
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save Word Senses
              </>
            )}
          </button>
        </div>
      )}

      {/* Multi-word chart display with responsive grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
        {words.map(renderWordChart)}
      </div>

      {/* Helper text */}
      <div className="text-xs text-gray-500">
        Click a word to view and select its senses. Selected senses will be saved for this term.
      </div>
    </div>
  );
};

export default WordSenseSelector;
