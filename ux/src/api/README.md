# Context Studio API Client

A type-safe, React-friendly API client for the Context Studio application, built with TypeScript, Axios, and TanStack Query.

## Architecture

The API client follows a layered architecture with the following key components:

- **Services**: HTTP client wrappers for each API resource
- **Hooks**: React Query hooks for data fetching and mutations
- **Types**: Auto-generated TypeScript types from OpenAPI spec
- **Error Handling**: Centralized error handling with user-friendly messages
- **Configuration**: Centralized API configuration

## Features

- 🔷 **Type Safety**: Auto-generated TypeScript types from OpenAPI spec
- 🔄 **Caching**: Intelligent caching with TanStack Query
- 📡 **Real-time Updates**: Automatic cache invalidation
- 🛡️ **Error Handling**: Comprehensive error handling with user feedback
- 📝 **Logging**: Structured logging for debugging
- 🎯 **Optimistic Updates**: Smooth UX with optimistic updates
- 🔄 **Retry Logic**: Automatic retry for failed requests
- 📱 **Offline Support**: Built-in offline capabilities

## Setup

### 1. Install Dependencies

```bash
npm install axios @tanstack/react-query
npm install -D openapi-typescript
```

### 2. Generate Types

```bash
npm run generate-types
```

### 3. Wrap Your App

```tsx
import { ApiProvider } from '@/api';

export default function App() {
  return (
    <ApiProvider>
      <YourApp />
    </ApiProvider>
  );
}
```

## Usage

### Basic Queries

```tsx
import { useLayers, useLayer } from '@/api/hooks/layers';

function LayerList() {
  const { data: layers, isLoading, error } = useLayers();
  const { data: layer } = useLayer('layer-id');

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <div>
      {layers?.map(layer => (
        <div key={layer.id}>{layer.title}</div>
      ))}
    </div>
  );
}
```

### Mutations

```tsx
import { useCreateLayer, useUpdateLayer, useDeleteLayer } from '@/api/hooks/layers';

function LayerForm() {
  const createLayer = useCreateLayer();
  const updateLayer = useUpdateLayer();
  const deleteLayer = useDeleteLayer();

  const handleCreate = async (data) => {
    try {
      await createLayer.mutateAsync(data);
      // Success handled automatically
    } catch (error) {
      // Error handled automatically
    }
  };

  return (
    <form onSubmit={handleCreate}>
      {/* form fields */}
      <button 
        type="submit" 
        disabled={createLayer.isPending}
      >
        {createLayer.isPending ? 'Creating...' : 'Create'}
      </button>
    </form>
  );
}
```

### Search/Find

```tsx
import { useLayerSearch } from '@/api/hooks/layers';

function SearchLayers() {
  const [query, setQuery] = useState('');
  const { data: results, isLoading } = useLayerSearch(
    { query },
    { enabled: query.length > 2 }
  );

  return (
    <div>
      <input 
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search layers..."
      />
      {isLoading && <div>Searching...</div>}
      {results?.map(result => (
        <div key={result.id}>
          {result.title} (Score: {result.score})
        </div>
      ))}
    </div>
  );
}
```

## API Structure

The API follows a hierarchical structure:
- **Layers**: Top-level organizational units
- **Domains**: Belong to layers, represent subject areas
- **Terms**: Belong to domains, represent specific concepts
- **Relationships**: Connect terms with semantic relationships

## Available Hooks

### Layers
- `useLayers(params?, options?)` - List all layers
- `useLayer(id, options?)` - Get a specific layer
- `useLayerSearch(params, options?)` - Search layers
- `useCreateLayer(options?)` - Create a new layer
- `useUpdateLayer(options?)` - Update a layer
- `useDeleteLayer(options?)` - Delete a layer

### Domains
- `useDomains(params?, options?)` - List all domains
- `useDomain(id, options?)` - Get a specific domain
- `useDomainsByLayer(layerId, options?)` - Get domains by layer
- `useDomainSearch(params, options?)` - Search domains
- `useCreateDomain(options?)` - Create a new domain
- `useUpdateDomain(options?)` - Update a domain
- `useDeleteDomain(options?)` - Delete a domain

### Terms
- `useTerms(params?, options?)` - List all terms
- `useTerm(id, options?)` - Get a specific term
- `useTermsByDomain(domainId, options?)` - Get terms by domain
- `useTermSearch(params, options?)` - Search terms
- `useCreateTerm(options?)` - Create a new term
- `useUpdateTerm(options?)` - Update a term
- `useDeleteTerm(options?)` - Delete a term

## Configuration

Configure the API client in your environment variables:

```env
EXPO_PUBLIC_API_URL=http://localhost:8000
```

## Error Handling

The client includes comprehensive error handling:

- **Network errors**: Automatic retry with exponential backoff
- **Validation errors**: Detailed field-level error messages
- **HTTP errors**: User-friendly error messages
- **Logging**: Structured error logging for debugging

## Development

### Regenerate Types

When the OpenAPI spec changes, regenerate types:

```bash
npm run generate-types
```

### Add New Endpoints

1. Update the service class
2. Add hooks in the hooks directory
3. Export from the main index file

## Best Practices

- Use the provided hooks instead of calling services directly
- Handle loading and error states in your components
- Use optimistic updates for better UX
- Implement proper error boundaries
- Use the search hooks for large datasets
- Cache invalidation is handled automatically
