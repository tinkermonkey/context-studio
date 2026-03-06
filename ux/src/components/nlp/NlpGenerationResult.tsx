import * as React from "react";
import { useEffect } from "react";
import { Alert } from "flowbite-react";
import { type PipelineType } from "../../api";
import { LlmPipelineRun } from "../llm_pipelines/LlmPipelineRun";
import type { NodeContext } from "./types";
import PipelineResultView from "./PipelineResultView";

/**
 * NlpGenerationResult handles the generation and display of AI-generated definitions
 * based on selected NLP analysis nodes. It provides functionality to generate
 * definitions for terms, domains, or layers and save them to the appropriate context.
 */
interface NlpGenerationResultProps {
  selectedNodeContext: Map<string, NodeContext>;
  className?: string;
  term: string;
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

export const NlpGenerationResult: React.FC<NlpGenerationResultProps> = ({
  selectedNodeContext,
  className = "",
  term,
  domainContext = null,
  parentTermContext = null,
  currentDefinition = null,
  termId = null,
  domainId = null,
  layerId = null,
  flavorList = null,
}) => {
  const [apiContext, setApiContext] = React.useState<Record<
    string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
    any
  > | null>(null);

  // Determine pipeline type and context based on IDs
  const pipelineType: PipelineType = React.useMemo(() => {
    if (termId) return "suggest_term_definition";
    if (domainId && !termId) return "suggest_domain_definition";
    if (layerId && !termId && !domainId) return "suggest_layer_definition";
    return "suggest_term_definition"; // Default fallback
  }, [termId, domainId, layerId]);

  // (save UI state moved into per-result component)

  // ...existing code...

  // (mutations moved into per-result component)

  // Clear pipeline state when context changes
  React.useEffect(() => {
    setApiContext(null);
  }, [
    selectedNodeContext,
    term,
    domainContext,
    parentTermContext,
    currentDefinition,
  ]);

  // Group and sort the selected contexts by token (same logic as in NlpRefinementPanel)
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const groupedContexts = React.useMemo(() => {
    if (selectedNodeContext.size === 0) return [];

    // Convert Map to array and extract token information from nodeId
    const contextEntries = Array.from(selectedNodeContext.entries()).map(
      ([nodeId, context]) => {
        // Parse nodeId to extract token info: token-{text}-{start}-{localNodeId}
        const parts = nodeId.split("-");
        const tokenText = parts[1] || "";
        const tokenStart = parseInt(parts[2] || "0", 10);

        return {
          nodeId,
          context,
          tokenText,
          tokenStart,
          sortKey: `${tokenStart.toString().padStart(10, "0")}-${tokenText}`, // For stable sorting
        };
      },
    );

    // Group by token
    const tokenGroups = new Map<string, typeof contextEntries>();
    contextEntries.forEach((entry) => {
      const tokenKey = `${entry.tokenText}-${entry.tokenStart}`;
      if (!tokenGroups.has(tokenKey)) {
        tokenGroups.set(tokenKey, []);
      }
      tokenGroups.get(tokenKey)!.push(entry);
    });

    // Sort groups by token order (start position) and sort items within each group
    const sortedGroups = Array.from(tokenGroups.entries())
      .sort(([, a], [, b]) => {
        // Sort by the first item's start position in each group
        return a[0].tokenStart - b[0].tokenStart;
      })
      .map(([tokenKey, entries]) => {
        // Within each token group, sort by type: input, then sense, then relation
        const typeOrder: Record<NodeContext["type"], number> = {
          input: 0,
          sense: 1,
          relation: 2,
        };
        const sortedEntries = entries.sort((a, b) => {
          const typeComparison =
            typeOrder[a.context.type] - typeOrder[b.context.type];
          if (typeComparison !== 0) return typeComparison;

          // Within the same type, sort by index if available
          const aIndex = a.context.index ?? 0;
          const bIndex = b.context.index ?? 0;
          return aIndex - bIndex;
        });

        // Grab the `token` element from the `context` of the first entry
        const tokenEntry = sortedEntries[0];
        const tokenDefinition = tokenEntry ? tokenEntry.context.token : null;

        // Remove the `token` element from the `context` for each entry
        sortedEntries.forEach((entry) => {
          delete entry.context.token;
        });

        return {
          tokenKey,
          tokenText: entries[0].tokenText,
          tokenStart: entries[0].tokenStart,
          tokenDefinition,
          entries: sortedEntries,
        };
      });

    return sortedGroups;
  }, [selectedNodeContext]);

  // Utility function to normalize predicates to lowercase space-separated words
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const normalizePredicate = React.useCallback((predicate: string): string => {
    if (!predicate) return predicate;

    return (
      predicate
        // Handle camelCase: insert space before uppercase letters
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        // Handle underscores: replace with spaces
        .replace(/_/g, " ")
        // Handle multiple spaces: collapse to single spaces
        .replace(/\s+/g, " ")
        // Convert to lowercase and trim
        .toLowerCase()
        .trim()
    );
  }, []);

  // Function to generate the API context JSON and prepare for pipeline execution
  React.useEffect(() => {
    // debounce 300ms
    const handler = setTimeout(() => {
      const ctx = buildApiContext();
      console.log(
        `Auto-generated ${pipelineType} API Context:`,
        JSON.stringify(ctx, null, 2),
      );
      setApiContext(ctx);
    }, 300);

    return () => clearTimeout(handler);
  }, [buildApiContext, pipelineType]);

  // (saving moved into per-result component `PipelineResultView`)

  // (rendering moved into PipelineResultView)

  return (
    <div className={`${className}`}>
      <div className="flex w-full flex-col">
        <div className="dark:bg-grey-900 mb-3 w-full divide-gray-200 bg-gray-100 px-4 py-3 dark:divide-gray-700">
          <h5 className="text-lg font-semibold">Definition Generation</h5>
        </div>

        <div className="px-4 pb-4">
          {selectedNodeContext.size > 0 ? (
            <div className="space-y-3">
              <LlmPipelineRun
                pipelineType={pipelineType}
                context={apiContext || {}}
                flavorList={flavorList}
                // Render each result with its own saving state
                resultTemplate={
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  (result: any) => (
                    <PipelineResultView
                      result={result}
                      apiContext={apiContext}
                      buildApiContext={buildApiContext}
                      termId={termId}
                      domainId={domainId}
                      layerId={layerId}
                    />
                  )
                }
                showTiming={false}
                onExecutionStart={() => {
                  console.log("Pipeline execution started");
                }}
                onExecutionComplete={(results) => {
                  console.log("Pipeline execution completed:", results);
                }}
                onFlavorComplete={(result) => {
                  console.log("Flavor completed:", result);
                }}
              />

              {!(termId || domainId || layerId) && (
                <Alert color="warning" className="text-sm">
                  No term, domain, or layer ID provided - cannot save
                  definitions
                </Alert>
              )}
            </div>
          ) : (
            <div className="text-sm text-gray-500">
              Select nodes from the analysis above to generate a definition
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NlpGenerationResult;
