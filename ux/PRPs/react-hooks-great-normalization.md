name: "React Hooks Migration: Great Normalization - Structure Nodes & Events"
description: |
  Complete migration of React hooks from separate layer/domain/term APIs to unified structure_nodes API,
  and from NodeEvent to ChangeEvent system. Includes comprehensive testing and validation loops.

---

## Goal
Migrate all React hooks, services, and components from using separate `/api/layers`, `/api/domains`, `/api/terms` endpoints to a unified `/api/structure_nodes` endpoint, and update event handling from `NodeEvent` to `ChangeEvent` system. Create backward-compatible wrappers during transition, then clean up legacy code.

## Why
- **API Simplification**: Consolidates 3 separate APIs into 1 unified endpoint with consistent patterns
- **Improved Type Safety**: Single `StructureNode` model with `node_type` discrimination reduces type complexity  
- **Enhanced Event System**: New `ChangeEvent` model supports predicate tracking and clearer record types
- **Better Performance**: Unified queries reduce redundant API calls and enable better caching strategies
- **Maintainability**: Single codebase path for CRUD operations instead of maintaining 3 separate patterns

## What
Replace existing layer/domain/term hooks with unified structure_nodes hooks while maintaining identical UI behavior. Update event system to use new change_events model. Provide smooth migration path with backward compatibility.

### Success Criteria
- [ ] All existing components work without modification during transition
- [ ] New unified hooks provide same functionality as current separate hooks
- [ ] Event system handles both NodeEvent and ChangeEvent during migration
- [ ] All tests pass with new hook implementations
- [ ] Performance is equal or better than current implementation
- [ ] Zero breaking changes for existing UI components

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window
- file: documentation/ux-guides/13_great_normalization_guide.md
  why: Complete migration specification with examples and patterns to follow
  
- file: src/api/hooks/layers/useLayers.ts
  why: Current pattern for query hooks - use as template for structure nodes
  
- file: src/api/hooks/layers/useLayerMutations.ts  
  why: Current pattern for mutation hooks - cache invalidation patterns
  
- file: src/api/hooks/predicates/relationships/useRelationships.ts
  why: Current relationship handling pattern to adapt for structure_node_links
  
- file: src/api/services/layers.ts
  why: Current service class pattern extending BaseService
  
- file: src/api/services/base.ts
  why: BaseService methods and pagination patterns to follow
  
- file: src/api/config.ts
  why: Current ENDPOINTS and QUERY_KEYS structure to extend
  
- url: https://tanstack.com/query/v5/docs/react/guides/queries
  section: "Custom Query Hooks"
  critical: TanStack Query v5 uses single object signature, not multiple overloads
  
- url: https://romanslonov.com/blog/tanstack-query-reusable-custom-hooks
  why: v5 patterns for reusable hooks with proper TypeScript typing
  
- file: test/integration/hooks.useDomains.integration.test.tsx
  why: Integration testing pattern to follow for new hooks
  
- file: test/utils/renderWithProviders.tsx
  why: Test utility setup for TanStack Query testing
```

### Current Codebase Tree (relevant sections)
```bash
src/
├── api/
│   ├── hooks/
│   │   ├── layers/           # MIGRATE: useLayers, useLayerMutations
│   │   ├── domains/          # MIGRATE: useDomains, useDomainMutations  
│   │   ├── terms/            # MIGRATE: useTerms, useTermMutations
│   │   └── predicates/relationships/  # MIGRATE: useRelationships
│   ├── services/
│   │   ├── base.ts           # EXTEND: BaseService patterns
│   │   ├── layers.ts         # REPLACE: with structureNodes.ts
│   │   ├── domains.ts        # REPLACE: with structureNodes.ts
│   │   └── terms.ts          # REPLACE: with structureNodes.ts
│   ├── client/types.ts       # UPDATE: with new OpenAPI types
│   └── config.ts             # UPDATE: endpoints and query keys
test/
└── integration/              # UPDATE: existing integration tests
```

### Desired Codebase Tree (new structure)
```bash
src/
├── api/
│   ├── hooks/
│   │   ├── structure_nodes/
│   │   │   ├── useStructureNodes.ts      # MAIN unified hook
│   │   │   ├── useStructureNodeMutations.ts
│   │   │   └── index.ts
│   │   ├── node_links/
│   │   │   ├── useNodeLinks.ts           # Replaces relationships
│   │   │   ├── useNodeLinkMutations.ts
│   │   │   └── index.ts
│   │   ├── legacy/                       # TEMPORARY backward compatibility
│   │   │   ├── useLayers.ts             # Wrapper around useStructureNodes
│   │   │   ├── useDomains.ts
│   │   │   └── useTerms.ts
│   │   └── events/
│   │       ├── useChangeEvents.ts        # New event system
│   │       └── index.ts
│   ├── services/
│   │   ├── structureNodes.ts             # NEW unified service
│   │   ├── nodeLinks.ts                  # NEW links service
│   │   └── changeEvents.ts               # NEW events service
│   └── types/
│       └── structureNodes.ts             # Type definitions and enums
```

### Known Gotchas & Library Quirks
```typescript
// CRITICAL: TanStack Query v5 single object signature
// OLD v4 pattern (DON'T USE):
useQuery(['key'], fetchFn, { options })

