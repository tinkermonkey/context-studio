# API Client Pagination Implementation

## Overview

Updated the Context Studio API client to properly handle server-side pagination and load all data when needed. The server has a default page size of 50 items and a maximum page size of 100 items.

## Changes Made

### 1. Base Service Updates (`/src/api/services/base.ts`)

- Added `PaginationConfig` interface to define pagination settings
- Added pagination configuration with default page size (50) and max page size (100)
- Implemented `getAllPaginated<T>()` method to fetch all pages of data automatically
- Implemented `getPage<T>()` method for single page requests

### 2. Service Layer Updates

Updated all service classes to support both paginated and full data loading:

- **LayerService** (`/src/api/services/layers.ts`)
- **DomainService** (`/src/api/services/domains.ts`)  
- **TermService** (`/src/api/services/terms.ts`)
- **RelationshipService** (`/src/api/services/relationships.ts`)

Each service now provides:
- `list(params?)` - Loads ALL data across multiple pages (unless `limit` is explicitly set)
- `listPage(params?)` - Loads a single page of data

### 3. Hook Layer Updates

Updated React Query hooks to provide both pagination strategies:

- **useLayers/useLayersPage** - Layers data loading
- **useDomains/useDomainsPage** - Domains data loading  
- **useTerms/useTermsPage** - Terms data loading
- **useRelationships/useRelationshipsPage** - Relationships data loading

### 4. API Client Exports

Updated main API index file to export the new `base` service types and interfaces.

## Usage Patterns

### Load All Data (Default Behavior)
```typescript
// This will now load ALL layers across multiple API calls
const { data: allLayers } = useLayers();

// Same behavior for other entities
const { data: allDomains } = useDomains();
const { data: allTerms } = useTerms();
```

### Load Single Page
```typescript
// Load just one page with specific pagination
const { data: layersPage } = useLayersPage({ 
  skip: 0, 
  limit: 20 
});

// Load page with filtering
const { data: domainsPage } = useDomainsPage({ 
  layer_id: "some-layer-id",
  skip: 50,
  limit: 25 
});
```

### Explicit Limit (Single Page)
```typescript
// When limit is explicitly set, only one page is fetched
const { data: limitedLayers } = useLayers({ limit: 10 });
```

## Implementation Details

### Pagination Logic

The `getAllPaginated()` method:
1. Uses the maximum page size (100) for efficiency
2. Makes repeated API calls with increasing `skip` values
3. Continues until fewer items than the limit are returned
4. Concatenates all results into a single array

### Backward Compatibility

- Existing code continues to work without changes
- Default behavior now loads all data instead of just the first page
- UI components will now show all available data instead of being limited to 50 items

### Performance Considerations

- Loading all data may result in multiple API calls for large datasets
- Use `listPage()` methods when you only need a specific page
- Consider implementing infinite scroll or virtual scrolling for very large datasets
- Query caching via TanStack Query helps reduce redundant API calls

## Benefits

1. **Fixed Data Limitation**: UI components now show all available data instead of just the first 50 items
2. **Flexible Usage**: Developers can choose between loading all data or specific pages
3. **Backward Compatible**: Existing code continues to work
4. **Efficient**: Uses maximum page size to minimize API calls when loading all data
5. **Type Safe**: Full TypeScript support with proper type definitions

## Future Enhancements

Consider implementing:
- Infinite scroll pagination for large datasets
- Virtual scrolling in table components
- Server-side filtering and sorting
- Real-time updates via WebSockets or polling
