/**
 * UnifiedSearchPage Component
 *
 * Simplified search page for reference sources
 */

import React, { useState } from "react";
import { TextInput, Button, Alert, Spinner, Tabs } from "flowbite-react";
import { Search, Info, List, Network } from "lucide-react";
import { SearchResults } from "./UnifiedSearch";
import { SourceSelector } from "./UnifiedSearch/SourceSelector";
import { NodeDetails } from "./ReferenceViewer";
import { GraphView } from "./GraphView";
import { UnifiedNode, SourceType, UnifiedSearchLink } from "@/api/types/unified";
import { useUnifiedSearch } from "@/api/hooks/unifiedReference/useUnifiedReference";

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
    "conceptnet",
    "dbpedia",
    "wikidata",
    "schema_org"
  ]);
  const [searchResults, setSearchResults] = useState<UnifiedNode[]>([]);
  const [searchLinks, setSearchLinks] = useState<UnifiedSearchLink[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [selectedNode, setSelectedNode] = useState<UnifiedNode | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  const {
    mutate: performSearch,
    isPending: isSearching,
    error: searchError,
  } = useUnifiedSearch({
    onSuccess: (data) => {
      setSearchResults(data.results);
      setSearchLinks(data.links || []);
      setTotalResults(data.total_results);
    },
    onError: (error) => {
      console.error("Search failed:", error);
      setSearchResults([]);
      setSearchLinks([]);
      setTotalResults(0);
    },
  });

  const handleSearch = () => {
    if (query.trim().length >= 2 && selectedSources.length > 0) {
      performSearch({
        query: query.trim(),
        sources: selectedSources,
        limit: 20,
        offset: 0,
      });
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  const handleNodeSelect = (node: UnifiedNode) => {
    setSelectedNode(node);
    setShowDetails(true);
  };

  const canSearch = query.trim().length >= 2 && selectedSources.length > 0;
  const hasSearched = searchResults.length > 0 || isSearching;

  return (
    <div className="container mx-auto max-w-6xl space-y-6 px-4 py-8">
      {/* Header */}
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold text-gray-900">{title}</h1>
        <p className="text-gray-600">{description}</p>
      </div>

      {/* Search Interface */}
      <div className="space-y-4">
        {/* Search Input Row */}
        <div className="flex gap-2 items-center">
          <TextInput
            icon={Search}
            placeholder="Enter search term..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isSearching}
            className="flex-1"
          />
          <Button
            onClick={handleSearch}
            disabled={!canSearch || isSearching}
          >
            {isSearching ? <Spinner size="sm" /> : "Search"}
          </Button>
          <SourceSelector
            selectedSources={selectedSources}
            onSourcesChange={setSelectedSources}
            disabled={isSearching}
          />
        </div>

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
        </div>

        {/* Results */}
        {hasSearched && (
          <Tabs aria-label="Search Results" className="mt-4 border-b border-gray-200">
            <Tabs.Item active title="Graph View" icon={Network}>
              <GraphView
                results={searchResults}
                searchLinks={searchLinks}
                onSelectNode={handleNodeSelect}
                isSearching={isSearching}
              />
            </Tabs.Item>
            <Tabs.Item title="List View" icon={List}>
              <SearchResults
                results={searchResults}
                totalResults={totalResults}
                onSelectNode={handleNodeSelect}
                isSearching={isSearching}
              />
            </Tabs.Item>
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