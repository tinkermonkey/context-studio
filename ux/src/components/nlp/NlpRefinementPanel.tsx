import * as React from "react";
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
}

export const NlpRefinementPanel: React.FC<NlpRefinementPanelProps> = ({
  selectedNodeContext,
  className = "",
}) => {
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

    return sortedGroups;
  }, [selectedNodeContext]);

  return (
    <div className={`${className}`}>
      <div className="flex flex-col w-full">
        <div className="w-full mb-3 bg-gray-100 dark:bg-grey-900 divide-gray-200 dark:divide-gray-700 px-2 py-5">
          <h5 className="text-lg font-semibold">Selected Node Context</h5>
        </div>
        {selectedNodeContext.size === 0 ? (
          <div className="text-sm text-gray-500 p-2">No nodes selected</div>
        ) : (
          <div className="space-y-4 text-sm p-2">
            {groupedContexts.map(
              ({
                tokenKey,
                tokenText,
                tokenStart,
                tokenDefinition,
                entries,
              }) => (
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
      </div>
    </div>
  );
};

export default NlpRefinementPanel;
