/**
 * UnifiedSearchBar Component
 *
 * Main search interface for unified reference search across multiple sources
 */

import React, { useState, useCallback, useEffect } from 'react';
import { TextInput, Button, Spinner, Select } from 'flowbite-react';
import { Search, X } from 'lucide-react';
import { debounce } from 'lodash';
import { useUnifiedSearch } from '@/api/hooks/unifiedReference/useUnifiedReference';
import { useReferenceStore, useSearchState } from '@/store/referenceSlice';
import { UnifiedSearchRequest } from '@/api/types/unified';

interface UnifiedSearchBarProps {
  placeholder?: string;
  minQueryLength?: number;
  debounceMs?: number;
  autoFocus?: boolean;
  disabled?: boolean;
  onSearchStart?: () => void;
  onSearchComplete?: () => void;
  onError?: (error: Error) => void;
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
}) => {
  const [localQuery, setLocalQuery] = useState('');

  const {
    query: storeQuery,
    type: searchType,
    isSearching,
  } = useSearchState();

  const {
    selectedSources,
    setSearchQuery,
    setSearchType,
    setIsSearching,
    setSearchResults,
    setSourceErrors,
    addToHistory,
  } = useReferenceStore();

  const { mutate: search, isPending, reset } = useUnifiedSearch({
    onSuccess: (data) => {
      setSearchResults(data.results, data.total_results);
      setSourceErrors(data.source_errors || {});
      setIsSearching(false);
      addToHistory(data.query);
      onSearchComplete?.();
    },
    onError: (error: Error) => {
      setIsSearching(false);
      console.error('Search failed:', error);
      onError?.(error);
    },
  });

  // Debounced search function
  const debouncedSearch = useCallback(
    debounce((searchQuery: string) => {
      if (searchQuery.trim().length >= minQueryLength && selectedSources.length > 0) {
        const request: UnifiedSearchRequest = {
          query: searchQuery,
          search_type: searchType,
          sources: selectedSources,
          limit: 20,
          offset: 0,
        };

        setIsSearching(true);
        onSearchStart?.();
        search(request);
      } else if (searchQuery.trim().length === 0) {
        // Clear results if query is empty
        setSearchResults([], 0);
        setSourceErrors({});
      }
    }, debounceMs),
    [searchType, selectedSources, minQueryLength, search, setIsSearching, setSearchResults, setSourceErrors, onSearchStart]
  );

  // Trigger search when local query changes
  useEffect(() => {
    setSearchQuery(localQuery);
    debouncedSearch(localQuery);
  }, [localQuery, debouncedSearch, setSearchQuery]);

  // Sync local query with store query when it changes externally
  useEffect(() => {
    if (storeQuery !== localQuery) {
      setLocalQuery(storeQuery);
    }
  }, [storeQuery, localQuery]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      debouncedSearch.cancel();
    };
  }, [debouncedSearch]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalQuery(e.target.value);
  };

  const handleClear = () => {
    setLocalQuery('');
    setSearchQuery('');
    setSearchResults([], 0);
    setSourceErrors({});
    reset();
  };

  const handleSearchTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newType = e.target.value as 'title' | 'definition';
    setSearchType(newType);
    // Re-trigger search with new type if there's a query
    if (localQuery.trim().length >= minQueryLength) {
      debouncedSearch(localQuery);
    }
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
            placeholder={hasNoSources ? "Please select at least one source..." : placeholder}
            value={localQuery}
            onChange={handleInputChange}
            disabled={disabled || hasNoSources}
            autoFocus={autoFocus}
            className="pr-10"
            color={hasNoSources ? "failure" : undefined}
          />

          {/* Clear button */}
          {showClearButton && !showSpinner && (
            <button
              onClick={handleClear}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Clear search"
            >
              <X className="w-5 h-5" />
            </button>
          )}

          {/* Loading spinner */}
          {showSpinner && (
            <div className="absolute right-2 top-1/2 -translate-y-1/2">
              <Spinner size="sm" />
            </div>
          )}
        </div>

        {/* Search Type Selector */}
        <Select
          value={searchType}
          onChange={handleSearchTypeChange}
          disabled={disabled}
          className="w-40"
        >
          <option value="title">Search Titles</option>
          <option value="definition">Search Definitions</option>
        </Select>
      </div>

      {/* Search Status */}
      {hasNoSources && (
        <div className="text-sm text-red-600 bg-red-50 p-2 rounded-md">
          Please select at least one reference source to search.
        </div>
      )}

      {localQuery.length > 0 && localQuery.length < minQueryLength && (
        <div className="text-sm text-yellow-600 bg-yellow-50 p-2 rounded-md">
          Query must be at least {minQueryLength} characters long.
        </div>
      )}
    </div>
  );
};

export default UnifiedSearchBar;