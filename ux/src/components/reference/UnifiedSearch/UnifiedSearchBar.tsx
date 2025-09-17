/**
 * UnifiedSearchBar Component
 *
 * Main search interface for unified reference search across multiple sources
 */

import React, { useState, useCallback, useEffect } from "react";
import { TextInput, Spinner, Button } from "flowbite-react";
import { Search, X } from "lucide-react";
import { useUnifiedSearch } from "@/api/hooks/unifiedReference/useUnifiedReference";
import { UnifiedSearchRequest, SourceType, UnifiedNode } from "@/api/types/unified";
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
}

export const UnifiedSearchBar: React.FC<UnifiedSearchBarProps> = ({
  placeholder = "Search across all reference sources...",
  minQueryLength = 2,
  debounceMs = 300,
  autoFocus = false,
  disabled = false,
  onSearchStart,
  onSearchComplete,
  onError,
  selectedSources = ["conceptnet", "dbpedia", "wikidata", "schema_org"],
  onSourcesChange,
}) => {
  const [localQuery, setLocalQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [sourceErrors, setSourceErrors] = useState<Record<string, string>>({});

  const {
    mutate: search,
    isPending,
    reset,
  } = useUnifiedSearch({
    onSuccess: (data) => {
      setSourceErrors(data.source_errors || {});
      setIsSearching(false);
      onSearchComplete?.(data.results, data.total_results);
    },
    onError: (error: Error) => {
      setIsSearching(false);
      console.error("Search failed:", error);
      onError?.(error);
    },
  });

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

      setIsSearching(true);
      onSearchStart?.();
      search(request);
    }
  }, [
    localQuery,
    selectedSources,
    minQueryLength,
    search,
    setIsSearching,
    onSearchStart,
  ]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalQuery(e.target.value);
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
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
    setSourceErrors({});
    reset();
  };


  const showSpinner = isPending || isSearching;
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
            onKeyPress={handleKeyPress}
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
          disabled={disabled || hasNoSources || localQuery.trim().length < minQueryLength}
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
    </div>
  );
};

export default UnifiedSearchBar;
