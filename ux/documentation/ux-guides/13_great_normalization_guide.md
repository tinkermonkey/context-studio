# React Hooks Migration Guide: The Great Normalization

## Overview

This guide provides comprehensive instructions for updating React hooks and frontend code to accommodate the API changes from the Great Normalization (Phase 1 and Phase 2). The normalization consolidates `layers`, `domains`, and `terms` into a unified `structure_nodes` table, and updates the event system to use `change_events`.

## Key Changes Summary

### Phase 1: Structure Nodes Normalization
- **Unified Endpoint**: `/api/layers`, `/api/domains`, `/api/terms` → `/api/structure_nodes`
- **Unified Model**: Separate models → Single `StructureNode` model with `node_type` field
- **Unified Search**: Individual find endpoints → `/api/structure_nodes/find`
- **Relationships**: `term_relationships` → `structure_node_links`

### Phase 2: Event System Normalization
- **Event Model**: `NodeEvent` → `ChangeEvent`
- **Event Table**: `structure_node_events` → `change_events`
- **Field Changes**: `node_type` → `record_type`, `node_id` → `record_id`
- **New Support**: Added predicate change tracking

## 1. API Endpoint Changes

### 1.1 CRUD Operations

**Old Endpoints:**
```typescript
// Layers
POST   /api/layers
GET    /api/layers
GET    /api/layers/{id}
PUT    /api/layers/{id}
DELETE /api/layers/{id}

// Domains
POST   /api/domains
GET    /api/domains
GET    /api/domains/{id}
PUT    /api/domains/{id}
DELETE /api/domains/{id}

// Terms
POST   /api/terms
GET    /api/terms
GET    /api/terms/{id}
PUT    /api/terms/{id}
DELETE /api/terms/{id}
```

**New Unified Endpoint:**
```typescript
POST   /api/structure_nodes
GET    /api/structure_nodes
GET    /api/structure_nodes/{id}
PUT    /api/structure_nodes/{id}
DELETE /api/structure_nodes/{id}

// Filtering by type
GET    /api/structure_nodes?node_type=layer
GET    /api/structure_nodes?node_type=domain
GET    /api/structure_nodes?node_type=term
GET    /api/structure_nodes?parent_node_id={uuid}
```

### 1.2 Search Operations

**Old Endpoints:**
```typescript
POST /api/layers/find
POST /api/domains/find
POST /api/terms/find
```

**New Unified Endpoint:**
```typescript
POST /api/structure_nodes/find
// Use node_type in request body to filter
```

### 1.3 Relationship Operations

**Old Endpoints:**
```typescript
POST /api/terms/relationships
GET  /api/terms/relationships
```

**New Endpoints:**
```typescript
POST /api/structure_nodes/links
GET  /api/structure_nodes/links
```

## 2. Data Model Changes

### 2.1 Request/Response Schema

**Old Layer Model:**
```typescript
interface Layer {
  id: string;
  title: string;
  definition?: string;
  created_at: string;
  version: number;
  last_modified: string;
}
```

**Old Domain Model:**
```typescript
interface Domain {
  id: string;
  layer_id: string;
  title: string;
  definition?: string;
  primary_predicate_id?: string;
  created_at: string;
  version: number;
  last_modified: string;
}
```

**Old Term Model:**
```typescript
interface Term {
  id: string;
  domain_id: string;
  parent_term_id?: string;
  title: string;
  definition?: string;
  created_at: string;
  version: number;
  last_modified: string;
}
```

**New Unified StructureNode Model:**
```typescript
enum NodeType {
  LAYER = "layer",
  DOMAIN = "domain",
  TERM = "term"
}

interface StructureNode {
  id: string;
  node_type: NodeType;
  parent_node_id?: string;  // Replaces layer_id, domain_id, parent_term_id
  title: string;
  definition?: string;
  structural_predicate_id?: string;  // Replaces primary_predicate_id
  title_embedding?: number[];
  definition_embedding?: number[];
  created_at: string;
  version: number;
  last_modified: string;
}

interface StructureNodeCreate {
  node_type: NodeType;
  parent_node_id?: string;  // Required for domains and terms
  title: string;
  definition?: string;
  structural_predicate_id?: string;
}

interface StructureNodeUpdate {
  title?: string;
  definition?: string;
  parent_node_id?: string;
  structural_predicate_id?: string;
}
```