// NEW v5 pattern (USE THIS):
useQuery({ 
  queryKey: ['key'], 
  queryFn: fetchFn,
  ...options 
})

// CRITICAL: TypeScript custom hook typing for TanStack Query v5
// Use proper Omit pattern for reusable hooks:
function useStructureNodes(
  params?: StructureNodeListParams,
  options?: Omit<UseQueryOptions<StructureNode[], Error>, 'queryKey' | 'queryFn'>
) {
  // Implementation
}

// CRITICAL: BaseService pagination patterns
// Always use getAllPaginated for hooks that load "all" data
// Use getPage for controlled pagination
// Use getPaginatedResponse when you need metadata

// CRITICAL: Query key patterns
// Follow existing pattern: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, id, params)
// Ensure proper cache invalidation in mutations

// CRITICAL: Event handling migration
// During transition, support both NodeEvent AND ChangeEvent
// Check event.record_type vs event.node_type for routing

// CRITICAL: Node type validation
// Layers: parent_node_id must be null/undefined
// Domains: parent_node_id must reference a layer
// Terms: parent_node_id must reference domain or another term
```

## Implementation Blueprint

### Data Models and Structure
The unified data model centralizes all structure entities with type discrimination:

```typescript
// Core enums and types
enum NodeType {
  LAYER = "layer",
  DOMAIN = "domain", 
  TERM = "term"
}

enum RecordType {
  STRUCTURE_NODE = "structure_node",
  STRUCTURE_NODE_LINK = "structure_node_link",
  PREDICATE = "predicate"
}

// Main unified model
interface StructureNode {
  id: string;
  node_type: NodeType;
  parent_node_id?: string;        // Replaces layer_id, domain_id, parent_term_id
  title: string;
  definition?: string;
  structural_predicate_id?: string; // Replaces primary_predicate_id
  title_embedding?: number[];
  definition_embedding?: number[];
  created_at: string;
  version: number;
  last_modified: string;
}

// New event model
interface ChangeEvent {
  id: number;
  event_type: "create" | "update" | "delete";
  record_type: RecordType;        // Replaces node_type
  record_id?: string;             // Replaces node_id
  old_data?: any;
  new_data?: any;
  timestamp: string;
  processed: boolean;
}

// Links model
interface StructureNodeLink {
  id: string;
  source_node_id: string;         // Replaces source_term_id
  target_node_id: string;         // Replaces target_term_id
  predicate: string;
  predicate_id?: string;
  created_at: string;
}
```

### List of Tasks to Complete (in order)

```yaml
Task 1 - Update Configuration:
MODIFY src/api/config.ts:
  - ADD QUERY_KEYS.STRUCTURE_NODES: 'structure_nodes'
  - ADD QUERY_KEYS.NODE_LINKS: 'node_links' 
  - ADD QUERY_KEYS.CHANGE_EVENTS: 'change_events'
  - ADD ENDPOINTS.STRUCTURE_NODES: '/api/structure_nodes'
  - ADD ENDPOINTS.NODE_LINKS: '/api/structure_nodes/links'
  - ADD ENDPOINTS.CHANGE_EVENTS: '/api/change_events'

Task 2 - Create Type Definitions:
CREATE src/api/types/structureNodes.ts:
  - DEFINE NodeType enum
  - DEFINE RecordType enum  
  - DEFINE StructureNode interface
  - DEFINE StructureNodeCreate interface
  - DEFINE StructureNodeUpdate interface
  - DEFINE ChangeEvent interface
  - DEFINE StructureNodeLink interface
  - EXPORT type guards (isLayer, isDomain, isTerm)

