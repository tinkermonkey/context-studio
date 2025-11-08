/**
 * ReferenceNodeSearch Component
 *
 * Search interface for finding reference nodes across external sources.
 * Reuses UnifiedSearchBar and SourceSelector patterns from UnifiedSearchPage.
 */

import React, { useState } from "react";
import { TextInput, Button, Alert, Spinner, Badge, Checkbox } from "flowbite-react";
import { Search, Info, Clock, CheckCircle, XCircle } from "lucide-react";
import { UnifiedNode, SourceType, SOURCE_METADATA } from "@/api/types/unified";
import { useStreamingUnifiedSearch, useSourceLoadingStates } from "@/api/hooks/unifiedReference/useStreamingReference";
import { SourceSelector } from "@/components/reference/UnifiedSearch/SourceSelector";
import { getSourceBadgeColor, getSourceLabel } from "@/utils/sourceUtils";

interface ReferenceNodeSearchProps {
  onAddNode: (node: UnifiedNode) => void;
  selectedNodes: UnifiedNode[];
}

export const ReferenceNodeSearch: React.FC<ReferenceNodeSearchProps> = ({
  onAddNode,
  selectedNodes,
}) => {
  const [query, setQuery] = useState("");
  const [selectedSources, setSelectedSources] = useState<SourceType[]>([
    "dbpedia",
    "schema_org",
    "conceptnet",
    "wikidata",
  ]);
  const [selectedResultIds, setSelectedResultIds] = useState<Set<string>>(new Set());
  const [searchError, setSearchError] = useState<Error | null>(null);

  const {
    search: performSearch,
    searchState,
    isSearching,
    hasResults,
    results: searchResults,
    totalResults,
    completedSources,
    errorSources,
  } = useStreamingUnifiedSearch({
    onComplete: (state) => {
      console.log("Search completed:", state);
    },
    onSourceUpdate: (update) => {
      console.log(`Source ${update.source} update:`, update);
    },
  });

  const sourceLoadingStates = useSourceLoadingStates(searchState);

  const handleSearch = () => {
    if (query.trim().length >= 2 && selectedSources.length > 0) {
      setSearchError(null);
      setSelectedResultIds(new Set());
      performSearch({
        query: query.trim(),
        sources: selectedSources,
        limit: 20,
        offset: 0,
      }).catch((error: Error) => {
        setSearchError(error);
      });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  const handleToggleSelection = (node: UnifiedNode) => {
    const nodeKey = `${node.source}-${node.id}`;
    const newSelection = new Set(selectedResultIds);

    if (newSelection.has(nodeKey)) {
      newSelection.delete(nodeKey);
    } else {
      newSelection.add(nodeKey);
    }

    setSelectedResultIds(newSelection);
  };

  const handleAddSelected = () => {
    const nodesToAdd = searchResults.filter((node) => {
      const nodeKey = `${node.source}-${node.id}`;
      return selectedResultIds.has(nodeKey);
    });

    nodesToAdd.forEach((node) => onAddNode(node));
    setSelectedResultIds(new Set());
  };

  const isNodeAlreadySelected = (node: UnifiedNode): boolean => {
    return selectedNodes.some(
      (n) => n.id === node.id && n.source === node.source
    );
  };

  const canSearch = query.trim().length >= 2 && selectedSources.length > 0;
  const hasSearched = hasResults || isSearching;
  const hasSelections = selectedResultIds.size > 0;

  // Create source status indicators
  const renderSourceStatus = () => {
    if (!searchState) return null;

    return (
      <div className="flex flex-wrap gap-2">
        {Object.entries(searchState.sources).map(([source, sourceUpdate]) => {
          const metadata = SOURCE_METADATA[source as SourceType];
          const isLoading = sourceLoadingStates.isSourceLoading(source as SourceType);
          const isComplete = sourceLoadingStates.isSourceComplete(source as SourceType);
          const isError = sourceLoadingStates.isSourceError(source as SourceType);
          const resultCount = sourceUpdate.results?.length || 0;

          let icon;
          let color: "gray" | "blue" | "green" | "red" = "gray";

          if (isLoading) {
            icon = <Clock className="h-3 w-3" />;
            color = "blue";
          } else if (isComplete) {
            icon = <CheckCircle className="h-3 w-3" />;
            color = "green";
          } else if (isError) {
            icon = <XCircle className="h-3 w-3" />;
            color = "red";
          }

          return (
            <Badge key={source} color={color} className="flex items-center gap-1">
              {icon}
              {metadata?.label || source}
              {isComplete && ` (${resultCount})`}
              {isLoading && <Spinner size="xs" />}
            </Badge>
          );
        })}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Search Input Row */}
      <div className="flex gap-2 items-center">
        <TextInput
          icon={Search}
          placeholder="Search reference sources..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isSearching}
          className="flex-1"
        />
        <Button onClick={handleSearch} disabled={!canSearch || isSearching}>
          {isSearching ? <Spinner size="sm" /> : "Search"}
        </Button>
        <SourceSelector
          selectedSources={selectedSources}
          onSourcesChange={setSelectedSources}
          disabled={isSearching}
        />
      </div>

      {/* Source Status Indicators */}
      {renderSourceStatus()}

      {/* Validation Messages */}
      <div className="space-y-2">
        {query.length > 0 && query.length < 2 && (
          <Alert color="warning">
            Search query must be at least 2 characters long.
          </Alert>
        )}

        {selectedSources.length === 0 && (
          <Alert color="failure">
            Please select at least one reference source.
          </Alert>
        )}

        {/* Search Error */}
        {searchError && (
          <Alert color="failure">
            Search failed: {searchError.message}
          </Alert>
        )}

        {/* Source Errors */}
        {errorSources.length > 0 && (
          <Alert color="warning">
            Some sources had errors:{" "}
            {errorSources
              .map((source) => SOURCE_METADATA[source]?.label || source)
              .join(", ")}
          </Alert>
        )}

        {/* Progress Information */}
        {isSearching && (
          <Alert color="info">
            <div className="flex items-center gap-2">
              <Spinner size="sm" />
              <span>
                Searching... ({completedSources.length} of{" "}
                {Object.keys(searchState?.sources || {}).length} sources complete)
                {hasResults && ` - ${totalResults} results found`}
              </span>
            </div>
          </Alert>
        )}

        {/* Deduplication Summary */}
        {searchState?.isComplete && searchState?.deduplicationStats && (
          <Alert color="success">
            <div className="text-sm">
              <strong>Search Complete:</strong> Found {totalResults} unique results
              {searchState.deduplicationStats.duplicatesRemoved > 0 && (
                <span>
                  {" "}
                  ({searchState.deduplicationStats.duplicatesRemoved} duplicates
                  removed)
                </span>
              )}
            </div>
          </Alert>
        )}
      </div>

      {/* Results with Selection Checkboxes */}
      {hasSearched && (
        <div className="space-y-3">
          {hasSelections && (
            <div className="flex items-center justify-between border-b pb-3">
              <span className="text-sm text-gray-600">
                {selectedResultIds.size} result{selectedResultIds.size !== 1 ? "s" : ""} selected
              </span>
              <Button size="sm" onClick={handleAddSelected}>
                Add Selected
              </Button>
            </div>
          )}

          {searchResults.length === 0 && !isSearching && (
            <Alert color="info" icon={Info}>
              No results found. Try adjusting your search query or selecting different
              sources.
            </Alert>
          )}

          {searchResults.map((node) => {
            const nodeKey = `${node.source}-${node.id}`;
            const isSelected = selectedResultIds.has(nodeKey);
            const alreadyAdded = isNodeAlreadySelected(node);
            const relevancePercent = Math.round((node.relevance_score || 0) * 100);

            return (
              <div
                key={nodeKey}
                className={`border rounded-lg p-3 ${
                  isSelected ? "border-blue-500 bg-blue-50" : "border-gray-200"
                } ${alreadyAdded ? "opacity-50" : ""}`}
              >
                <div className="flex items-start gap-3">
                  <Checkbox
                    checked={isSelected}
                    onChange={() => handleToggleSelection(node)}
                    disabled={alreadyAdded}
                    className="mt-1"
                  />
                  <div className="flex-1">
                    <h4 className="font-medium text-gray-900">{node.title}</h4>
                    {node.definition && (
                      <p className="mt-1 text-sm text-gray-600 line-clamp-2">
                        {node.definition}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge color={getSourceBadgeColor(node.source)}>
                        {getSourceLabel(node.source)}
                      </Badge>
                      {(node.relevance_score || 0) < 1 && (
                        <Badge color="gray" size="sm">
                          {relevancePercent}% match
                        </Badge>
                      )}
                      {alreadyAdded && (
                        <Badge color="success" size="sm">
                          Already Added
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Additional loading indicator at bottom */}
          {isSearching && searchResults.length > 0 && (
            <div className="py-4 text-center">
              <Spinner size="sm" className="mr-2" />
              <span className="text-sm text-gray-600">
                Loading additional results...
              </span>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!hasSearched && (
        <Alert color="info" icon={Info}>
          Enter a search term and select sources to find reference nodes.
        </Alert>
      )}
    </div>
  );
};

export default ReferenceNodeSearch;
