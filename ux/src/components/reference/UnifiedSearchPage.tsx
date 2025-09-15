/**
 * UnifiedSearchPage Component
 *
 * Main page for unified reference search across multiple sources
 */

import React, { useState, useEffect } from 'react';
import { Card, Alert, Button } from 'flowbite-react';
import { Search, History, Settings, Info } from 'lucide-react';
import {
  UnifiedSearchBar,
  SourceSelector,
  SearchResults,
} from './UnifiedSearch';
import { NodeDetails } from './ReferenceViewer';
import { useReferenceStore, useSearchState, useSelectionState, useHistoryState } from '@/store/referenceSlice';
import { UnifiedNode } from '@/api/types/unified';

interface UnifiedSearchPageProps {
  title?: string;
  description?: string;
  compact?: boolean;
}

export const UnifiedSearchPage: React.FC<UnifiedSearchPageProps> = ({
  title = "Unified Reference Search",
  description = "Search across multiple reference sources including ConceptNet, WordNet, DBpedia, Wikidata, and Schema.org",
  compact = false,
}) => {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [showIntro, setShowIntro] = useState(true);

  const {
    query,
    hasResults,
    isSearching,
  } = useSearchState();

  const {
    selectedNode,
    showDetails,
  } = useSelectionState();

  const {
    history,
    hasHistory,
    recentNodes,
    hasRecentNodes,
  } = useHistoryState();

  const {
    setSearchQuery,
    setShowNodeDetails,
    clearSearch,
  } = useReferenceStore();

  // Hide intro after first search
  useEffect(() => {
    if (hasResults || query.length > 0) {
      setShowIntro(false);
    }
  }, [hasResults, query]);

  const handleNodeSelect = (node: UnifiedNode) => {
    setShowNodeDetails(true);
  };

  const handleHistorySelect = (historyQuery: string) => {
    setSearchQuery(historyQuery);
    setActiveTab(0); // Switch to search tab
  };

  const handleRecentNodeSelect = (node: UnifiedNode) => {
    handleNodeSelect(node);
  };

  const SearchHistoryContent = () => (
    <div className="space-y-6">
      {/* Search History */}
      {hasHistory && (
        <Card>
          <div className="space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <History className="w-5 h-5" />
              Recent Searches
            </h3>
            <div className="space-y-2">
              {history.map((item, index) => (
                <button
                  key={index}
                  onClick={() => handleHistorySelect(item)}
                  className="w-full text-left p-3 rounded-lg border hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <Search className="w-4 h-4 text-gray-400" />
                    <span>{item}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* Recent Nodes */}
      {hasRecentNodes && (
        <Card>
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Recently Viewed</h3>
            <div className="space-y-3">
              {recentNodes.map((node) => (
                <button
                  key={node.id}
                  onClick={() => handleRecentNodeSelect(node)}
                  className="w-full text-left p-3 rounded-lg border hover:bg-gray-50 transition-colors"
                >
                  <div className="space-y-1">
                    <h4 className="font-medium text-blue-600 hover:text-blue-800">
                      {node.title}
                    </h4>
                    {node.definition && (
                      <p className="text-sm text-gray-600 line-clamp-2">
                        {node.definition}
                      </p>
                    )}
                    <div className="text-xs text-gray-400">
                      From {node.source}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* Empty state */}
      {!hasHistory && !hasRecentNodes && (
        <Alert color="info" icon={Info}>
          <div className="space-y-2">
            <p className="font-medium">No search history yet</p>
            <p className="text-sm">
              Your search queries and viewed nodes will appear here for quick access.
            </p>
          </div>
        </Alert>
      )}
    </div>
  );

  return (
    <div className={`${compact ? 'space-y-4' : 'container mx-auto px-4 py-8 space-y-6'}`}>
      <div className={compact ? '' : 'max-w-7xl mx-auto'}>
        {/* Header */}
        {!compact && (
          <div className="space-y-4">
            <div className="text-center space-y-2">
              <h1 className="text-4xl font-bold text-gray-900">{title}</h1>
              <p className="text-lg text-gray-600 max-w-3xl mx-auto">
                {description}
              </p>
            </div>

            {showIntro && (
              <Alert color="info" onDismiss={() => setShowIntro(false)}>
                <div className="space-y-2">
                  <p className="font-medium">Welcome to Unified Reference Search!</p>
                  <p className="text-sm">
                    Search across multiple knowledge sources simultaneously. Use the source
                    selector to choose which databases to include in your search.
                  </p>
                </div>
              </Alert>
            )}
          </div>
        )}

        {/* Search Interface */}
        <div className="space-y-6">
          <UnifiedSearchBar
            autoFocus={!compact}
            onSearchStart={() => setActiveTab(0)}
          />

          <div className="space-y-6">
            {/* Tab Navigation */}
            <div className="border-b border-gray-200">
              <nav className="-mb-px flex space-x-8">
                <button
                  onClick={() => setActiveTab(0)}
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 0
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Search className="w-4 h-4" />
                    Search Results
                    {isSearching && <span className="text-xs">(searching...)</span>}
                  </div>
                </button>
                <button
                  onClick={() => setActiveTab(1)}
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 1
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <History className="w-4 h-4" />
                    History
                    {(hasHistory || hasRecentNodes) && (
                      <span className="text-xs">
                        ({(history?.length || 0) + (recentNodes?.length || 0)})
                      </span>
                    )}
                  </div>
                </button>
                {!compact && (
                  <button
                    onClick={() => setActiveTab(2)}
                    className={`py-2 px-1 border-b-2 font-medium text-sm ${
                      activeTab === 2
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Settings className="w-4 h-4" />
                      Sources
                    </div>
                  </button>
                )}
              </nav>
            </div>

            {/* Tab Content */}
            {activeTab === 0 && (
              <div className="mt-6">
                <div className={`grid gap-6 ${compact ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-4'}`}>
                  {/* Source Selector */}
                  {!compact && (
                    <div className="lg:col-span-1">
                      <SourceSelector showStatus={true} />
                    </div>
                  )}

                  {/* Search Results */}
                  <div className={compact ? 'col-span-1' : 'lg:col-span-3'}>
                    <SearchResults
                      onSelectNode={handleNodeSelect}
                      showVirtualization={!compact}
                      compact={compact}
                    />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 1 && (
              <div className="mt-6">
                <SearchHistoryContent />
              </div>
            )}

            {!compact && activeTab === 2 && (
              <div className="mt-6">
                <SourceSelector showStatus={true} />
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        {!compact && hasResults && (
          <div className="flex justify-center pt-6">
            <Button
              color="gray"
              onClick={clearSearch}
              className="flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              New Search
            </Button>
          </div>
        )}
      </div>

      {/* Node Details Modal */}
      <NodeDetails
        isOpen={showDetails}
        onClose={() => setShowNodeDetails(false)}
        onNodeSelect={handleNodeSelect}
      />
    </div>
  );
};

export default UnifiedSearchPage;