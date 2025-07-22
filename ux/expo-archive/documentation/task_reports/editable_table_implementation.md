# Editable Table Component Implementation

## Overview

The `EditableTable` component is a comprehensive, reusable table component designed for viewing and editing nodes (layers, domains, terms) in the Context Studio application. It provides in-place editing capabilities, pagination, search functionality, and integrates seamlessly with the existing API client architecture.

## Architecture

### Core Components

1. **`EditableTable`** - The main generic table component
2. **`LayerTable`** - Specialized wrapper for layer entities
3. **`DomainTable`** - Specialized wrapper for domain entities  
4. **`TermTable`** - Specialized wrapper for term entities

### Key Features

- **In-place editing**: Click on title or definition cells to edit directly
- **Pagination**: Navigate through large datasets with configurable page sizes
- **Search**: Real-time search with debouncing using vector search API
- **Type-safe**: Full TypeScript support with proper type inference
- **Responsive**: Works across desktop, tablet, and mobile devices
- **Error handling**: Comprehensive error handling with user-friendly messages

## Implementation Details

### File Structure

```
components/
├── common/
│   ├── EditableTable.tsx          # Main generic table component
│   ├── LayerTable.tsx             # Layer-specific table wrapper
│   ├── DomainTable.tsx            # Domain-specific table wrapper
│   ├── TermTable.tsx              # Term-specific table wrapper
│   └── index.ts                   # Barrel exports
├── examples/
│   └── EditableTableExample.tsx   # Usage examples
└── hooks/
    └── useDebounce.ts             # Debounce hook for search
```

### Data Flow

1. **Data Loading**: Uses React Query hooks for efficient data fetching and caching
2. **Search Integration**: Debounced search queries trigger vector search API calls
3. **Mutations**: Update and delete operations use optimistic updates with rollback on error
4. **State Management**: Local state for editing, pagination, and search with global cache invalidation

### Column Configuration

The table automatically displays relevant columns based on node type:

- **Common columns**: ID, Title, Definition, Created At, Last Modified
- **Relationship columns**: 
  - Domains: Layer ID
  - Terms: Domain ID
- **Actions column**: Edit and Delete buttons (optional)

### API Integration

The component integrates with the existing API client architecture:

- Uses typed service clients (`layerService`, `domainService`, `termService`)
- Implements proper error handling with `handleApiError`
- Leverages React Query for caching and optimistic updates
- Supports vector search through `/find` endpoints

## Usage Examples

### Basic Layer Table

```tsx
import { LayerTable } from '../common';

export const LayersPage = () => {
  return (
    <LayerTable
      showActions={true}
      enableInlineEdit={true}
      enableSearch={true}
      enablePagination={true}
      pageSize={20}
    />
  );
};
```

### Domain Table with Layer Filter

```tsx
import { DomainTable } from '../common';

export const DomainsPage = () => {
  return (
    <DomainTable
      layerId="specific-layer-id"
      enableSearch={true}
      pageSize={10}
    />
  );
};
```

### Custom Table Configuration

```tsx
import { EditableTable } from '../common';
import { useLayers, useUpdateLayer } from '../../api/hooks/layers';

export const CustomLayerTable = () => {
  const { data, isLoading, error } = useLayers();
  const updateLayer = useUpdateLayer();

  const handleUpdate = async (id: string, updateData: LayerUpdate) => {
    await updateLayer.mutateAsync({ id, data: updateData });
  };

  return (
    <EditableTable
      nodeType="layer"
      data={data || []}
      isLoading={isLoading}
      error={error}
      onUpdate={handleUpdate}
      enableInlineEdit={true}
      showActions={false}
    />
  );
};
```

## Technical Specifications

### Props Interface

```typescript
interface EditableTableProps {
  nodeType: 'layer' | 'domain' | 'term';
  data: NodeData[];
  isLoading: boolean;
  error: Error | null;
  onUpdate: (id: string, updateData: UpdateData) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
  onRefresh: () => void;
  onSearch?: (query: string, searchField: 'title' | 'definition') => void;
  pagination?: {
    skip: number;
    limit: number;
    total?: number;
    onPageChange: (skip: number, limit: number) => void;
  };
  showActions?: boolean;
  enableInlineEdit?: boolean;
  enableSearch?: boolean;
  enablePagination?: boolean;
}
```

### State Management

- **Edit State**: Tracks currently editing cell with ID, field, and value
- **Search State**: Manages search query and active search mode
- **Pagination State**: Handles current page offset and limit
- **Update State**: Tracks which row is currently being updated

### Performance Optimizations

- **Debounced Search**: 300ms delay to prevent excessive API calls
- **React Query Caching**: Efficient data caching and invalidation
- **Optimistic Updates**: Immediate UI updates with rollback on error
- **Conditional Rendering**: Only render necessary components based on configuration

## Error Handling

The component implements comprehensive error handling:

- **API Errors**: Caught and displayed using the global error handler
- **Validation Errors**: Inline validation for edit operations
- **Network Errors**: Graceful handling of connectivity issues
- **Fallback States**: Loading spinners and error messages

## Testing Strategy

### Unit Tests
- Component rendering with different props
- Edit functionality and state management
- Search and pagination behavior
- Error handling scenarios

### Integration Tests
- API integration with mock services
- React Query cache invalidation
- End-to-end user workflows

## Future Enhancements

1. **Column Customization**: Allow users to show/hide specific columns
2. **Bulk Operations**: Select multiple rows for batch updates/deletes
3. **Sorting**: Client-side and server-side sorting capabilities
4. **Export Functionality**: Export table data to CSV/JSON
5. **Advanced Filtering**: Multiple filter criteria and operators
6. **Keyboard Navigation**: Full keyboard accessibility support

## Dependencies

- **React**: Core framework
- **React Query**: Data fetching and caching
- **Gluestack UI v2**: Component library
- **TypeScript**: Type safety
- **Tailwind CSS**: Styling (via Nativewind)
- **React Native**: Cross-platform compatibility

## Known Issues

1. **Search Persistence**: Search state doesn't persist across page navigation
2. **Mobile Optimization**: Table may need horizontal scrolling on small screens
3. **Large Datasets**: Performance may degrade with extremely large datasets

## Conclusion

The `EditableTable` component provides a robust, feature-rich solution for data management in the Context Studio application. It follows React best practices, integrates seamlessly with the existing architecture, and provides an excellent user experience for viewing and editing node data.
