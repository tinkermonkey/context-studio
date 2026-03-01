/**
 * UnifiedSearchPage Component
 *
 * Simplified search page for reference sources
 */

import React, { useState } from "react";
import {
  TextInput,
  Button,
  Alert,
  Spinner,
  Tabs,
  TabItem,
  Badge,
} from "flowbite-react";
import {
  Search,
  Info,
  List,
  Network,
  Clock,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { SearchResults } from "./UnifiedSearch";
import { SourceSelector } from "./UnifiedSearch/SourceSelector";
import { NodeDetails } from "./ReferenceViewer";
import { GraphView } from "./GraphView";
import {
  UnifiedNode,
  SourceType,
  UnifiedSearchLink,
  SOURCE_METADATA,
} from "@/api/types/unified";
import {
  useStreamingUnifiedSearch,
  useSourceLoadingStates,
} from "@/api/hooks/unifiedReference/useStreamingReference";

interface UnifiedSearchPageProps {
  title?: string;
  description?: string;
}

export const UnifiedSearchPage: React.FC<UnifiedSearchPageProps> = ({
  title = "Reference Search",
  description = "Search across multiple reference sources",
}) => {
  const [query, setQuery] = useState("");
  const [selectedSources, setSelectedSources] = useState<SourceType[]>([
    "dbpedia",
    "schema_org",
    "conceptnet",
    "wikidata",
  ]);
  const [selectedNode, setSelectedNode] = useState<UnifiedNode | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [searchError, setSearchError] = useState<Error | null>(null);

  const {
    search: performSearch,
    searchState,
    isSearching,
    hasResults,
    results: searchResults,
    links: searchLinks,
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

  const handleNodeSelect = (node: UnifiedNode) => {
    setSelectedNode(node);
    setShowDetails(true);
  };

  const canSearch = query.trim().length >= 2 && selectedSources.length > 0;
  const hasSearched = hasResults || isSearching;

  // Create source status indicators
  const renderSourceStatus = () => {
    if (!searchState) return null;

    return (
      <div className="mb-4 flex flex-wrap gap-2">
        {Object.entries(searchState.sources).map(([source, sourceUpdate]) => {
          const metadata = SOURCE_METADATA[source as SourceType];
          const isLoading = sourceLoadingStates.isSourceLoading(
            source as SourceType,
          );
          const isComplete = sourceLoadingStates.isSourceComplete(
            source as SourceType,
          );
          const isError = sourceLoadingStates.isSourceError(
            source as SourceType,
          );
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
            <Badge
              key={source}
              color={color}
              className="flex items-center gap-1"
            >
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
    <div className="container mx-auto max-w-6xl space-y-6 px-4 py-8">
      {/* Header */}
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-bold text-gray-900">{title}</h1>
        <p className="text-gray-600">{description}</p>
      </div>

      {/* Search Interface */}
      <div className="space-y-4">
        {/* Search Input Row */}
        <div className="flex items-center gap-2">
          <TextInput
            data-testid="reference-search-input"
            icon={Search}
            placeholder="Enter search term..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSearching}
            className="flex-1"
          />
          <Button
            data-testid="reference-search-button"
            onClick={handleSearch}
            disabled={!canSearch || isSearching}
          >
            {isSearching ? <Spinner size="sm" /> : "Search"}
          </Button>
          <SourceSelector
            data-testid="reference-source-filter"
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
            <Alert color="failure">Search failed: {searchError.message}</Alert>
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
                  {Object.keys(searchState?.sources || {}).length} sources
                  complete)
                  {hasResults &&
                    ` - ${totalResults} deduplicated results so far`}
                  {searchState?.deduplicationStats &&
                    searchState.deduplicationStats.duplicatesRemoved > 0 &&
                    ` (${searchState.deduplicationStats.duplicatesRemoved} duplicates removed)`}
                </span>
              </div>
            </Alert>
          )}

          {/* Deduplication Summary */}
          {searchState?.isComplete && searchState?.deduplicationStats && (
            <Alert color="success">
              <div className="text-sm">
                <strong>Search Complete:</strong> Found {totalResults} unique
                results
                {searchState.deduplicationStats.duplicatesRemoved > 0 && (
                  <span>
                    {" "}
                    ({searchState.deduplicationStats.duplicatesRemoved}{" "}
                    duplicates removed)
                  </span>
                )}
                {searchState.deduplicationStats.crossReferences > 0 && (
                  <span>
                    , {searchState.deduplicationStats.crossReferences}{" "}
                    cross-references discovered
                  </span>
                )}
                {searchLinks.length > 0 && (
                  <span>, {searchLinks.length} total relationships</span>
                )}
              </div>
            </Alert>
          )}
        </div>

        {/* Results - searchResults and searchLinks are already deduplicated and normalized by the streaming service */}
        {hasSearched && (
          <Tabs
            aria-label="Search Results"
            className="mt-4 border-b border-gray-200"
          >
            <TabItem active title="Graph View" icon={Network}>
              {/* Break out of container for full-width graph */}
              <div className="-mx-4 sm:-mx-6 lg:-mx-8 xl:-mx-12 2xl:-mx-16">
                <div className="relative right-1/2 left-1/2 -mr-[50vw] -ml-[50vw] w-screen px-8">
                  <GraphView
                    results={searchResults}
                    searchLinks={searchLinks}
                    onSelectNode={handleNodeSelect}
                    isSearching={isSearching}
                  />
                </div>
              </div>
            </TabItem>
            <TabItem title="List View" icon={List}>
              <SearchResults
                data-testid="reference-results-list"
                results={searchResults}
                totalResults={totalResults}
                onSelectNode={handleNodeSelect}
                isSearching={isSearching}
                streamingState={searchState}
                showSourceProgress={true}
              />
            </TabItem>
          </Tabs>
        )}

        {/* Empty State */}
        {!hasSearched && (
          <Alert color="info" icon={Info}>
            Enter a search term and select sources to begin searching.
          </Alert>
        )}
      </div>

      {/* Node Details Modal */}
      {selectedNode && (
        <NodeDetails
          node={selectedNode}
          isOpen={showDetails}
          onClose={() => setShowDetails(false)}
          onNodeSelect={handleNodeSelect}
          searchLinks={searchLinks}
          searchResults={searchResults}
        />
      )}
    </div>
  );
};

export default UnifiedSearchPage;
