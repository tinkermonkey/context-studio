# MSW + Axios Adapter Investigation Summary

## Issue

When attempting to use MSW (Mock Service Worker) with axios in a Vitest/jsdom test environment, MSW was not consistently intercepting HTTP requests made by axios. This caused integration tests to hit real backends instead of using mock handlers.

## Root Cause Analysis

### The Problem

1. **Adapter Selection**: Axios automatically selects an adapter based on the environment:
   - In browsers: `xhr` adapter (XMLHttpRequest)
   - In Node.js: `http` adapter (Node's http/https modules)
   - In jsdom: Can use `fetch`, `xhr`, or `http` depending on globals available

2. **MSW Timing**: MSW patches Node's `http` and `https` modules when `server.listen()` is called. If modules import and capture references to http/https before MSW patches them, the patches don't take effect.

3. **Module Loading Order**: In our setup:
   - Vitest loads test files
   - Test files import `apiClient` from axios.ts
   - axios.ts creates axios instance and may capture http/https references
   - MSW server starts later in test setup or per-test

### Investigation Steps Attempted

1. **Forced Node HTTP Adapter**: Tried to force axios to use Node's HTTP adapter by:
   - Removing `fetch` and `XMLHttpRequest` from global scope
   - Setting custom adapters on axios instances
   - Creating MSW-compatible adapters that defer http/https imports

2. **Early MSW Startup**: Moved MSW server startup to `vitest.setup.ts` to patch Node internals before other modules load.

3. **Custom Adapters**: Created adapters that import http/https inside the adapter function rather than at module load time.

### Results

- **Direct fetch + MSW**: Works reliably (MSW intercepts fetch calls)
- **Axios + MSW**: Inconsistent interception due to timing and adapter selection
- **Service-level spies**: Work reliably in all environments

## Solution: Service-Level Mocking

Instead of relying on MSW to intercept network calls made by axios, we use Vitest spies at the service layer:

```typescript
// Instead of MSW network interception:
server.use(rest.put("/api/domains/1", handler));

// Use service-level spy:
const mockUpdate = vi
  .spyOn(domainService, "update")
  .mockResolvedValue(mockData);
```

### Benefits of Service-Level Mocking

1. **Reliability**: Works consistently across environments
2. **Determinism**: No timing or adapter selection issues
3. **Precision**: Mock exactly what the component uses
4. **Maintainability**: Easier to understand and debug

### When to Use Each Approach

**MSW (network-level)**:

- ✅ Components that use fetch directly
- ✅ Testing network error handling
- ✅ End-to-end scenarios where you want to test the full HTTP stack

**Service-level spies**:

- ✅ Components that use React Query hooks
- ✅ Testing component behavior with different data states
- ✅ Unit/integration tests focused on UI logic
- ✅ When axios + MSW interception is unreliable

## Implementation

The `DomainDetails` integration test now uses:

- Service-level spy: `vi.spyOn(domainService, 'update')`
- Hoistable mocks for router and hooks to avoid external dependencies
- Assertions on `QueryClient.invalidateQueries` calls

This approach is deterministic and tests the actual component behavior without network dependency.

## Files Updated

- `test/integration/domain_edit.integration.test.tsx` - Converted to service-level spy
- `test/integration/msw_adapter_repro.test.ts` - Investigation demo
- `test/utils/forceMSWAdapter.ts` - Experimental adapter (kept for reference)
- `test/utils/mswCompatibleHttpAdapter.ts` - Alternative adapter approach
- `test/msw/setupTests.ts` - Standardized MSW helper for tests that can use it

## Recommendation

Continue using service-level spies for axios-based integration tests while keeping MSW available for tests that can reliably use it (e.g., components that use fetch directly).
