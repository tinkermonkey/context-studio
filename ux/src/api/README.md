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

### Graph Operations

```tsx
import { 
  useGraphStats, 
  useTermSearch, 
  useRelatedTerms, 
  useSparqlQuery,
  useGraphRefresh 
} from '@/api/hooks/graph';

function GraphAnalytics() {
  const { data: stats } = useGraphStats();
  const { data: terms } = useTermSearch({ title: 'concept', exact: false });
  const { data: related } = useRelatedTerms('term-id-123', { max_depth: 2 });
  
  const sparqlQuery = useSparqlQuery();
  const refreshGraph = useGraphRefresh();

  const handleSparqlQuery = async () => {
    try {
      const results = await sparqlQuery.mutateAsync({
        query: `
          SELECT ?term ?title WHERE {
            ?term a :Term .
            ?term :title ?title .
          } LIMIT 10
        `
      });
      console.log('SPARQL Results:', results);
    } catch (error) {
      console.error('SPARQL Error:', error);
    }
  };

  const handleRefresh = async () => {
    try {
      await refreshGraph.mutateAsync();
      console.log('Graph refreshed successfully');
    } catch (error) {
      console.error('Refresh failed:', error);
    }
  };

  return (
    <div>
      <h2>Graph Statistics</h2>
      <pre>{JSON.stringify(stats, null, 2)}</pre>
      
      <h2>Term Search Results</h2>
      {terms?.map((term, index) => (
        <div key={index}>{JSON.stringify(term)}</div>
      ))}
      
      <h2>Related Terms</h2>
      <pre>{JSON.stringify(related, null, 2)}</pre>
      
      <button onClick={handleSparqlQuery} disabled={sparqlQuery.isPending}>
        {sparqlQuery.isPending ? 'Executing...' : 'Execute SPARQL Query'}
      </button>
      
      <button onClick={handleRefresh} disabled={refreshGraph.isPending}>
        {refreshGraph.isPending ? 'Refreshing...' : 'Refresh Graph'}
      </button>
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
- **Graph**: Provides advanced analytics, SPARQL queries, and graph operations across all entities

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

### Graph Analytics & Operations
- `useGraphStats(options?)` - Get comprehensive graph statistics
- `useTermSearch(params, options?)` - Search terms using SPARQL
- `useTermInfo(termId, options?)` - Get detailed term information
- `useRelatedTerms(termId, params?, options?)` - Find related terms
- `useTermHierarchy(termId, options?)` - Get term hierarchy
- `useDomainAnalysis(domainId, options?)` - Analyze domain structure
- `useDomainInfo(domainId, options?)` - Get domain information
- `useDomainHierarchy(params?, options?)` - Get domain hierarchy
- `useLayerAnalytics(params?, options?)` - Get layer analytics
- `useLayerInfo(layerId, options?)` - Get layer information
- `useCommunityDetection(params?, options?)` - Detect graph communities
- `useSparqlExamples(options?)` - Get example SPARQL queries
- `useRdfExport(params?, options?)` - Export RDF data
- `useGraphExport(params?, options?)` - Export graph data

### Graph Mutations
- `useGraphRefresh(options?)` - Refresh graph from database
- `useSparqlQuery(options?)` - Execute SPARQL queries
- `useSearchAndAnalyze(options?)` - Search and analyze terms
- `useCentralityCalculation(options?)` - Calculate node centrality
- `useShortestPath(options?)` - Find shortest path between nodes
- `useNeighborsQuery(options?)` - Get node neighbors

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
