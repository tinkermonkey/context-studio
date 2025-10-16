/**
 * SearchResults Component
 *
 * Displays unified search results
 */

import React from "react";
import { Card, Badge, Button, Alert, Spinner } from "flowbite-react";
import { ExternalLink, AlertCircle, Info, Clock, CheckCircle, XCircle } from "lucide-react";
import { UnifiedNode, SourceType } from "@/api/types/unified";
import { SOURCE_METADATA } from "@/api/types/unified";
import { StreamingSearchState, SourceSearchUpdate } from "@/api/types/streamingReference";
import { useSourceLoadingStates } from "@/api/hooks/unifiedReference/useStreamingReference";
import { getSourceBadgeColor, getSourceLabel } from "@/utils/sourceUtils";

interface SearchResultsProps {
  results: UnifiedNode[];
  totalResults: number;
  onSelectNode?: (node: UnifiedNode) => void;
  onLoadMore?: () => void;
  isSearching?: boolean;
  sourceErrors?: Record<string, string>;
  compact?: boolean;
  streamingState?: StreamingSearchState | null;
  showSourceProgress?: boolean;
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
  const relevancePercent = Math.round((node.relevance_score || 0) * 100);

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
            <Badge color={getSourceBadgeColor(node.source)}>
              {getSourceLabel(node.source)}
            </Badge>

            {(node.relevance_score || 0) < 1 && (
              <Badge color="gray" size="sm">
                {relevancePercent}% match
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
                  if (node.source_url) {
                    window.open(node.source_url, "_blank");
                  }
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
  streamingState = null,
  showSourceProgress = true,
}) => {
  const hasResults = results.length > 0;
  const hasErrors = Object.keys(sourceErrors).length > 0;
  const hasMore = results.length < totalResults;

  const sourceLoadingStates = useSourceLoadingStates(streamingState);

  const handleSelectNode = (node: UnifiedNode) => {
    onSelectNode?.(node);
  };

  // Render source progress indicators
  const renderSourceProgress = () => {
    if (!showSourceProgress || !streamingState) return null;

    return (
      <div className="mb-4 space-y-2">
        <h4 className="text-sm font-medium text-gray-700">Source Progress</h4>
        <div className="flex flex-wrap gap-2">
          {Object.entries(streamingState.sources).map(([source, sourceUpdate]) => {
            const metadata = SOURCE_METADATA[source as SourceType];
            const isLoading = sourceLoadingStates.isSourceLoading(source as SourceType);
            const isComplete = sourceLoadingStates.isSourceComplete(source as SourceType);
            const isError = sourceLoadingStates.isSourceError(source as SourceType);
            const resultCount = sourceUpdate.results?.length || 0;
            const executionTime = sourceLoadingStates.getSourceExecutionTime(source as SourceType);

            let icon;
            let color: "gray" | "blue" | "green" | "red" = "gray";
            let statusText = "Pending";

            if (isLoading) {
              icon = <Clock className="h-3 w-3" />;
              color = "blue";
              statusText = "Loading...";
            } else if (isComplete) {
              icon = <CheckCircle className="h-3 w-3" />;
              color = "green";
              statusText = `${resultCount} results`;
              if (executionTime) {
                statusText += ` (${executionTime}ms)`;
              }
            } else if (isError) {
              icon = <XCircle className="h-3 w-3" />;
              color = "red";
              statusText = "Error";
            }

            return (
              <div
                key={source}
                className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
              >
                <div className={`flex items-center gap-1 text-${color}-600`}>
                  {icon}
                  {isLoading && <Spinner size="xs" />}
                </div>
                <span className="font-medium">{metadata?.label || source}</span>
                <span className="text-gray-500">{statusText}</span>
              </div>
            );
          })}
        </div>
      </div>
    );
  };


  // Show loading state during search
  if (isSearching && !hasResults) {
    return (
      <div className="space-y-6">
        {renderSourceProgress()}
        <div className="flex items-center justify-center py-12">
          <div className="space-y-4 text-center">
            <Spinner size="lg" />
            <p className="text-gray-600">Searching across reference sources...</p>
            {streamingState && (
              <p className="text-sm text-gray-500">
                {streamingState.completedSources.length} of {Object.keys(streamingState.sources).length} sources complete
              </p>
            )}
          </div>
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
      {/* Source Progress */}
      {renderSourceProgress()}

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

      {/* Streaming errors from state */}
      {streamingState && streamingState.errorSources.length > 0 && (
        <Alert color="warning" icon={AlertCircle}>
          <div className="space-y-2">
            <p className="font-medium">Source errors during streaming search:</p>
            <div className="text-sm">
              {streamingState.errorSources.map(source => {
                const error = sourceLoadingStates.getSourceError(source);
                return (
                  <div key={source}>
                    <strong>{SOURCE_METADATA[source]?.label || source}:</strong>{" "}
                    {error || "Unknown error"}
                  </div>
                );
              })}
            </div>
          </div>
        </Alert>
      )}

      {/* Results summary */}
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>
          Showing {results.length} of {totalResults} results
          {isSearching && " (searching...)"}
          {streamingState && !streamingState.isComplete && (
            <span className="ml-2 text-blue-600">
              • {streamingState.completedSources.length} of {Object.keys(streamingState.sources).length} sources complete
            </span>
          )}
        </span>

        {(hasErrors || (streamingState && streamingState.errorSources.length > 0)) && (
          <span className="text-yellow-600">
            {(Object.keys(sourceErrors).length + (streamingState?.errorSources.length || 0))} source
            {(Object.keys(sourceErrors).length + (streamingState?.errorSources.length || 0)) > 1 ? "s" : ""} had errors
          </span>
        )}
      </div>

      {/* Results list */}
      <div className="space-y-4">
        {results.map((node, index) => (
          <ResultCard
            key={`${node.source}-${node.id}-${index}`}
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