Task 3 - Create Unified Service:
CREATE src/api/services/structureNodes.ts:
  - EXTEND BaseService class
  - IMPLEMENT list(params) with node_type filtering
  - IMPLEMENT listPage, listPageWithMetadata
  - IMPLEMENT get(id), create(data), update(id, data), delete(id)
  - IMPLEMENT find(params) for search
  - MIRROR existing pagination and error handling patterns from LayerService

Task 4 - Create Node Links Service:
CREATE src/api/services/nodeLinks.ts:
  - EXTEND BaseService class  
  - IMPLEMENT list, get, create, delete for links
  - REPLACE term-relationship endpoints with node-link endpoints
  - PRESERVE existing relationship query patterns

Task 5 - Create Main Structure Nodes Hook:
CREATE src/api/hooks/structure_nodes/useStructureNodes.ts:
  - IMPLEMENT useStructureNodes (loads all nodes with optional filtering)
  - IMPLEMENT useStructureNodesPage (single page)
  - IMPLEMENT useStructureNodesByType (filter by node_type)
  - IMPLEMENT useStructureNodesByParent (filter by parent_node_id)
  - IMPLEMENT useStructureNode (single node by id)
  - IMPLEMENT useStructureNodeSearch (semantic search)
  - USE TanStack Query v5 single object signature throughout
  - FOLLOW TypeScript patterns from existing hooks

Task 6 - Create Structure Node Mutations Hook:
CREATE src/api/hooks/structure_nodes/useStructureNodeMutations.ts:
  - IMPLEMENT useCreateStructureNode with proper cache updates
  - IMPLEMENT useUpdateStructureNode with optimistic updates
  - IMPLEMENT useDeleteStructureNode with cascade invalidation
  - MIRROR cache invalidation patterns from existing mutation hooks
  - ENSURE proper error handling for validation rules

Task 7 - Create Node Links Hooks:
CREATE src/api/hooks/node_links/useNodeLinks.ts:
CREATE src/api/hooks/node_links/useNodeLinkMutations.ts:
  - REPLACE relationship hooks with link hooks
  - IMPLEMENT useNodeLinks, useNodeLinksByNode, useNodeLink
  - IMPLEMENT useCreateNodeLink, useDeleteNodeLink
  - PRESERVE existing relationship query patterns

Task 8 - Create Convenience Wrapper Hooks:
CREATE src/api/hooks/structure_nodes/convenience.ts:
  - IMPLEMENT useLayers() -> useStructureNodesByType(NodeType.LAYER)
  - IMPLEMENT useDomains(layerId?) -> useStructureNodesByParent(layerId, NodeType.DOMAIN)  
  - IMPLEMENT useTerms(parentId?) -> useStructureNodesByParent(parentId, NodeType.TERM)
  - IMPLEMENT createLayer, createDomain, createTerm convenience functions
  - PROVIDE same interface as existing separate hooks

Task 9 - Create Legacy Compatibility Wrappers:
CREATE src/api/hooks/legacy/useLayers.ts:
CREATE src/api/hooks/legacy/useDomains.ts:  
CREATE src/api/hooks/legacy/useTerms.ts:
  - WRAP convenience hooks to maintain exact same API
  - ENSURE zero breaking changes for existing components
  - ADD deprecation comments for future cleanup

Task 10 - Update Event System:
CREATE src/api/hooks/events/useChangeEvents.ts:
  - IMPLEMENT useChangeEvents hook for new event model
  - HANDLE both NodeEvent and ChangeEvent during migration
  - PROVIDE event type discrimination and routing

Task 11 - Create Integration Tests:
CREATE test/integration/hooks.useStructureNodes.integration.test.tsx:
  - TEST unified hooks with real API calls
  - TEST filtering by node_type and parent_node_id
  - TEST backward compatibility wrappers
  - MIRROR existing integration test patterns

Task 12 - Create Unit Tests:  
CREATE test/unit/hooks/structure_nodes/:
  - TEST all new hooks with MSW mocking
  - TEST error handling and edge cases
  - TEST TypeScript type inference
  - ACHIEVE same coverage as existing hook tests

