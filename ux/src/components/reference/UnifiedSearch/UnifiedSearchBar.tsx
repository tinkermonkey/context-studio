/**
 * UnifiedSearchBar Component
 *
 * Main search interface for unified reference search across multiple sources
 */

import React, { useState, useCallback} from "react";
import { Badge, Button, Spinner, TextInput  } from "flowbite-react";;
import { Search, X, Clock, CheckCircle, XCircle } from "lucide-react";
import {
  useStreamingUnifiedSearch,
  useSourceLoadingStates,
} from "@/api/hooks/unifiedReference/useStreamingReference";
import {
  UnifiedSearchRequest,
  SourceType,
  UnifiedNode,
  SOURCE_METADATA,
} from "@/api/types/unified";
import { SourceDropdown } from "./SourceDropdown";

interface UnifiedSearchBarProps {
  placeholder?: string;
  minQueryLength?: number;
  debounceMs?: number;
  autoFocus?: boolean;
  disabled?: boolean;
  onSearchStart?: () => void;
  onSearchComplete?: (results: UnifiedNode[], total: number) => void;
  onError?: (error: Error) => void;
  selectedSources?: SourceType[];
  onSourcesChange?: (sources: SourceType[]) => void;
  showSourceStatus?: boolean;
}

export const UnifiedSearchBar: React.FC<UnifiedSearchBarProps> = ({
  placeholder = "Search across all reference sources...",
  minQueryLength = 2,
  autoFocus = false,
  disabled = false,
  onSearchStart,
  onSearchComplete,
  onError,
  selectedSources = ["dbpedia", "schema_org", "conceptnet", "wikidata"],
  onSourcesChange,
  showSourceStatus = true,
}) => {
  const [localQuery, setLocalQuery] = useState("");

  const {
    search,
    searchState,
    isSearching,
  } = useStreamingUnifiedSearch({
    onComplete: (state) => {
      onSearchComplete?.(state.aggregatedResults, state.totalResults);
    },
    onSourceUpdate: (update) => {
      // Call onSearchComplete with partial results as they arrive
      if (update.status === "completed" && update.results) {
        // Get current aggregated results from the search state
        const currentResults = searchState?.aggregatedResults || [];
        const currentTotal = searchState?.totalResults || 0;
        onSearchComplete?.(currentResults, currentTotal);
      }
    },
  });

  const sourceLoadingStates = useSourceLoadingStates(searchState);

  // Manual search function (only called when user explicitly searches)
  const performSearch = useCallback(() => {
    if (
      localQuery.trim().length >= minQueryLength &&
      selectedSources.length > 0
    ) {
      const request: UnifiedSearchRequest = {
        query: localQuery.trim(),
        sources: selectedSources as SourceType[],
        limit: 20,
        offset: 0,
      };

      onSearchStart?.();
      search(request).catch((error: Error) => {
        console.error("Search failed:", error);
        onError?.(error);
      });
    }
  }, [
    localQuery,
    selectedSources,
    minQueryLength,
    search,
    onSearchStart,
    onError,
  ]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalQuery(e.target.value);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      performSearch();
    }
  };

  const handleSearchClick = () => {
    performSearch();
  };

  const handleClear = () => {
    setLocalQuery("");
    onSearchComplete?.([], 0);
  };

  const showSpinner = isSearching;
  const showClearButton = localQuery.length > 0;
  const hasNoSources = selectedSources.length === 0;

  return (
    <div className="space-y-4">
      {/* Search Input Row */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <TextInput
            icon={Search}
            placeholder={
              hasNoSources
                ? "Please select at least one source..."
                : placeholder
            }
            value={localQuery}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            disabled={disabled || hasNoSources}
            autoFocus={autoFocus}
            className="pr-10"
            color={hasNoSources ? "failure" : undefined}
          />

          {/* Clear button */}
          {showClearButton && !showSpinner && (
            <button
              onClick={handleClear}
              className="absolute top-1/2 right-2 -translate-y-1/2 text-gray-400 transition-colors hover:text-gray-600"
              aria-label="Clear search"
            >
              <X className="h-5 w-5" />
            </button>
          )}

          {/* Loading spinner */}
          {showSpinner && (
            <div className="absolute top-1/2 right-2 -translate-y-1/2">
              <Spinner size="sm" />
            </div>
          )}
        </div>

        {/* Search Button */}
        <Button
          onClick={handleSearchClick}
          disabled={
            disabled ||
            hasNoSources ||
            localQuery.trim().length < minQueryLength
          }
          className="flex items-center gap-2"
        >
          <Search className="h-4 w-4" />
          Search
        </Button>

        {/* Source Selector Dropdown */}
        <SourceDropdown
          selectedSources={selectedSources}
          onSourcesChange={onSourcesChange}
        />
      </div>

      {/* Search Status */}
      {hasNoSources && (
        <div className="rounded-md bg-red-50 p-2 text-sm text-red-600">
          Please select at least one reference source to search.
        </div>
      )}

      {localQuery.length > 0 && localQuery.length < minQueryLength && (
        <div className="rounded-md bg-yellow-50 p-2 text-sm text-yellow-600">
          Query must be at least {minQueryLength} characters long.
        </div>
      )}

      {/* Source Status Indicators */}
      {showSourceStatus && searchState && (
        <div className="flex flex-wrap gap-2">
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
                className="flex items-center gap-1 text-xs"
              >
                {icon}
                {metadata?.label || source}
                {isComplete && ` (${resultCount})`}
                {isLoading && <Spinner size="xs" />}
              </Badge>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default UnifiedSearchBar;
