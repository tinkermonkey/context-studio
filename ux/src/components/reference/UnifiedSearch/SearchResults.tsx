/**
 * SearchResults Component
 *
 * Displays unified search results with virtual scrolling for performance
 */

import React, { useMemo } from 'react';
import { Card, Badge, Button, Alert, Spinner } from 'flowbite-react';
import { ExternalLink, AlertCircle, Info } from 'lucide-react';
// Virtual scrolling temporarily disabled due to react-window import issues
// import * as ReactWindow from 'react-window';
import { UnifiedNode } from '@/api/types/unified';
import { SOURCE_METADATA } from '@/api/types/unified';
import { DeduplicationIndicator } from './DeduplicationIndicator';
import { useReferenceStore, useSearchState } from '@/store/referenceSlice';

interface SearchResultsProps {
  onSelectNode?: (node: UnifiedNode) => void;
  onLoadMore?: () => void;
  itemHeight?: number;
  listHeight?: number;
  showVirtualization?: boolean;
  compact?: boolean;
}

interface ResultCardProps {
  node: UnifiedNode;
  onSelect: () => void;
  style?: React.CSSProperties;
  compact?: boolean;
}

const ResultCard: React.FC<ResultCardProps> = ({
  node,
  onSelect,
  style,
  compact = false
}) => {
  const sourceMetadata = SOURCE_METADATA[node.source] || {
    label: node.source,
    color: 'gray',
    description: '',
  };

  const confidencePercent = Math.round(node.confidence_score * 100);

  return (
    <div style={style} className="px-2 pb-4">
      <Card
        className="hover:shadow-lg transition-shadow cursor-pointer h-full"
        onClick={onSelect}
      >
        <div className="space-y-3 h-full flex flex-col">
          {/* Content */}
          <div className="flex-1">
            <h3 className="text-lg font-semibold line-clamp-2 mb-2">
              {node.title}
            </h3>

            {!compact && node.definition && (
              <p className="text-gray-600 text-sm line-clamp-3 mb-3">
                {node.definition}
              </p>
            )}
          </div>

          {/* Metadata badges */}
          <div className="flex flex-wrap gap-2">
            <Badge color={sourceMetadata.color as any}>
              {sourceMetadata.label}
            </Badge>

            {node.confidence_score < 1 && (
              <Badge color="gray" size="sm">
                {confidencePercent}% match
              </Badge>
            )}

            {node.merged_from && node.merged_from.length > 0 && (
              <DeduplicationIndicator
                mergedSources={node.merged_from}
                similarityScore={node.confidence_score}
                primarySource={node.source}
                size="sm"
              />
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-between items-center pt-2 border-t border-gray-100">
            <Button
              size="xs"
              color="blue"
              onClick={(e) => {
                e.stopPropagation();
                onSelect();
              }}
            >
              View Details
            </Button>

            {node.source_url && (
              <Button
                size="xs"
                color="gray"
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(node.source_url, '_blank');
                }}
                className="flex items-center gap-1"
              >
                <ExternalLink className="w-3 h-3" />
                Source
              </Button>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
};

export const SearchResults: React.FC<SearchResultsProps> = ({
  onSelectNode,
  onLoadMore,
  itemHeight = 200,
  listHeight = 600,
  showVirtualization = true,
  compact = false,
}) => {
  const {
    results,
    total,
    isSearching,
    hasResults,
    hasMore,
    errors,
    hasErrors,
  } = useSearchState();

  const { selectNode, addToRecentNodes } = useReferenceStore();

  const handleSelectNode = (node: UnifiedNode) => {
    selectNode(node);
    addToRecentNodes(node);
    onSelectNode?.(node);
  };

  // Memoize the virtual list item renderer
  const VirtualizedItem = useMemo(() => {
    return ({ index, style }: { index: number; style: React.CSSProperties }) => (
      <ResultCard
        node={results[index]}
        onSelect={() => handleSelectNode(results[index])}
        style={style}
        compact={compact}
      />
    );
  }, [results, handleSelectNode, compact]);

  // Show loading state during search
  if (isSearching && !hasResults) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center space-y-4">
          <Spinner size="lg" />
          <p className="text-gray-600">Searching across reference sources...</p>
        </div>
      </div>
    );
  }

  // Show empty state
  if (!hasResults && !isSearching) {
    return (
      <Alert color="info" icon={Info}>
        <div className="space-y-2">
          <p className="font-medium">No results found</p>
          <p className="text-sm">
            Try adjusting your search query or selecting different sources.
          </p>
        </div>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      {/* Error alerts */}
      {hasErrors && (
        <Alert color="warning" icon={AlertCircle}>
          <div className="space-y-2">
            <p className="font-medium">Some sources encountered errors:</p>
            <ul className="list-disc list-inside text-sm space-y-1">
              {Object.entries(errors).map(([source, error]) => (
                <li key={source}>
                  <strong>{SOURCE_METADATA[source]?.label || source}:</strong> {error}
                </li>
              ))}
            </ul>
          </div>
        </Alert>
      )}

      {/* Results summary */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          Showing {results.length} of {total} results
          {isSearching && ' (searching...)'}
        </span>

        {hasErrors && (
          <span className="text-yellow-600">
            {Object.keys(errors).length} source{Object.keys(errors).length > 1 ? 's' : ''} had errors
          </span>
        )}
      </div>

      {/* Results list */}
      <div className="space-y-4">
        {results.map((node) => (
          <ResultCard
            key={node.id}
            node={node}
            onSelect={() => handleSelectNode(node)}
            compact={compact}
          />
        ))}
      </div>

      {/* Load more */}
      {hasMore && onLoadMore && (
        <div className="text-center pt-4">
          <Button
            onClick={onLoadMore}
            disabled={isSearching}
            color="gray"
          >
            {isSearching ? (
              <>
                <Spinner size="sm" className="mr-2" />
                Loading...
              </>
            ) : (
              'Load More Results'
            )}
          </Button>
        </div>
      )}

      {/* Additional loading indicator at bottom */}
      {isSearching && hasResults && (
        <div className="text-center py-4">
          <Spinner size="sm" className="mr-2" />
          <span className="text-sm text-gray-600">Loading additional results...</span>
        </div>
      )}
    </div>
  );
};

export default SearchResults;