Task 13 - Update Component Integration:
MODIFY key components to import from new hook locations:
  - UPDATE import statements gradually
  - TEST each component after hook replacement
  - ENSURE UI behavior remains identical

Task 14 - Performance Validation:
  - RUN existing integration tests
  - MEASURE API call patterns and caching effectiveness  
  - ENSURE performance equal or better than current
  - VALIDATE reduced redundant calls

Task 15 - Legacy Cleanup:
REMOVE after full migration validated:
  - DELETE src/api/hooks/layers/, domains/, terms/
  - DELETE src/api/services/layers.ts, domains.ts, terms.ts
  - DELETE src/api/hooks/legacy/ wrappers
  - UPDATE imports to use unified hooks directly
```

### Per Task Pseudocode

```typescript
// Task 3: Unified Service Pattern
export class StructureNodeService extends BaseService {
  async list(params?: StructureNodeListParams): Promise<StructureNode[]> {
    // PATTERN: Build URL with query params like existing services
    const url = ENDPOINTS.STRUCTURE_NODES + '/';
    const queryParams = new URLSearchParams();
    
    if (params?.node_type) queryParams.append('node_type', params.node_type);
    if (params?.parent_node_id) queryParams.append('parent_node_id', params.parent_node_id);
    
    // CRITICAL: Use BaseService pagination methods
    if (params?.limit !== undefined) {
      return this.getPage<StructureNode>(url + '?' + queryParams, params);
    }
    return this.getAllPaginated<StructureNode>(url + '?' + queryParams, params);
  }

  // PATTERN: Mirror exact same method signatures as LayerService
  async get(id: string): Promise<StructureNode> {
    return this.getResource<StructureNode>(`${ENDPOINTS.STRUCTURE_NODES}/${id}`);
  }
}

// Task 5: Main Query Hook Pattern  
export const useStructureNodes = (
  params?: StructureNodeListParams,
  options?: Omit<UseQueryOptions<StructureNode[], Error>, 'queryKey' | 'queryFn'>
) => {
  return useQuery({
    queryKey: createQueryKey(QUERY_KEYS.STRUCTURE_NODES, undefined, params),
    queryFn: () => structureNodeService.list(params),
    ...options,
  });
};

// PATTERN: Type-specific convenience hooks
export const useLayerNodes = (options?: UseQueryOptions<StructureNode[], Error>) => {
  return useStructureNodes({ node_type: NodeType.LAYER }, options);
};

export const useDomainNodes = (layerId?: string, options?: UseQueryOptions<StructureNode[], Error>) => {
  return useStructureNodes({ 
    node_type: NodeType.DOMAIN, 
    parent_node_id: layerId 
  }, options);
};

// Task 6: Mutation Hook Pattern
export const useCreateStructureNode = (
  options?: UseMutationOptions<StructureNode, Error, StructureNodeCreate>
) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: StructureNodeCreate) => structureNodeService.create(data),
    onSuccess: (data) => {
      // PATTERN: Invalidate related queries based on node_type
      queryClient.invalidateQueries({
        queryKey: [QUERY_KEYS.STRUCTURE_NODES],
      });
      
      // PATTERN: Update specific node cache
      queryClient.setQueryData(
        createQueryKey(QUERY_KEYS.STRUCTURE_NODES, data.id),
        data
      );
    },
    ...options,
  });
};

// Task 9: Legacy Compatibility Pattern
export const useLayers = (
  params?: LayerListParams,
  options?: UseQueryOptions<LayerOut[], Error>
) => {
  // PATTERN: Map old interface to new hook
  const structureParams: StructureNodeListParams = {
    node_type: NodeType.LAYER,
    ...params
  };
  
  const result = useStructureNodes(structureParams, options);
  
  // CRITICAL: Return data in expected format for backward compatibility
  return {
    ...result,
    data: result.data as LayerOut[], // Type assertion for compatibility
  };
};
```

### Integration Points
```yaml
ENDPOINTS:
  - update: src/api/config.ts ENDPOINTS object
  - add: STRUCTURE_NODES, NODE_LINKS, CHANGE_EVENTS

QUERY_KEYS:
  - update: src/api/config.ts QUERY_KEYS object  
  - maintain: existing keys during transition
  - add: STRUCTURE_NODES, NODE_LINKS, CHANGE_EVENTS

TYPES:
  - generate: new OpenAPI types with `npm run generate-types`
  - import: from updated client/types.ts
  - create: local type definitions for complex interfaces

