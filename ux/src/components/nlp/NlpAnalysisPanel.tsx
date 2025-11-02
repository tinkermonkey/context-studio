import * as React from "react";
import { useState, useEffect, useCallback, useRef } from "react";
import {
  Button,
  Spinner,
  Accordion,
  AccordionPanel,
  AccordionTitle,
  AccordionContent,
} from "flowbite-react";
import { useNLPAnalysis } from "@/api/hooks/nlp/useNLPAnalysis";
import { apiLogger } from "@/api/utils/logger";
import { NlpTokenAnalysisPanel } from "@/components/nlp/NlpTokenAnalysisPanel";
import { NlpRefinementPanel } from "@/components/nlp/NlpRefinementPanel";
import { NlpGenerationResult } from "@/components/nlp/NlpGenerationResult";
import { useNlpAnalysisStore } from "@/stores/nlpAnalysisStore";
import type {
  NodeContext,
  SelectedNodeContextEntry,
} from "@/components/nlp/types";

interface NlpAnalysisPanelProps {
  text: string;
  textTitle?: string | null;
  domainContext?: {
    title: string;
    definition: string;
  } | null;
  parentTermContext?: {
    title: string;
    definition: string;
    relationshipPredicate?: string;
  } | null;
  currentDefinition?: string | null;
  // Context IDs for saving definitions
  termId?: string | null;
  domainId?: string | null;
  layerId?: string | null;
  // Optional list of pipeline flavor IDs to use instead of enabled flavors
  flavorList?: string[] | null;
}

