import React, { useState, useCallback, useMemo, useEffect } from "react";
import { Button, Spinner } from "flowbite-react";
import { Save } from "lucide-react";
import { useNLPAnalysis } from "@/api/hooks/nlp/useNLPAnalysis";
import { useUpdateWordSenses } from "@/api/hooks/structure_nodes/useWordSenses";
import { WordSense } from "@/api/types/structureNodes";
import { toast } from "@/utils/toast";
import NlpConceptChart from "./NlpConceptChart";

interface MultiWordNlpConceptChartProps {
  /** Structure node title to parse into words */
  title: string;
  /** Initial selected senses from persisted data */
  persistedSenses: WordSense[];
  /** Structure node ID for save operations */
  nodeId: string;
  /** Optional callback when save completes */
  onSaveComplete?: () => void;
}

interface WordAnalysis {
  word: string;
  data: any | null;
  isLoading: boolean;
  error: Error | null;
}

/**
 * MultiWordNlpConceptChart displays NLP concept charts for all words in a title.
 * Supports interactive sense selection per word with persistent storage.
 */
export const MultiWordNlpConceptChart: React.FC<MultiWordNlpConceptChartProps> = ({
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

  // State: selected senses per word (word -> WordSense | null)
  const [selectedSenses, setSelectedSenses] = useState<Map<string, WordSense | null>>(() => {
    const initialMap = new Map<string, WordSense | null>();

    // Initialize with persisted senses
    persistedSenses.forEach((sense) => {
      initialMap.set(sense.term.toLowerCase(), sense);
    });

    return initialMap;
  });

  // State: available senses per word from NLP analysis (word -> WordSense[])
  const [availableSenses, setAvailableSenses] = useState<Map<string, any>>(new Map());

  // State: analysis status per word
  const [wordAnalyses, setWordAnalyses] = useState<Map<string, WordAnalysis>>(() => {
    const initialMap = new Map<string, WordAnalysis>();
    words.forEach((word) => {
      initialMap.set(word, {
        word,
        data: null,
        isLoading: false,
        error: null,
      });
    });
    return initialMap;
  });

  // State: currently active/expanded word
  const [activeWord, setActiveWord] = useState<string | null>(null);

  // State: selected node IDs for chart interaction
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(new Set());

  // Compute dirty flag by comparing current selections with persisted
  const isDirty = useMemo(() => {
    // Check if number of selections changed
    const currentSelections = Array.from(selectedSenses.entries()).filter(
      ([_, sense]) => sense !== null
    );

    if (currentSelections.length !== persistedSenses.length) {
      return true;
    }

    // Check if any selection changed
    for (const [word, currentSense] of currentSelections) {
      const persistedSense = persistedSenses.find(
        (s) => s.term.toLowerCase() === word
      );

      if (!persistedSense || persistedSense.sense_id !== currentSense?.sense_id) {
        return true;
      }
    }

    return false;
  }, [selectedSenses, persistedSenses]);

  // Mutation hook for saving word senses
  const { mutate: saveWordSenses, isPending: isSaving } = useUpdateWordSenses(nodeId, {
    onSuccess: () => {
      toast.success("Word senses saved successfully");
      onSaveComplete?.();
    },
    onError: (error) => {
      toast.error(`Failed to save word senses: ${error.message}`);
    },
  });

  // Handle word click - expand to show senses
  const handleWordClick = useCallback((word: string) => {
    setActiveWord((current) => (current === word ? null : word));

    // Trigger NLP analysis if not already analyzed
    const analysis = wordAnalyses.get(word);
    if (analysis && !analysis.data && !analysis.isLoading && !analysis.error) {
      // Mark as loading
      setWordAnalyses((prev) => {
        const next = new Map(prev);
        next.set(word, { ...analysis, isLoading: true });
        return next;
      });
    }
  }, [wordAnalyses]);

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

    setSelectedSenses((prev) => {
      const next = new Map(prev);
      const currentSense = next.get(word);

      // Toggle: if same sense clicked, deselect it
      if (currentSense?.sense_id === wordSense.sense_id) {
        next.set(word, null);
      } else {
        next.set(word, wordSense);
      }

      return next;
    });
  }, []);

  // Handle node click in the chart (for sense selection)
  const handleNodeClick = useCallback((word: string, nodeId: string) => {
    // Parse node ID to determine if it's a sense node
    if (nodeId.startsWith("sense-")) {
      const senseIndex = parseInt(nodeId.replace("sense-", ""), 10);
      const analysis = wordAnalyses.get(word);

      if (analysis?.data?.wordnet?.synsets?.[senseIndex]) {
        const synset = analysis.data.wordnet.synsets[senseIndex];
        handleSenseSelect(word, synset);
      }
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
  }, [wordAnalyses, handleSenseSelect]);

  // Handle save button click
  const handleSave = useCallback(() => {
    // Collect all selected senses (excluding null values)
    const sensesToSave: WordSense[] = Array.from(selectedSenses.values()).filter(
      (sense): sense is WordSense => sense !== null
    );

    saveWordSenses({
      selected_senses: sensesToSave,
    });
  }, [selectedSenses, saveWordSenses]);

  // Custom hook instance for each word - we'll manage them individually
  // For now, we'll use a simpler approach with direct API calls
  useEffect(() => {
    const analyzeWord = async (word: string) => {
      const analysis = wordAnalyses.get(word);
      if (!analysis || analysis.data || !analysis.isLoading) {
        return;
      }

      try {
        // Use the NLP analysis hook indirectly by fetching
        const response = await fetch(
          `/api/nlp/analyze?text=${encodeURIComponent(word)}`
        );

        if (!response.ok) {
          throw new Error(`Analysis failed: ${response.statusText}`);
        }

        const result = await response.json();
        const tokenData = result.tokens?.[0]; // Get first token

        setWordAnalyses((prev) => {
          const next = new Map(prev);
          next.set(word, {
            word,
            data: tokenData,
            isLoading: false,
            error: null,
          });
          return next;
        });

        // Cache the analysis data
        setAvailableSenses((prev) => {
          const next = new Map(prev);
          next.set(word, tokenData);
          return next;
        });
      } catch (error) {
        setWordAnalyses((prev) => {
          const next = new Map(prev);
          next.set(word, {
            word,
            data: null,
            isLoading: false,
            error: error as Error,
          });
          return next;
        });
      }
    };

    // Check if any word needs analysis
    for (const [word, analysis] of wordAnalyses.entries()) {
      if (analysis.isLoading && !analysis.data) {
        analyzeWord(word);
      }
    }
  }, [wordAnalyses]);

  // Render individual word chart
  const renderWordChart = (word: string) => {
    const analysis = wordAnalyses.get(word);
    const isActive = activeWord === word;
    const selectedSense = selectedSenses.get(word);

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

    // Determine background color based on state
    const bgColorClass = selectedSense
      ? "bg-blue-50 border-blue-300"
      : "bg-gray-50 border-gray-300";

    return (
      <div
        key={word}
        className={`rounded-lg border-2 p-3 transition-all ${isActive ? "border-blue-500" : bgColorClass}`}
      >
        {/* Word header - clickable to expand */}
        <button
          onClick={() => handleWordClick(word)}
          className="mb-2 w-full text-left font-semibold text-gray-800 hover:text-blue-600"
        >
          {word}
          {selectedSense && (
            <span className="ml-2 text-xs text-blue-600">
              ({selectedSense.sense_id})
            </span>
          )}
        </button>

        {/* Show analysis when active */}
        {isActive && (
          <div className="mt-2">
            {analysis?.isLoading && (
              <div className="flex items-center gap-2">
                <Spinner size="sm" />
                <span className="text-sm text-gray-600">Analyzing...</span>
              </div>
            )}

            {analysis?.error && (
              <div className="text-sm text-red-600">
                Error: {analysis.error.message}
              </div>
            )}

            {analysis?.data && (
              <NlpConceptChart
                data={{
                  text: analysis.data.text,
                  lemma: analysis.data.lemma || analysis.data.text,
                  pos: analysis.data.pos || analysis.data.tag || "",
                  concepcy: {
                    related_terms: analysis.data.concepcy?.related_terms || [],
                  },
                  wordnet: {
                    synsets: (analysis.data.wordnet?.synsets || []).map((s: any) => ({
                      name: s.name || s.synset || s.id || s[0] || "unknown",
                      definition: s.definition || s.gloss || s.def || "",
                      lemmas: s.lemmas || [],
                      pos: s.pos || s.partOfSpeech || analysis.data.pos || "",
                      offset: s.offset || 0,
                      domain: s.domain || "general",
                    })),
                    definitions: (analysis.data.wordnet?.synsets || []).map(
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
          <Button
            onClick={handleSave}
            disabled={isSaving}
            size="sm"
            color="blue"
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
          </Button>
        </div>
      )}

      {/* Multi-word chart display */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {words.map(renderWordChart)}
      </div>

      {/* Helper text */}
      <div className="text-xs text-gray-500">
        Click a word to view and select its senses. Selected senses will be saved for this term.
      </div>
    </div>
  );
};

export default MultiWordNlpConceptChart;