### 2.2 Relationship Schema

**Old Schema:**
```typescript
interface TermRelationship {
  id: string;
  source_term_id: string;
  target_term_id: string;
  predicate: string;
  predicate_id?: string;
  created_at: string;
}
```

**New Schema:**
```typescript
interface StructureNodeLink {
  id: string;
  source_node_id: string;  // Replaces source_term_id
  target_node_id: string;  // Replaces target_term_id
  predicate: string;
  predicate_id?: string;
  created_at: string;
}
```

### 2.3 Event Schema Changes

**Old Event Schema:**
```typescript
interface NodeEvent {
  id: number;
  event_type: "create" | "update" | "delete";
  node_type: string;  // "layer", "domain", "term", "structure_node_link"
  node_id?: string;
  old_data?: any;
  new_data?: any;
  timestamp: string;
  processed: boolean;
}
```

**New Event Schema:**
```typescript
enum RecordType {
  STRUCTURE_NODE = "structure_node",
  STRUCTURE_NODE_LINK = "structure_node_link",
  PREDICATE = "predicate"
}

interface ChangeEvent {
  id: number;
  event_type: "create" | "update" | "delete";
  record_type: RecordType;  // Replaces node_type
  record_id?: string;        // Replaces node_id
  old_data?: any;
  new_data?: any;
  timestamp: string;
  processed: boolean;
}
```

## 3. React Hook Migration Examples

### 3.1 useLayer Hook Migration

