import * as React from "react";
import { Button, Card, Alert, Spinner } from "flowbite-react";
import { CheckCircle, XCircle, Lightbulb, AlertCircle } from "lucide-react";
import { useSuggestDefinitionMutation, type DefinitionSuggestionResponse } from "../../api";
import type { NodeContext } from "./types";

/**
 * NlpRefinementPanel displays the context information for selected nodes
 * from the NLP analysis charts. It shows detailed information about input tokens,
 * WordNet senses, and ConceptNet relations, grouped by token and ordered by
 * their appearance in the source text. Within each token group, inputs are
 * shown first, followed by senses, then relations.
 */
interface NlpRefinementPanelProps {
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
}

export const NlpRefinementPanel: React.FC<NlpRefinementPanelProps> = ({
  selectedNodeContext,
  className = "",
  term,
  textTitle = null,
  domainContext = null,
  parentTermContext = null,
  currentDefinition = null,
}) => {
  // State for managing suggested definition
  const [suggestedDefinition, setSuggestedDefinition] = React.useState<DefinitionSuggestionResponse | null>(null);
  
  // LLM mutation hook for generating definitions
  const suggestDefinitionMutation = useSuggestDefinitionMutation({
    onSuccess: (data) => {
      setSuggestedDefinition(data);
      console.log('Definition suggestion received:', data);
    },
    onError: (error) => {
      console.error('Error generating definition suggestion:', error);
    },
  });
  // Clear suggested definition when context changes
  React.useEffect(() => {
    setSuggestedDefinition(null);
  }, [selectedNodeContext, term, domainContext, parentTermContext, currentDefinition]);

  // Group and sort the selected contexts by token
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

    //console.log("Grouped Contexts:", sortedGroups);
    //console.log("Grouped Contexts:", JSON.stringify(sortedGroups, null, 2));

    return sortedGroups;
  }, [selectedNodeContext]);

  // Utility function to normalize predicates to lowercase space-separated words
  const normalizePredicate = React.useCallback((predicate: string): string => {
    if (!predicate) return predicate;
    
    return predicate
      // Handle camelCase: insert space before uppercase letters
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      // Handle underscores: replace with spaces
      .replace(/_/g, ' ')
      // Handle multiple spaces: collapse to single spaces
      .replace(/\s+/g, ' ')
      // Convert to lowercase and trim
      .toLowerCase()
      .trim();
  }, []);

  // Function to generate the API context JSON and call the LLM API
  const generateApiContext = React.useCallback(() => {
    const componentTerms = groupedContexts.map(({ tokenText, entries }) => {
      const selectedDefinitions: string[] = [];
      const selectedRelations: Array<{
        predicate: string;
        object: string;
        weight: number;
        text: string;
      }> = [];

      entries.forEach(({ context }) => {
        if (context.type === "sense" && context.synset) {
          selectedDefinitions.push(context.synset.definition);
        } else if (
          context.type === "relation" &&
          context.relation &&
          context.targetTerm
        ) {
          selectedRelations.push({
            predicate: normalizePredicate(context.relationType || "unknown"),
            object: context.targetTerm.label,
            weight: context.relation.weight || 0,
            text: context.relation.text || "",
          });
        }
      });

      return {
        text: tokenText,
        selected_definitions: selectedDefinitions,
        selected_relations: selectedRelations,
      };
    });

    const apiContext = {
      term: term,
      domain_title: domainContext?.title || undefined,
      domain_definition: domainContext?.definition || undefined,
      parent_term_title: parentTermContext?.title || undefined,
      parent_term_definition: parentTermContext?.definition || undefined,
      parent_relationship_predicate: normalizePredicate(
        parentTermContext?.relationshipPredicate || "",
      ) || undefined,
      component_terms: componentTerms,
      current_definition: currentDefinition || undefined,
      dbpedia_context: {},
    };

    console.log("Generated API Context:", JSON.stringify(apiContext, null, 2));

    // Call the LLM API
    suggestDefinitionMutation.mutate(apiContext);

    return apiContext;
  }, [
    groupedContexts,
    term,
    domainContext,
    parentTermContext,
    currentDefinition,
    normalizePredicate,
    suggestDefinitionMutation,
  ]);

  return (
    <div className={`flex w-full p-2 rounded-lg border border-gray-200 bg-white shadow-md dark:border-gray-700 dark:bg-gray-800 flex-col${className}`}>
      <div className="mb-3">
        <h5 className="text-lg font-semibold">Selected Node Context</h5>
      </div>
      {selectedNodeContext.size === 0 ? (
        <div className="text-sm text-gray-500">No nodes selected</div>
      ) : (
        <div className="space-y-4 text-sm">
          {groupedContexts.map(
            ({ tokenKey, tokenText, tokenStart, tokenDefinition, entries }) => (
              <div
                key={tokenKey}
                className="border-b border-gray-200 pb-3 last:border-b-0"
              >
                <div className="mb-2">
                  <h6 className="text-xs font-semibold tracking-wide text-gray-800 uppercase">
                    Token: "{tokenText}" (pos: {tokenStart})
                  </h6>
                  {tokenDefinition && (
                    <div className="mt-1 text-xs text-gray-600">
                      Lemma: {tokenDefinition.lemma} | POS:{" "}
                      {tokenDefinition.pos}
                    </div>
                  )}
                </div>
                {entries.length > 0 && (
                  <div className="space-y-2">
                    {entries.map(({ nodeId, context }) => (
                      <div
                        key={nodeId}
                        className="border-b border-gray-100 pb-2 pl-2 last:border-b-0"
                      >
                        <div className="mb-1 font-medium text-gray-700">
                          {context.type === "sense" &&
                            `Sense: ${context.synset?.name}`}
                          {context.type === "relation" &&
                            `${context.relationType}: ${context.targetTerm?.label || context.relation?.object?.label || context.relation?.subject?.label}`}
                        </div>
                        {context.type === "sense" && context.synset && (
                          <div className="text-xs text-gray-600">
                            <div className="mb-1">
                              {context.synset.definition}
                            </div>
                            <div className="text-gray-500">
                              POS: {context.synset.pos} | Domain:{" "}
                              {context.synset.domain}
                            </div>
                          </div>
                        )}
                        {context.type === "relation" && context.relation && (
                          <div className="text-xs text-gray-600">
                            <div className="mb-1">
                              Weight: {context.relation.weight}
                            </div>
                            <div className="text-gray-500">
                              {context.relation.text}
                            </div>
                            {context.targetTerm && (
                              <div className="mt-1 text-gray-500">
                                Target: {context.targetTerm.label} (
                                {context.targetTerm.language})
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ),
          )}
        </div>
      )}

      {/* Generate Definition Button */}
      {selectedNodeContext.size > 0 && (
        <div className="mt-4 space-y-3">
          <Button
            size="sm"
            onClick={generateApiContext}
            disabled={suggestDefinitionMutation.isPending || !term.trim()}
            className="w-full"
          >
            {suggestDefinitionMutation.isPending ? (
              <div className="flex items-center gap-2">
                <Spinner size="sm" />
                <span>Generating Definition...</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4" />
                <span>Generate Suggested Definition</span>
              </div>
            )}
          </Button>

          {/* Error Display */}
          {suggestDefinitionMutation.error && (
            <Alert color="failure" className="text-sm">
              <div className="flex items-center gap-2">
                <XCircle className="h-4 w-4" />
                <span className="font-medium">Error:</span>
              </div>
              <div className="mt-1">
                {suggestDefinitionMutation.error.message}
              </div>
            </Alert>
          )}

          {/* Success Display */}
          {suggestedDefinition && (
            <Alert color="success" className="text-sm">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4" />
                  <span className="font-medium">Suggested Definition</span>
                </div>
                
                <div className="space-y-2">
                  <div>
                    <h6 className="text-xs font-semibold text-green-800 uppercase tracking-wide mb-1">
                      Definition:
                    </h6>
                    <p className="text-sm text-green-700">
                      {suggestedDefinition.definition}
                    </p>
                  </div>
                  
                  <div>
                    <h6 className="text-xs font-semibold text-green-800 uppercase tracking-wide mb-1">
                      Reasoning:
                    </h6>
                    <p className="text-xs text-green-600">
                      {suggestedDefinition.reasoning}
                    </p>
                  </div>
                  
                  {suggestedDefinition.discrepancies && (
                    <div>
                      <h6 className="text-xs font-semibold text-amber-800 uppercase tracking-wide mb-1 flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" />
                        Discrepancies:
                      </h6>
                      <p className="text-xs text-amber-700">
                        {suggestedDefinition.discrepancies}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </Alert>
          )}
        </div>
      )}
    </div>
  );
};

export default NlpRefinementPanel;
