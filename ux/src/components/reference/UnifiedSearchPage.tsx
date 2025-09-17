/**
 * UnifiedSearchPage Component
 *
 * Main page for unified reference search across multiple sources
 */

import React, { useState } from "react";
import { Button } from "flowbite-react";
import { Search } from "lucide-react";
import {
  UnifiedSearchBar,
  SearchResults,
} from "./UnifiedSearch";
import { NodeDetails } from "./ReferenceViewer";
import { UnifiedNode, SourceType } from "@/api/types/unified";

interface UnifiedSearchPageProps {
  title?: string;
  description?: string;
}

export const UnifiedSearchPage: React.FC<UnifiedSearchPageProps> = ({
  title = "Unified Reference Search",
  description = "Search across multiple reference sources including ConceptNet, DBpedia, Wikidata, and Schema.org",
}) => {
  const [searchResults, setSearchResults] = useState<UnifiedNode[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [selectedSources, setSelectedSources] = useState<SourceType[]>(["conceptnet", "dbpedia", "wikidata", "schema_org"]);
  const [selectedNode, setSelectedNode] = useState<UnifiedNode | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  const handleSearchComplete = (results: UnifiedNode[], total: number) => {
    setSearchResults(results);
    setTotalResults(total);
  };

  const handleNodeSelect = (node: UnifiedNode) => {
    setSelectedNode(node);
    setShowDetails(true);
  };

  const clearSearch = () => {
    setSearchResults([]);
    setTotalResults(0);
    setSelectedNode(null);
    setShowDetails(false);
  };

  return (
    <div className="container mx-auto space-y-6 px-4 py-8">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="space-y-4">
          <div className="space-y-2 text-center">
            <h1 className="text-4xl font-bold text-gray-900">{title}</h1>
            <p className="mx-auto max-w-3xl text-lg text-gray-600">
              {description}
            </p>
          </div>
        </div>

        {/* Search Interface */}
        <div className="space-y-6">
          <UnifiedSearchBar
            autoFocus
            selectedSources={selectedSources}
            onSourcesChange={setSelectedSources}
            onSearchComplete={handleSearchComplete}
          />

          {/* Search Results */}
          <div className="mt-6">
            <SearchResults
              results={searchResults}
              totalResults={totalResults}
              onSelectNode={handleNodeSelect}
            />
          </div>
        </div>

      </div>

      {/* Node Details Modal */}
      <NodeDetails
        node={selectedNode}
        isOpen={showDetails}
        onClose={() => setShowDetails(false)}
        onNodeSelect={handleNodeSelect}
      />
    </div>
  );
};

export default UnifiedSearchPage;