CACHING:
  - pattern: use createQueryKey utility consistently
  - invalidate: related queries on mutations (nodes -> links, parent -> children)
  - optimize: reduce redundant API calls through unified queries
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Run these FIRST - fix any errors before proceeding
npm run typecheck                    # TypeScript compilation
npm run format:check                 # Prettier formatting
# Expected: No errors. If errors, READ the error and fix.
```

### Level 2: Unit Tests
```typescript  
// CREATE test/unit/hooks/structure_nodes/useStructureNodes.test.tsx
// PATTERN: Follow existing hook testing patterns
import { renderHook, waitFor } from '@testing-library/react';
import { useStructureNodes } from '@/api/hooks/structure_nodes/useStructureNodes';
import { renderWithProviders } from '@/test/utils/renderWithProviders';

describe('useStructureNodes', () => {
  it('fetches all structure nodes', async () => {
    const { result } = renderHook(() => useStructureNodes(), {
      wrapper: ({ children }) => renderWithProviders(children as any),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
      expect(result.current.data).toBeDefined();
    });
  });

  it('filters by node type', async () => {
    const { result } = renderHook(
      () => useStructureNodes({ node_type: NodeType.LAYER }), 
      { wrapper: ({ children }) => renderWithProviders(children as any) }
    );

    await waitFor(() => {
      expect(result.current.data?.every(node => node.node_type === 'layer')).toBe(true);
    });
  });
});
```

```bash
# Run and iterate until passing:
npm test -- --run test/unit/hooks/structure_nodes
# If failing: Read error, understand root cause, fix code, re-run
```

### Level 3: Integration Tests
```bash
# Test with actual API endpoints
npm run dev                          # Start development server in background

# Test the unified endpoints directly
curl -X GET "http://localhost:8000/api/structure_nodes?node_type=layer"
# Expected: Array of layer nodes

curl -X POST "http://localhost:8000/api/structure_nodes" \
  -H "Content-Type: application/json" \
  -d '{"node_type": "layer", "title": "Test Layer"}'
# Expected: Created layer object

# Run integration tests
npm test -- --run test/integration
# Expected: All tests pass with new hooks
```

### Level 4: Component Integration
```bash
# Test with actual UI components
# Pick a component that uses layers/domains/terms hooks
# Temporarily update it to use new hooks and verify UI works identically

# Example: Update a table component
# BEFORE: import { useLayers } from '@/api/hooks/layers';
# AFTER: import { useLayers } from '@/api/hooks/legacy/useLayers';
# VERIFY: Table displays exact same data and behavior
```

## Final Validation Checklist
- [ ] All tests pass: `npm test --run`
- [ ] No TypeScript errors: `npm run typecheck`  
- [ ] No formatting issues: `npm run format:check`
- [ ] Integration tests pass with real API: `npm test -- --run test/integration`
- [ ] Legacy wrapper hooks work identically: Manual component testing
- [ ] Performance is equal/better: Compare network tabs before/after
- [ ] Event system handles both old and new events: Test real-time updates
- [ ] Documentation updated: Update relevant docs

---

## Anti-Patterns to Avoid
- ❌ Don't change existing component interfaces during migration
- ❌ Don't skip backward compatibility wrappers - they're critical
- ❌ Don't use TanStack Query v4 patterns (multiple overloads) - use v5 single object
- ❌ Don't ignore cache invalidation patterns - follow existing mutation hooks
- ❌ Don't hardcode node types - use NodeType enum consistently  
- ❌ Don't skip integration testing - hooks must work with real API
- ❌ Don't remove old hooks until full migration is validated
- ❌ Don't forget to handle parent-child relationships properly (layers->domains->terms)

## Quality Score Assessment
**Confidence Level: 9/10** - This PRP provides comprehensive context with:
✅ Complete codebase analysis with exact file references  
✅ External best practices research for TanStack Query v5
✅ Step-by-step migration plan with preservation of existing behavior
✅ Executable validation loops at multiple levels  
✅ Backward compatibility strategy to prevent breaking changes
✅ Real code patterns from existing codebase to follow
✅ Known gotchas and library-specific requirements
✅ Progressive implementation approach with safety checks

The high confidence comes from thorough research into existing patterns, external best practices, and a carefully planned migration strategy that maintains system stability throughout the process.