export const NlpAnalysisPanel: React.FC<NlpAnalysisPanelProps> = ({
  text,
  textTitle = null,
  domainContext = null,
  parentTermContext = null,
  currentDefinition = null,
  termId = null,
  domainId = null,
  layerId = null,
  flavorList = null,
}) => {
  // Subscribe to the NLP analysis store
  const { shouldAnalyze, currentText, reset } = useNlpAnalysisStore();
  const [hasAnalyzed, setHasAnalyzed] = useState(false);

  // Custom hook for API call
  const lowercasedText = text.toLowerCase();
  const queryKey = [
    "nlp",
    "analysis",
    JSON.stringify({ text: lowercasedText }),
  ];
  const {
    data: analysisResult,
    isLoading: loading,
    error,
    refetch,
  } = useNLPAnalysis(lowercasedText, {
    enabled: false,
    queryKey,
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes
    cacheTime: 1000 * 60 * 30, // Keep in cache for 30 minutes
  });

  // Watch for analyze trigger from store
  useEffect(() => {
    if (shouldAnalyze && currentText.toLowerCase() === lowercasedText) {
      setHasAnalyzed(true);
      refetch();
      reset(); // Reset the trigger
      apiLogger.info("NLP analysis triggered from store", { text });
    }
  }, [shouldAnalyze, currentText, lowercasedText, refetch, reset, text]);

  // Error handling
  useEffect(() => {
    if (error) {
      apiLogger.error("NLP analysis error", { error });
    }
  }, [error]);

  // selected nodes from the embedded charts - single source of truth
  const [selectedNodeIds, setSelectedNodeIds] = useState<Set<string>>(
    new Set(),
  );
  const [selectedNodeContext, setSelectedNodeContext] = useState<
    Map<string, NodeContext>
  >(new Map());

  /**
   * Translates a prefixed node ID back to its original JSON context from the token data.
   *
   * @param fullNodeId - The full node ID in format: token-{text}-{start}-{localNodeId}
   * @returns The context object containing the original data structure, or null if not found
   */
  const getNodeContext = useCallback(
    (fullNodeId: string): NodeContext | null => {
      // Parse the full node ID: token-{text}-{start}-{localNodeId}
      const parts = fullNodeId.split("-");
      if (parts.length < 4 || parts[0] !== "token") {
        console.warn("Invalid node ID format:", fullNodeId);
        return null;
      }

      // Extract token info and local node ID
      const text = parts[1];
      const start = parseInt(parts[2], 10);
      const localNodeId = parts.slice(3).join("-"); // Rejoin in case the local ID has dashes

      // Find the corresponding token in the analysis result
      if (!analysisResult?.tokens) {
        console.warn("No tokens available in analysis result");
        return null;
      }

      const token = analysisResult.tokens.find(
        (t: any) => t.text === text && (t.start ?? 0) === start,
      );

      if (!token) {
        console.warn("Token not found for node ID:", fullNodeId, {
          text,
          start,
        });
        return null;
      }

      // Parse the local node ID to extract context
      if (localNodeId === "input") {
        return {
          type: "input" as const,
          text: token.text,
          lemma: token.lemma || token.text,
          pos: token.pos || token.tag || "",
          token: token,
        };
      }

      if (localNodeId.startsWith("sense-")) {
        const senseIndex = parseInt(localNodeId.replace("sense-", ""), 10);
        const synsets = token.wordnet?.synsets || [];

        if (senseIndex >= 0 && senseIndex < synsets.length) {
          const synset = synsets[senseIndex] as any;
          return {
            type: "sense" as const,
            index: senseIndex,
            synset: {
              name:
                synset.name ||
                synset.synset ||
                synset.id ||
                synset[0] ||
                "unknown",
              definition: synset.definition || synset.gloss || synset.def || "",
              lemmas: synset.lemmas || [],
              pos:
                synset.pos ||
                synset.partOfSpeech ||
                token.pos ||
                token.tag ||
                "",
              offset: synset.offset || 0,
              domain: synset.domain || "general",
            },
            token: token,
          };
        }
      }

      if (localNodeId.startsWith("relation-")) {
        // Parse relation-{relationType}-{index}
        const relationParts = localNodeId.split("-");
        if (relationParts.length >= 3) {
          const relationType = relationParts[1];
          const relationIndex = parseInt(relationParts[2], 10);

          const relatedTerms = token.concepcy?.related_terms || [];
          // Filter relations by type and find the one at the given index
          // Note: related_terms is typed as string[] but actually contains relation objects
          const relationsOfType = (relatedTerms as any[]).filter(
            (rel: any) =>
              rel.relation === relationType &&
              rel.subject?.label === (token.lemma || token.text),
          );

          if (relationIndex >= 0 && relationIndex < relationsOfType.length) {
            const relation = relationsOfType[relationIndex];
            // Determine which term is the target (not the current token)
            const currentTokenLemma = token.lemma || token.text;
            const targetTerm =
              relation.subject?.label === currentTokenLemma
                ? relation.object
                : relation.subject;

            return {
              type: "relation" as const,
              relationType: relationType,
              index: relationIndex,
              relation: relation,
              targetTerm: targetTerm,
              token: token,
            };
          }
        }
      }

      console.warn("Could not parse node context for:", fullNodeId, {
        localNodeId,
      });
      return null;
    },
    [analysisResult],
  );

  /**
   * Gets the current selected node contexts as an array of objects.
   * Useful for parent components that need to access the selected data.
   *
   * @returns Array of {nodeId, context} objects for all currently selected nodes
   */
  const getSelectedContexts = useCallback((): SelectedNodeContextEntry[] => {
    return Array.from(selectedNodeContext.entries()).map(
      ([nodeId, context]) => ({
        nodeId,
        context,
      }),
    );
  }, [selectedNodeContext]);

  // Handle node click events - toggle selection and update context
  const handleNodeClick = useCallback(
    (nodeId: string) => {
      console.log("Node clicked", { nodeId });

      setSelectedNodeIds((prev) => {
        const next = new Set(prev);
        const wasSelected = next.has(nodeId);

        if (wasSelected) {
          next.delete(nodeId);
        } else {
          next.add(nodeId);
        }
        return next;
      });

      // Update the context map
      setSelectedNodeContext((prev) => {
        const next = new Map(prev);
        const context = getNodeContext(nodeId);

        if (context) {
          if (prev.has(nodeId)) {
            // Node was deselected, remove from context
            next.delete(nodeId);
          } else {
            // Node was selected, add to context
            next.set(nodeId, context);
          }
        }

        return next;
      });
    },
    [getNodeContext],
  );

  return (
    <>
      {loading ? (
        <div className="flex items-center gap-3 py-4">
          <Spinner size="sm" />
          <span className="text-sm text-gray-600">
            Analyzing {textTitle}...
          </span>
        </div>
      ) : analysisResult ? (
        <div className="space-y-3">
          <div>
            <h4 className="mb-2 text-lg font-bold">
              {textTitle} Token Analysis
            </h4>
            {!analysisResult.tokens || analysisResult.tokens.length === 0 ? (
              <div className="py-2 text-sm text-gray-500">
                No tokens available
              </div>
            ) : (
              <div className="flex flex-col items-stretch gap-4 md:flex-row">
                <div className="flex w-full min-w-0 md:w-2/3">
                  <Accordion alwaysOpen className="w-full">
                    {(analysisResult.tokens || []).map((token: any) => {
                      // Create a unique prefix for this token's chart nodes
                      const tokenPrefix = `token-${token.text}-${token.start ?? 0}`;

                      // Memoize the selection handler to prevent unnecessary re-renders
                      const onNodeClick = (nodeId: string) => {
                        // Create a full node ID with token prefix for global tracking
                        const fullNodeId = `${tokenPrefix}-${nodeId}`;
                        handleNodeClick(fullNodeId);
                      };

                      return (
                        <AccordionPanel
                          key={`${token.text}-${token.start ?? 0}`}
                        >
                          <AccordionTitle>
                            Token &quot;
                            <span className="font-bold italic">{`${token.text}`}</span>
                            &quot;
                          </AccordionTitle>
                          <AccordionContent className="p-0">
                            <React.Suspense
                              fallback={
                                <div className="flex items-center gap-2">
                                  <Spinner size="sm" />{" "}
                                  <span className="text-sm text-gray-500">
                                    Loading details...
                                  </span>
                                </div>
                              }
                            >
                              <NlpTokenAnalysisPanel
                                token={token}
                                selectedNodeIds={selectedNodeIds}
                                onNodeClick={onNodeClick}
                              />
                            </React.Suspense>
                          </AccordionContent>
                        </AccordionPanel>
                      );
                    })}
                  </Accordion>
                </div>
                <div className="flex w-full min-w-0 md:w-1/3">
                  <NlpRefinementPanel
                    selectedNodeContext={selectedNodeContext}
                    className="flex w-full rounded-lg border border-gray-200"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Definition Generation Panel */}
          <NlpGenerationResult
            selectedNodeContext={selectedNodeContext}
            term={text}
            textTitle={textTitle}
            domainContext={domainContext}
            parentTermContext={parentTermContext}
            currentDefinition={currentDefinition}
            termId={termId}
            domainId={domainId}
            layerId={layerId}
            flavorList={flavorList}
            className="w-full rounded-lg border border-gray-200 bg-white"
          />
        </div>
      ) : (
        <div className="py-4 text-sm text-gray-500">
          Click &quot;Analyze {textTitle}&quot; to view token analysis and
          generation options.
        </div>
      )}
    </>
  );
};
