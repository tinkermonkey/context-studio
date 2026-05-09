# Streaming Reference Search Implementation

## Overview

Implemented a client-side streaming solution for unified reference search that eliminates the bottleneck of waiting for all sources to respond. The new system calls individual source endpoints in parallel and streams results back to the UI as each source responds.

## What Was Implemented

### 1. Enhanced Types (`src/api/types/streamingReference.ts`)

- `StreamingSearchState` - Complete state management for streaming searches
- `SourceSearchUpdate` - Individual source response updates
- `StreamingSearchOptions` - Configuration options for streaming behavior
- `SOURCE_ENDPOINTS` - Configuration mapping for available source endpoints
- Helper functions for state management and initialization

### 2. Streaming Service (`src/api/services/streamingReference.ts`)

**Key Features:**

- Parallel execution of individual source endpoint calls
- Real-time callback-based updates as sources respond
- Configurable timeouts and retry logic per source
- Graceful error handling with partial results
- AbortController support for cancellation

**Main Methods:**

- `searchStreaming()` - Core streaming search with callbacks
- `searchAllSources()` - Promise-based API that resolves when complete
- `getSourceStatus()` - Check available sources

### 3. Streaming Hooks (`src/api/hooks/unifiedReference/useStreamingReference.ts`)

**Primary Hooks:**

- `useStreamingUnifiedSearch` - Main hook for streaming search with real-time state
- `useSourceLoadingStates` - Track per-source loading/completion states
- `useStreamingSearchMutation` - React Query mutation pattern for streaming
- `useSearchComparison` - Performance metrics and comparison utilities

**Additional Utilities:**

- `usePrefetchStreamingSearch` - Background prefetching
- `useCachedStreamingResults` - Access cached streaming results

### 4. Enhanced Unified Service (`src/api/services/unifiedReference.ts`)

**New Methods Added:**

- `searchSource(source, request)` - Search individual sources directly
- `searchSpecificSources(sources, request)` - Search subset of sources
- `getAvailableSources()` - Get source configuration and status
- `testSourceConnectivity(source)` - Test individual source connectivity

### 5. Enhanced Unified Hooks (`src/api/hooks/unifiedReference/useUnifiedReference.ts`)

**New Hooks Added:**

- `useSourceSearch` - Query hook for individual source search
- `useSourceSearchMutation` - Mutation for individual source search
- `useAvailableSources` - Get available sources and their status
- `useSourceConnectivity` - Test source connectivity
- `useSpecificSourcesSearch` - Search multiple specific sources

## Usage Examples

### Basic Streaming Search

```typescript
import { useStreamingUnifiedSearch } from '@/api/hooks/unifiedReference/useStreamingReference';

function SearchComponent() {
  const {
    search,
    searchState,
    isSearching,
    hasResults,
    results,
    completedSources,
    errorSources
  } = useStreamingUnifiedSearch({
    onComplete: (state) => console.log('Search complete:', state),
    onSourceUpdate: (update) => console.log('Source update:', update)
  });

  const handleSearch = () => {
    search({ query: 'artificial intelligence', limit: 10 });
  };

  return (
    <div>
      <button onClick={handleSearch} disabled={isSearching}>
        Search
      </button>

      {searchState && (
        <div>
          <p>Sources completed: {completedSources.length}</p>
          <p>Sources with errors: {errorSources.length}</p>
          <p>Results so far: {results.length}</p>
        </div>
      )}
    </div>
  );
}
```

### Per-Source Loading States

```typescript
import { useSourceLoadingStates } from '@/api/hooks/unifiedReference/useStreamingReference';

function SourceStatusIndicator({ searchState }: { searchState: StreamingSearchState }) {
  const { sourceStates, isSourceLoading, isSourceComplete } = useSourceLoadingStates(searchState);

  return (
    <div>
      {Object.entries(sourceStates).map(([source, state]) => (
        <div key={source}>
          {source}: {isSourceLoading(source) ? 'Loading...' : isSourceComplete(source) ? 'Complete' : 'Pending'}
          {state.results && <span> ({state.results.length} results)</span>}
        </div>
      ))}
    </div>
  );
}
```

### Individual Source Search

```typescript
import { useSourceSearchMutation } from '@/api/hooks/unifiedReference/useUnifiedReference';

function DBpediaSearch() {
  const dbpediaSearch = useSourceSearchMutation('dbpedia');

  const handleSearch = () => {
    dbpediaSearch.mutate({ query: 'machine learning' });
  };

  return (
    <div>
      <button onClick={handleSearch} disabled={dbpediaSearch.isPending}>
        Search DBpedia Only
      </button>
      {dbpediaSearch.data && (
        <div>Found {dbpediaSearch.data.results.length} results from DBpedia</div>
      )}
    </div>
  );
}
```

## Architecture Benefits

### Performance Improvements

- **First Result Speed**: Users see results as soon as the fastest source responds
- **No Blocking**: Slow sources don't prevent fast sources from displaying results
- **Parallel Execution**: All sources searched simultaneously on client-side

### User Experience

- **Progressive Loading**: Results appear incrementally
- **Source-Specific Feedback**: Users see which sources are loading/complete/errored
- **Cancellation Support**: Users can cancel searches in progress

### Fault Tolerance

- **Partial Results**: Failed sources don't prevent successful ones from showing results
- **Retry Logic**: Configurable retry attempts for failed sources
- **Graceful Degradation**: System works even when some sources are unavailable

## Configuration

### Enabling/Disabling Sources

Update `SOURCE_ENDPOINTS` in `src/api/types/streamingReference.ts`:

```typescript
export const SOURCE_ENDPOINTS: Record<SourceType, SourceEndpointConfig> = {
  dbpedia: {
    endpoint: "/api/reference/dbpedia/search",
    enabled: true, // Toggle availability
    timeout: 5000,
    priority: 1,
  },
  // ... other sources
};
```

### Timeout Configuration

Per-source timeouts can be configured in the `SOURCE_ENDPOINTS` or overridden in search options:

```typescript
const { search } = useStreamingUnifiedSearch({
  timeout: 8000, // Override default timeout
});
```

## Backward Compatibility

- All existing hooks and services remain unchanged
- Original unified search endpoint `/api/reference/search` still works
- New functionality is additive, not replacing existing patterns
- Existing components can be gradually migrated to streaming approach

## Available Endpoints

Currently configured endpoints:

- `/api/reference/dbpedia/search` (enabled)
- `/api/reference/schema-org/search` (enabled)
- `/api/reference/conceptnet/search` (disabled - enable when available)
- `/api/reference/wikidata/search` (disabled - enable when available)

## Performance Monitoring

Use `useSearchComparison` hook to track performance improvements:

```typescript
const { trackStreamingSearch, metrics, getPerformanceImprovement } =
  useSearchComparison();

// Track streaming search performance
trackStreamingSearch(searchState);

// Get improvement percentage over unified search
const improvement = getPerformanceImprovement(); // e.g., 65% faster first result
```

## Next Steps

1. Enable additional source endpoints as they become available
2. Implement result deduplication across sources
3. Add source-priority weighting for result ordering
4. Consider implementing result streaming for very large datasets
5. Add analytics to track source performance and reliability
