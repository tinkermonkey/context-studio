# API Client Pagination Updates

This document outlines the changes made to the API client to support the new pagination features with the `total` parameter.

## Summary of Changes

The API server has been updated to include a `total` field in paginated responses, allowing the client to know the total number of available items without having to fetch all pages. This update brings several improvements:

1. **Better UX**: Users can see total counts and navigate pages more effectively
2. **Performance**: No need to fetch all pages just to know the total count
3. **Infinite Scroll**: Easier implementation of infinite scroll patterns
4. **Page Navigation**: Proper page navigation with page numbers

## Updated API Response Structure

### Before
```typescript
// API returned simple arrays
LayerOut[]
DomainOut[]
TermOut[]
```

### After
```typescript
// API now returns paginated responses
interface PaginatedResponse<T> {
  data: T[];      // The actual items
  total: number;  // Total number of items available
  skip: number;   // Number of items skipped
  limit: number;  // Maximum items per page
}
```

## Changes Made

### 1. Regenerated TypeScript Types
- Added `generate-types` script to `package.json`
- Installed `openapi-typescript` and `typescript` dev dependencies
- Regenerated `src/api/client/types.ts` from the updated OpenAPI spec

### 2. Updated Base Service (`src/api/services/base.ts`)
- Added `PaginatedResponse<T>` interface
- Updated `getAllPaginated()` method to use the new response structure
- Updated `getPage()` method to extract data from paginated response
- Added new `getPaginatedResponse()` method for accessing full pagination metadata

### 3. Updated Service Classes
All service classes now include new methods for accessing pagination metadata:

#### Layers Service (`src/api/services/layers.ts`)
- Added `listPageWithMetadata()` method
- Updated imports to include `PaginatedResponse` and `PaginatedLayersResponse` types

#### Domains Service (`src/api/services/domains.ts`)
- Added `listPageWithMetadata()` method
- Updated imports to include `PaginatedResponse` and `PaginatedDomainsResponse` types

#### Terms Service (`src/api/services/terms.ts`)
- Added `listPageWithMetadata()` method
- Updated imports to include `PaginatedResponse` and `PaginatedTermsResponse` types

### 4. Updated React Query Hooks
All hook files now include new hooks for accessing pagination metadata:

#### Layers Hooks (`src/api/hooks/layers/useLayers.ts`)
- Added `useLayersPageWithMetadata()` hook

#### Domains Hooks (`src/api/hooks/domains/useDomains.ts`)
- Added `useDomainsPageWithMetadata()` hook

#### Terms Hooks (`src/api/hooks/terms/useTerms.ts`)
- Added `useTermsPageWithMetadata()` hook

## Usage Examples

### Basic Pagination with Metadata
```tsx
import { useLayersPageWithMetadata } from '@/api';

function LayersTable() {
  const { data: response, isLoading, error } = useLayersPageWithMetadata({
    skip: 0,
    limit: 10,
    sort: 'title'
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;
  if (!response) return null;

  const { data: layers, total, skip, limit } = response;
  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  return (
    <div>
      <h2>Layers ({total} total)</h2>
      <div>
        Page {currentPage} of {totalPages}
      </div>
      <table>
        {layers.map(layer => (
          <tr key={layer.id}>
            <td>{layer.title}</td>
          </tr>
        ))}
      </table>
    </div>
  );
}
```

### Infinite Scroll Implementation
```tsx
import { useInfiniteQuery } from '@tanstack/react-query';
import { layerService } from '@/api';

function InfiniteLayersList() {
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['layers', 'infinite'],
    queryFn: async ({ pageParam = 0 }) => {
      return layerService.listPageWithMetadata({
        skip: pageParam,
        limit: 20
      });
    },
    getNextPageParam: (lastPage) => {
      const nextSkip = lastPage.skip + lastPage.limit;
      return nextSkip < lastPage.total ? nextSkip : undefined;
    }
  });

  const allLayers = data?.pages.flatMap(page => page.data) ?? [];
  const totalCount = data?.pages[0]?.total ?? 0;

  return (
    <div>
      <h2>Layers ({totalCount} total)</h2>
      {allLayers.map(layer => (
        <div key={layer.id}>{layer.title}</div>
      ))}
      {hasNextPage && (
        <button 
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
        >
          {isFetchingNextPage ? 'Loading...' : 'Load More'}
        </button>
      )}
    </div>
  );
}
```

### Pagination Helper Function
```typescript
import { calculatePaginationInfo } from '@/api/test-pagination';

// Use the helper to get comprehensive pagination info
const paginationInfo = calculatePaginationInfo(response);
// Returns:
// {
//   currentPage: 1,
//   totalPages: 5,
//   hasNextPage: true,
//   hasPreviousPage: false,
//   startItem: 1,
//   endItem: 10,
//   totalItems: 50,
//   itemsInCurrentPage: 10
// }
```

## Backward Compatibility

All existing methods continue to work as before:
- `list()` - Returns all items across all pages (unchanged)
- `listPage()` - Returns items for a single page (unchanged)

New methods provide additional functionality:
- `listPageWithMetadata()` - Returns paginated response with metadata
- `useXXXPageWithMetadata()` hooks - React Query hooks for paginated responses

## API Endpoints Affected

The following endpoints now return paginated responses:
- `GET /api/layers/` → `PaginatedLayersResponse`
- `GET /api/domains/` → `PaginatedDomainsResponse`  
- `GET /api/terms/` → `PaginatedTermsResponse`

## Migration Guide

### For Simple Lists (No Changes Required)
If you're currently using the simple list methods, no changes are required:
```typescript
// This continues to work exactly as before
const layers = await layerService.list();
const { data: layers } = useLayers();
```

### For Paginated Lists (Optional Enhancement)
If you want to take advantage of the new total count, use the new methods:
```typescript
// Before
const { data: layers } = useLayersPage({ skip: 0, limit: 10 });

// After (with total count)
const { data: response } = useLayersPageWithMetadata({ skip: 0, limit: 10 });
const { data: layers, total, skip, limit } = response;
```

## Testing

A test file `src/api/test-pagination.ts` has been created to demonstrate and verify the new pagination functionality. This file includes:
- Example usage of all new pagination methods
- Helper functions for calculating pagination metadata
- Sample code for common pagination scenarios

## Files Modified

### Core Files
- `package.json` - Added `generate-types` script and dev dependencies
- `src/api/client/types.ts` - Regenerated from updated OpenAPI spec

### Service Layer
- `src/api/services/base.ts` - Updated base service with pagination support
- `src/api/services/layers.ts` - Added pagination metadata methods
- `src/api/services/domains.ts` - Added pagination metadata methods
- `src/api/services/terms.ts` - Added pagination metadata methods

### Hook Layer
- `src/api/hooks/layers/useLayers.ts` - Added metadata hooks
- `src/api/hooks/domains/useDomains.ts` - Added metadata hooks
- `src/api/hooks/terms/useTerms.ts` - Added metadata hooks

### Documentation/Testing
- `src/api/test-pagination.ts` - Test file demonstrating new functionality
- `PAGINATION_UPDATES.md` - This documentation file