**Old Implementation:**
```typescript
// useLayer.ts
export const useLayer = () => {
  const createLayer = async (data: LayerCreate) => {
    const response = await fetch('/api/layers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  };

  const getLayers = async () => {
    const response = await fetch('/api/layers');
    return response.json();
  };

  const updateLayer = async (id: string, data: LayerUpdate) => {
    const response = await fetch(`/api/layers/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  };

  const deleteLayer = async (id: string) => {
    await fetch(`/api/layers/${id}`, { method: 'DELETE' });
  };

  const searchLayers = async (query: SearchQuery) => {
    const response = await fetch('/api/layers/find', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(query)
    });
    return response.json();
  };

  return { createLayer, getLayers, updateLayer, deleteLayer, searchLayers };
};
```

**New Implementation:**
```typescript
// useStructureNode.ts
export const useStructureNode = () => {
  const createNode = async (data: StructureNodeCreate) => {
    const response = await fetch('/api/structure_nodes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  };

  const getNodes = async (nodeType?: NodeType, parentNodeId?: string) => {
    const params = new URLSearchParams();
    if (nodeType) params.append('node_type', nodeType);
    if (parentNodeId) params.append('parent_node_id', parentNodeId);
    
    const response = await fetch(`/api/structure_nodes?${params}`);
    return response.json();
  };

  const updateNode = async (id: string, data: StructureNodeUpdate) => {
    const response = await fetch(`/api/structure_nodes/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  };

  const deleteNode = async (id: string) => {
    await fetch(`/api/structure_nodes/${id}`, { method: 'DELETE' });
  };

  const searchNodes = async (query: NodeSearchQuery) => {
    const response = await fetch('/api/structure_nodes/find', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(query)
    });
    return response.json();
  };

  // Convenience methods for specific node types
  const createLayer = (data: Omit<StructureNodeCreate, 'node_type'>) => 
    createNode({ ...data, node_type: NodeType.LAYER });
  
  const createDomain = (data: Omit<StructureNodeCreate, 'node_type'>) => 
    createNode({ ...data, node_type: NodeType.DOMAIN });
  
  const createTerm = (data: Omit<StructureNodeCreate, 'node_type'>) => 
    createNode({ ...data, node_type: NodeType.TERM });

  const getLayers = () => getNodes(NodeType.LAYER);
  const getDomains = (layerId?: string) => getNodes(NodeType.DOMAIN, layerId);
  const getTerms = (parentId?: string) => getNodes(NodeType.TERM, parentId);

  return {
    // Generic methods
    createNode,
    getNodes,
    updateNode,
    deleteNode,
    searchNodes,
    // Type-specific convenience methods
    createLayer,
    createDomain,
    createTerm,
    getLayers,
    getDomains,
    getTerms
  };
};
```

### 3.2 useDomain Hook Migration

**Old Implementation:**
```typescript
// useDomain.ts
export const useDomain = () => {
  const createDomain = async (data: DomainCreate) => {
    const response = await fetch('/api/domains', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  };

  const getDomainsByLayer = async (layerId: string) => {
    const response = await fetch(`/api/domains?layer_id=${layerId}`);
    return response.json();
  };

  // ... other methods
};
```

**New Implementation (using shared hook):**
```typescript
// useDomain.ts (wrapper around useStructureNode)
export const useDomain = () => {
  const { createNode, getNodes, updateNode, deleteNode, searchNodes } = useStructureNode();

  const createDomain = async (layerId: string, data: Omit<StructureNodeCreate, 'node_type' | 'parent_node_id'>) => {
    return createNode({
      ...data,
      node_type: NodeType.DOMAIN,
      parent_node_id: layerId  // layer_id becomes parent_node_id
    });
  };

  const getDomainsByLayer = async (layerId: string) => {
    return getNodes(NodeType.DOMAIN, layerId);
  };

  const updateDomain = async (id: string, data: StructureNodeUpdate) => {
    // If updating primary_predicate_id, map to structural_predicate_id
    const mappedData = {
      ...data,
      structural_predicate_id: data.structural_predicate_id
    };
    return updateNode(id, mappedData);
  };

  return { createDomain, getDomainsByLayer, updateDomain, deleteDomain: deleteNode };
};
```

### 3.3 useTerm Hook Migration

**Old Implementation:**
```typescript
// useTerm.ts
export const useTerm = () => {
  const createTerm = async (data: TermCreate) => {
    const response = await fetch('/api/terms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  };

  const getTermsByDomain = async (domainId: string) => {
    const response = await fetch(`/api/terms?domain_id=${domainId}`);
    return response.json();
  };

  const getTermsByParent = async (parentTermId: string) => {
    const response = await fetch(`/api/terms?parent_term_id=${parentTermId}`);
    return response.json();
  };

  // ... relationships methods
};
```

**New Implementation:**
```typescript
// useTerm.ts (wrapper around useStructureNode)
export const useTerm = () => {
  const { createNode, getNodes, updateNode, deleteNode, searchNodes } = useStructureNode();

  const createTerm = async (parentId: string, data: Omit<StructureNodeCreate, 'node_type' | 'parent_node_id'>) => {
    return createNode({
      ...data,
      node_type: NodeType.TERM,
      parent_node_id: parentId  // Can be either domain_id or parent_term_id
    });
  };

  const getTermsByParent = async (parentId: string) => {
    // parentId can be either a domain or another term
    return getNodes(NodeType.TERM, parentId);
  };

  // For backward compatibility, if you need to get all terms in a domain hierarchy
  const getTermsByDomain = async (domainId: string) => {
    // This might require recursive fetching or a specialized endpoint
    // depending on your implementation needs
    const directTerms = await getNodes(NodeType.TERM, domainId);
    // Additional logic to fetch nested terms if needed
    return directTerms;
  };

  return { createTerm, getTermsByParent, getTermsByDomain, updateTerm: updateNode, deleteTerm: deleteNode };
};
```

### 3.4 useTermRelationships Migration

**Old Implementation:**
```typescript
// useTermRelationships.ts
export const useTermRelationships = () => {
  const createRelationship = async (data: TermRelationshipCreate) => {
    const response = await fetch('/api/terms/relationships', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  };

  const getRelationships = async (termId: string) => {
    const response = await fetch(`/api/terms/relationships?source_term_id=${termId}`);
    return response.json();
  };
};
```

**New Implementation:**
```typescript
// useNodeLinks.ts
export const useNodeLinks = () => {
  const createLink = async (data: StructureNodeLinkCreate) => {
    const response = await fetch('/api/structure_nodes/links', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  };

  const getLinks = async (nodeId: string, direction: 'source' | 'target' = 'source') => {
    const param = direction === 'source' ? 'source_node_id' : 'target_node_id';
    const response = await fetch(`/api/structure_nodes/links?${param}=${nodeId}`);
    return response.json();
  };

  const deleteLink = async (linkId: string) => {
    await fetch(`/api/structure_nodes/links/${linkId}`, { method: 'DELETE' });
  };

  // Backward compatibility wrapper
  const createTermRelationship = (sourceTermId: string, targetTermId: string, predicate: string, predicateId?: string) => {
    return createLink({
      source_node_id: sourceTermId,
      target_node_id: targetTermId,
      predicate,
      predicate_id: predicateId
    });
  };

  return { createLink, getLinks, deleteLink, createTermRelationship };
};
```

## 4. Event Handling Updates

### 4.1 WebSocket Event Listeners

**Old Implementation:**
```typescript
// eventListener.ts
socket.on('node_event', (event: NodeEvent) => {
  switch (event.node_type) {
    case 'layer':
      handleLayerEvent(event);
      break;
    case 'domain':
      handleDomainEvent(event);
      break;
    case 'term':
      handleTermEvent(event);
      break;
  }
});
```

**New Implementation:**
```typescript
// eventListener.ts
socket.on('change_event', (event: ChangeEvent) => {
  switch (event.record_type) {
    case RecordType.STRUCTURE_NODE:
      // Need to check the actual node_type from event data
      const nodeType = event.new_data?.node_type || event.old_data?.node_type;
      handleStructureNodeEvent(event, nodeType);
      break;
    case RecordType.STRUCTURE_NODE_LINK:
      handleNodeLinkEvent(event);
      break;
    case RecordType.PREDICATE:
      handlePredicateEvent(event);
      break;
  }
});

function handleStructureNodeEvent(event: ChangeEvent, nodeType: string) {
  // Route to specific handlers based on node_type
  switch (nodeType) {
    case 'layer':
      handleLayerChange(event);
      break;
    case 'domain':
      handleDomainChange(event);
      break;
    case 'term':
      handleTermChange(event);
      break;
  }
}
```

## 5. State Management Updates

### 5.1 Redux/Zustand Store Updates

**Old Store Structure:**
```typescript
interface AppState {
  layers: Layer[];
  domains: Domain[];
  terms: Term[];
  termRelationships: TermRelationship[];
}
```

**New Store Structure:**
```typescript
interface AppState {
  structureNodes: {
    byId: Record<string, StructureNode>;
    allIds: string[];
    byType: {
      layer: string[];
      domain: string[];
      term: string[];
    };
  };
  nodeLinks: StructureNodeLink[];
}

// Helper selectors
const selectLayers = (state: AppState) => 
  state.structureNodes.byType.layer.map(id => state.structureNodes.byId[id]);

const selectDomains = (state: AppState) => 
  state.structureNodes.byType.domain.map(id => state.structureNodes.byId[id]);

const selectTerms = (state: AppState) => 
  state.structureNodes.byType.term.map(id => state.structureNodes.byId[id]);

const selectNodesByParent = (state: AppState, parentId: string) =>
  state.structureNodes.allIds
    .map(id => state.structureNodes.byId[id])
    .filter(node => node.parent_node_id === parentId);
```

## 6. Query and Filter Updates

### 6.1 Search Query Updates

**Old Search Query:**
```typescript
interface LayerSearchQuery {
  title?: string;
  definition?: string;
  created_at?: string;
  minimum_score?: number;
  limit?: number;
}
```

**New Search Query:**
```typescript
interface NodeSearchRequest {
  title?: string;
  definition?: string;
  node_type?: NodeType;  // Optional filter by type
  parent_node_id?: string;  // Optional filter by parent
  created_at?: string;
  minimum_score?: number;
  limit?: number;
}

// Example: Search for all domains in a specific layer
const searchDomainsInLayer = async (layerId: string, searchTerm: string) => {
  const query: NodeSearchRequest = {
    title: searchTerm,
    node_type: NodeType.DOMAIN,
    parent_node_id: layerId,
    minimum_score: 0.7
  };
  return await searchNodes(query);
};
```

## 7. Common Migration Patterns

### 7.1 Field Mapping Reference

| Old Field | New Field | Notes |
|-----------|-----------|-------|
| `layer_id` (in domains) | `parent_node_id` | For domains, parent is always a layer |
| `domain_id` (in terms) | `parent_node_id` | For root terms in a domain |
| `parent_term_id` (in terms) | `parent_node_id` | For nested terms |
| `primary_predicate_id` | `structural_predicate_id` | Renamed field |
| `source_term_id` | `source_node_id` | In relationships/links |
| `target_term_id` | `target_node_id` | In relationships/links |
| `node_type` (events) | `record_type` | In event system |
| `node_id` (events) | `record_id` | In event system |

### 7.2 Type Guards and Utilities

```typescript
// Type guards for working with unified nodes
function isLayer(node: StructureNode): boolean {
  return node.node_type === NodeType.LAYER;
}

function isDomain(node: StructureNode): boolean {
  return node.node_type === NodeType.DOMAIN;
}

function isTerm(node: StructureNode): boolean {
  return node.node_type === NodeType.TERM;
}

// Utility to get parent type
function getParentType(node: StructureNode): NodeType | null {
  if (!node.parent_node_id) return null;
  
  switch (node.node_type) {
    case NodeType.DOMAIN:
      return NodeType.LAYER;
    case NodeType.TERM:
      // Could be domain or another term - need to fetch parent
      return null; // Requires API call to determine
    default:
      return null;
  }
}

// Utility to build hierarchy path
async function getNodePath(nodeId: string): Promise<StructureNode[]> {
  const path: StructureNode[] = [];
  let currentId = nodeId;
  
  while (currentId) {
    const node = await fetchNode(currentId);
    path.unshift(node);
    currentId = node.parent_node_id;
  }
  
  return path;
}
```

### 7.3 Error Handling Updates

```typescript
// Updated error handling for validation rules
async function createStructureNode(data: StructureNodeCreate) {
  try {
    const response = await fetch('/api/structure_nodes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      const error = await response.json();
      
      // Handle specific validation errors
      switch (error.detail) {
        case 'Layers cannot have parent structure_nodes':
          throw new Error('Layers must be root nodes');
        case 'Domains must have a parent layer':
          throw new Error('Please select a parent layer for this domain');
        case 'Terms must have a parent domain':
          throw new Error('Please select a parent domain or term');
        case 'Domain parent must be a layer':
          throw new Error('Domains can only be children of layers');
        case 'Term parent must be a domain or term':
          throw new Error('Terms can only be children of domains or other terms');
        case 'Operation would create circular reference':
          throw new Error('This change would create a circular reference');
        default:
          throw new Error(error.detail || 'Failed to create node');
      }
    }
    
    return response.json();
  } catch (error) {
    console.error('Error creating structure node:', error);
    throw error;
  }
}
```

## 8. Testing Updates

### 8.1 Update Test Fixtures

```typescript
// testFixtures.ts
export const mockStructureNode: StructureNode = {
  id: 'test-id',
  node_type: NodeType.TERM,
  parent_node_id: 'domain-id',
  title: 'Test Term',
  definition: 'Test definition',
  structural_predicate_id: null,
  created_at: '2024-01-01T00:00:00Z',
  version: 1,
  last_modified: '2024-01-01T00:00:00Z'
};

export const mockLayer: StructureNode = {
  ...mockStructureNode,
  node_type: NodeType.LAYER,
  parent_node_id: undefined
};

export const mockDomain: StructureNode = {
  ...mockStructureNode,
  node_type: NodeType.DOMAIN,
  parent_node_id: 'layer-id'
};
```

### 8.2 Update API Mocks

```typescript
// apiMocks.ts
import { rest } from 'msw';

export const handlers = [
  // Old endpoints (remove these)
  // rest.get('/api/layers', ...),
  // rest.get('/api/domains', ...),
  // rest.get('/api/terms', ...),
  
  // New unified endpoints
  rest.get('/api/structure_nodes', (req, res, ctx) => {
    const nodeType = req.url.searchParams.get('node_type');
    const parentNodeId = req.url.searchParams.get('parent_node_id');
    
    let nodes = mockNodes;
    if (nodeType) {
      nodes = nodes.filter(n => n.node_type === nodeType);
    }
    if (parentNodeId) {
      nodes = nodes.filter(n => n.parent_node_id === parentNodeId);
    }
    
    return res(ctx.json({ data: nodes, total: nodes.length }));
  }),
  
  rest.post('/api/structure_nodes', async (req, res, ctx) => {
    const data = await req.json();
    const newNode = {
      id: generateId(),
      ...data,
      created_at: new Date().toISOString(),
      version: 1,
      last_modified: new Date().toISOString()
    };
    return res(ctx.json(newNode));
  })
];
```

## 9. Migration Checklist

### Phase 1: Preparation
- [ ] Review and understand the unified data model
- [ ] Identify all hooks and components using old endpoints
- [ ] Create mapping of old fields to new fields
- [ ] Set up feature flags for gradual migration

### Phase 2: Core Hook Updates
- [ ] Create new `useStructureNode` hook
- [ ] Create new `useNodeLinks` hook
- [ ] Update type definitions and interfaces
- [ ] Implement backward-compatible wrappers

### Phase 3: Component Updates
- [ ] Update components to use new hooks
- [ ] Update forms to use new field names
- [ ] Update validation logic for new rules
- [ ] Update error handling for new error messages

### Phase 4: State Management
- [ ] Update store structure for unified nodes
- [ ] Create selectors for type-specific queries
- [ ] Update reducers/actions for new data model
- [ ] Migrate existing state data

### Phase 5: Event System
- [ ] Update WebSocket listeners for `change_events`
- [ ] Update event handlers for new schema
- [ ] Add support for predicate events
- [ ] Test real-time updates

### Phase 6: Testing and Validation
- [ ] Update all test fixtures
- [ ] Update API mocks
- [ ] Run regression tests
- [ ] Test backward compatibility wrappers
- [ ] Performance testing with new endpoints

### Phase 7: Cleanup
- [ ] Remove old hooks and components
- [ ] Remove backward compatibility wrappers
- [ ] Update documentation
- [ ] Remove old type definitions

## 10. Troubleshooting Guide

### Common Issues and Solutions

**Issue: Parent node validation errors**
- Solution: Ensure correct parent-child relationships:
  - Layers: No parent
  - Domains: Parent must be a layer
  - Terms: Parent must be a domain or another term

**Issue: Circular reference errors**
- Solution: Validate hierarchy before updates
- Use the `getNodePath` utility to check for cycles

**Issue: Missing node_type in responses**
- Solution: Always include `node_type` when creating nodes
- Check that backend is returning the field

**Issue: Event handling for mixed node types**
- Solution: Check `node_type` within event data
- Route to appropriate handlers based on type

**Issue: Performance with large hierarchies**
- Solution: Implement pagination for large result sets
- Use virtualization for long lists
- Consider caching frequently accessed nodes

## 11. Performance Optimization Tips

1. **Batch Operations**: When fetching multiple node types, use parallel requests
2. **Caching**: Cache node hierarchies that don't change frequently
3. **Lazy Loading**: Load child nodes only when expanded
4. **Debouncing**: Debounce search operations
5. **Memoization**: Memoize computed hierarchies and paths

## 12. Additional Resources

- API Documentation: `/documentation/api.md`
- Data Model Documentation: `/documentation/data_model.md`
- Migration Scripts: `/database/migrations/006_nodes.py`
- Design Documents: `/documentation/requirements/13.*.md`

## Support

For questions or issues during migration:
1. Check this guide for common patterns
2. Review the troubleshooting section
3. Consult the API documentation
4. Contact the backend team for clarification on specific behaviors