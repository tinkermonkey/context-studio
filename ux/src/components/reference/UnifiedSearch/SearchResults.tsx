/**
 * SearchResults Component
 *
 * Displays unified search results
 */

import React from "react";
import { Card, Badge, Button, Alert, Spinner } from "flowbite-react";
import { ExternalLink, AlertCircle, Info } from "lucide-react";
import { UnifiedNode } from "@/api/types/unified";
import { SOURCE_METADATA } from "@/api/types/unified";

interface SearchResultsProps {
  results: UnifiedNode[];
  totalResults: number;
  onSelectNode?: (node: UnifiedNode) => void;
  onLoadMore?: () => void;
  isSearching?: boolean;
  sourceErrors?: Record<string, string>;
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
  compact = false,
}) => {
  const sourceMetadata = SOURCE_METADATA[node.source] || {
    label: node.source,
    color: "gray",
    description: "",
  };

  const confidencePercent = Math.round((node.confidence_score || 0) * 100);

  return (
    <div style={style} className="px-2 pb-4">
      <Card
        className="h-full cursor-pointer transition-shadow hover:shadow-lg"
        onClick={onSelect}
      >
        <div className="flex h-full flex-col space-y-3">
          {/* Content */}
          <div className="flex-1">
            <h3 className="mb-2 line-clamp-2 text-lg font-semibold">
              {node.title}
            </h3>

            {!compact && node.definition && (
              <p className="mb-3 line-clamp-3 text-sm text-gray-600">
                {node.definition}
              </p>
            )}
          </div>

          {/* Metadata badges */}
          <div className="flex flex-wrap gap-2">
            <Badge color={sourceMetadata.color as any}>
              {sourceMetadata.label}
            </Badge>

            {(node.confidence_score || 0) < 1 && (
              <Badge color="gray" size="sm">
                {confidencePercent}% match
              </Badge>
            )}

            {node.merged_from && node.merged_from.length > 0 && (
              <Badge color="purple" size="sm">
                Merged from {node.merged_from.length} source{node.merged_from.length > 1 ? 's' : ''}
              </Badge>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between border-t border-gray-100 pt-2">
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
                  window.open(node.source_url, "_blank");
                }}
                className="flex items-center gap-1"
              >
                <ExternalLink className="h-3 w-3" />
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
  results,
  totalResults,
  onSelectNode,
  onLoadMore,
  isSearching = false,
  sourceErrors = {},
  compact = false,
}) => {
  const hasResults = results.length > 0;
  const hasErrors = Object.keys(sourceErrors).length > 0;
  const hasMore = results.length < totalResults;

  const handleSelectNode = (node: UnifiedNode) => {
    onSelectNode?.(node);
  };


  // Show loading state during search
  if (isSearching && !hasResults) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="space-y-4 text-center">
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
            <ul className="list-inside list-disc space-y-1 text-sm">
              {Object.entries(sourceErrors).map(([source, error]) => (
                <li key={source}>
                  <strong>{SOURCE_METADATA[source]?.label || source}:</strong>{" "}
                  {error}
                </li>
              ))}
            </ul>
          </div>
        </Alert>
      )}

      {/* Results summary */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          Showing {results.length} of {totalResults} results
          {isSearching && " (searching...)"}
        </span>

        {hasErrors && (
          <span className="text-yellow-600">
            {Object.keys(sourceErrors).length} source
            {Object.keys(sourceErrors).length > 1 ? "s" : ""} had errors
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
        <div className="pt-4 text-center">
          <Button onClick={onLoadMore} disabled={isSearching} color="gray">
            {isSearching ? (
              <>
                <Spinner size="sm" className="mr-2" />
                Loading...
              </>
            ) : (
              "Load More Results"
            )}
          </Button>
        </div>
      )}

      {/* Additional loading indicator at bottom */}
      {isSearching && hasResults && (
        <div className="py-4 text-center">
          <Spinner size="sm" className="mr-2" />
          <span className="text-sm text-gray-600">
            Loading additional results...
          </span>
        </div>
      )}
    </div>
  );
};

export default SearchResults;
