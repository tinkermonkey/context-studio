# E2E Test Expansion Plan

## Overview

This document outlines the plan to expand end-to-end test coverage for Context Studio. The current e2e infrastructure is robust and fully functional, with comprehensive Layer Management tests serving as an excellent foundation. This plan prioritizes testing core knowledge graph workflows first, then advanced features.

**Current Status:** 13 passing tests covering Layer Management and basic smoke tests
**Goal:** Comprehensive coverage of all critical user workflows

---

## Testing Infrastructure Assessment

### ✅ Infrastructure Status: EXCELLENT

**Strengths:**
- Playwright configured with global setup/teardown for server lifecycle management
- Isolated test databases created fresh for each test run
- Backend (FastAPI on port 8888) and frontend (Vite on port 3888) automatically managed
- Sequential test execution prevents race conditions
- Well-structured test helpers and fixtures
- `apiRequest()` helper for backend validation
- Proper use of `data-testid` attributes for reliable selectors

**Test Pattern (from `layers.spec.ts`):**
```typescript
// 1. Display Tests - Verify UI renders correctly
// 2. Create Tests - Test record creation with validation
// 3. Edit Tests - Test record updates
// 4. Delete Tests - Test single and bulk deletion
// 5. Search/Filter Tests - Test filtering functionality
// 6. Navigation Tests - Test routing between views
// 7. Validation Tests - Test form validation
// 8. Backend Verification - Use apiRequest() to verify persistence
```

---

## Test Coverage Gaps

### Currently Covered ✅
- **Layer Management** (`e2e/tests/layers.spec.ts`)
  - Complete CRUD operations
  - Bulk delete
  - Search and filtering
  - Form validation
  - Navigation to detail views
  - Cancel operations

### Not Yet Covered ❌

#### High Priority - Core Knowledge Graph
1. **Domain Management** - Domains belong to layers
2. **Term Management** - Terms belong to domains and layers (hierarchical)
3. **Structure Node Detail View** - Detailed view with relationships
4. **Node Relationships** - Links between nodes with predicates

#### Medium Priority - Data Integration
5. **Predicate Management** - Semantic relationship definitions
6. **Reference Data Search** - External data source integration
7. **RAG Experiments** - Test paragraph annotation and pipeline testing

#### Low Priority - Admin Features
8. **Pipeline Configuration** - LLM pipeline flavor management

---

## Implementation Plan

### Phase 1: Core Knowledge Graph (Week 1-2)

#### 1.1 Domain Management Tests
**File:** `e2e/tests/domains.spec.ts`

**Test Cases:**
- [ ] Display domains table with layer associations
- [ ] Create domain with layer selection
- [ ] Edit domain properties and layer association
- [ ] Delete single domain
- [ ] Bulk delete domains
- [ ] Filter domains by layer (sidebar navigation)
- [ ] Search domains by title
- [ ] Navigate to domain detail view
- [ ] Validate required fields (title, layer)
- [ ] Cancel domain creation
- [ ] Verify backend persistence for all operations

**Key UI Elements to Test:**
- `[data-testid="domain-table"]`
- `[data-testid="domain-add-button"]`
- `[data-testid="domain-title-input"]`
- `[data-testid="domain-layer-selector"]`
- `[data-testid="domain-submit-button"]`
- Layer filter sidebar with collapsible layer list

**Backend Validation:**
```typescript
// Verify domain created with correct layer association
const response = await apiRequest(page, '/api/structure_nodes?node_type=domain');
const domain = response.data.find(d => d.title === domainTitle);
expect(domain.parent_id).toBe(layerId);
```

#### 1.2 Term Management Tests
**File:** `e2e/tests/terms.spec.ts`

**Test Cases:**
- [ ] Display terms table with domain/layer associations
- [ ] Create term with domain and layer selection
- [ ] Edit term properties and associations
- [ ] Delete single term
- [ ] Bulk delete terms
- [ ] Filter terms by layer
- [ ] Filter terms by domain
- [ ] Filter terms by both layer and domain
- [ ] Search terms by title
- [ ] Navigate to term detail view
- [ ] Validate required fields (title, domain)
- [ ] Cancel term creation
- [ ] Verify hierarchical relationships (layer → domain → term)

**Key UI Elements to Test:**
- `[data-testid="term-table"]`
- `[data-testid="term-add-button"]`
- `[data-testid="term-title-input"]`
- `[data-testid="term-domain-selector"]`
- Hierarchical sidebar with collapsible layers and domains

**Complex Scenario:**
```typescript
// Create layer → domain → term hierarchy
// Filter by layer, verify only terms in that layer's domains appear
// Filter by domain, verify only terms in that domain appear
// Verify cascade filtering works correctly
```

#### 1.3 Structure Node Detail View Tests
**File:** `e2e/tests/node-details.spec.ts`

**Test Cases:**
- [ ] Load and display layer detail page
- [ ] Load and display domain detail page
- [ ] Load and display term detail page
- [ ] Display node metadata (title, definition, type, dates)
- [ ] Edit node title inline
- [ ] Edit node definition inline
- [ ] View child nodes section (e.g., domains under a layer)
- [ ] Navigate to child nodes
- [ ] View relationships/links section
- [ ] Handle nodes with no children
- [ ] Handle nodes with no relationships
- [ ] Error handling for invalid node IDs
- [ ] Back navigation to table view

**Key UI Elements to Test:**
- `[data-testid="node-detail-title"]`
- `[data-testid="node-detail-definition"]`
- `[data-testid="node-detail-type"]`
- `[data-testid="node-children-section"]`
- `[data-testid="node-relationships-section"]`

---

### Phase 2: Knowledge Graph Relationships (Week 3)

#### 2.1 Node Relationship Tests
**File:** `e2e/tests/node-relationships.spec.ts`

**Test Cases:**
- [ ] View existing relationships on detail page
- [ ] Create relationship between two terms (term → term)
- [ ] Select predicate for relationship
- [ ] Create custom predicate inline
- [ ] Delete relationship
- [ ] Navigate via relationship links
- [ ] View bidirectional relationships
- [ ] Validate relationship creation (source, target, predicate required)
- [ ] Handle relationship creation errors

**Key UI Elements to Test:**
- `[data-testid="add-relationship-button"]`
- `[data-testid="relationship-source-selector"]`
- `[data-testid="relationship-target-selector"]`
- `[data-testid="relationship-predicate-selector"]`
- `[data-testid="relationship-list"]`

**Complex Scenario:**
```typescript
// Create: Layer A → Domain B → Term C → (related-to) → Term D
// Navigate: Term C detail → click relationship → lands on Term D detail
// Verify: Both terms show the relationship
// Delete: Remove relationship from Term D
// Verify: Relationship removed from both terms
```

#### 2.2 Predicate Management Tests
**File:** `e2e/tests/predicates.spec.ts`

**Test Cases:**
- [ ] Display predicates table
- [ ] Create predicate
- [ ] Edit predicate
- [ ] Delete predicate
- [ ] Map predicate to DBpedia property
- [ ] Search predicates
- [ ] Validate required fields
- [ ] Verify predicates available in relationship selector

**Key UI Elements to Test:**
- `[data-testid="predicate-table"]`
- `[data-testid="predicate-add-button"]`
- `[data-testid="predicate-label-input"]`
- `[data-testid="predicate-dbpedia-mapping"]`

---

### Phase 3: Data Integration Features (Week 4)

#### 3.1 Reference Data Search Tests
**File:** `e2e/tests/reference-search.spec.ts`

**Test Cases:**
- [ ] Load reference search page
- [ ] Search ConceptNet for terms
- [ ] Search DBpedia for terms
- [ ] Search Wikidata for terms
- [ ] View search results
- [ ] Paginate through results
- [ ] View reference entity details
- [ ] Link reference entity to structure node
- [ ] Filter by reference source
- [ ] Handle search errors gracefully

**Key UI Elements to Test:**
- `[data-testid="reference-search-input"]`
- `[data-testid="reference-source-filter"]`
- `[data-testid="reference-results-list"]`
- `[data-testid="reference-link-button"]`

**Note:** May require mocked reference API responses if external APIs are slow or rate-limited.

#### 3.2 RAG Experiments Tests
**File:** `e2e/tests/rag-experiments.spec.ts`

**Test Cases:**
- [ ] Load RAG experiments page
- [ ] Create test paragraph
- [ ] Edit test paragraph
- [ ] Delete test paragraph
- [ ] Annotate paragraph with expected chunks
- [ ] Select pipeline for testing
- [ ] Run pipeline test
- [ ] View test results
- [ ] Compare multiple pipeline results
- [ ] Navigate between test list and results

**Key UI Elements to Test:**
- `[data-testid="test-paragraph-editor"]`
- `[data-testid="annotation-selector"]`
- `[data-testid="pipeline-test-runner"]`
- `[data-testid="test-results-viewer"]`

**Note:** These tests may require mocked LLM responses or test pipeline configurations.

---

### Phase 4: Configuration Management (Week 5)

#### 4.1 Pipeline Configuration Tests
**File:** `e2e/tests/pipeline-config.spec.ts`

**Test Cases:**
- [ ] List pipeline flavors by type
- [ ] Create new pipeline flavor
- [ ] Edit pipeline flavor configuration
- [ ] Delete pipeline flavor
- [ ] Test pipeline flavor
- [ ] View pipeline execution history
- [ ] Navigate between pipeline types

**Note:** Lower priority as these are admin features used less frequently.

---

## Test Data Management Strategy

### Approach: Create via API, Verify via UI
To keep tests fast and focused, use the `apiRequest()` helper to create prerequisite data:

```typescript
// Example: Testing term creation requires a domain and layer
test('should create a term', async ({ page }) => {
  // Create prerequisites via API
  const layer = await apiRequest(page, '/api/structure_nodes', {
    method: 'POST',
    body: { title: 'Test Layer', node_type: 'layer' }
  });

  const domain = await apiRequest(page, '/api/structure_nodes', {
    method: 'POST',
    body: {
      title: 'Test Domain',
      node_type: 'domain',
      parent_id: layer.id
    }
  });

  // Now test term creation through UI
  await page.goto('/app/terms');
  await page.click('[data-testid="term-add-button"]');
  // ... rest of UI interaction
});
```

### Test Isolation
- Each test should create its own data
- Don't rely on data from previous tests
- Use unique timestamps in titles to avoid conflicts: `Test Layer ${Date.now()}`

---

## Required UI Updates for Testing

### Add Missing data-testid Attributes

The following components need `data-testid` attributes added for reliable test selectors:

#### Domains
- [ ] Domain table: `[data-testid="domain-table"]`
- [ ] Domain row: `[data-testid="domain-row-{id}"]`
- [ ] Add button: `[data-testid="domain-add-button"]`
- [ ] Title input: `[data-testid="domain-title-input"]`
- [ ] Definition input: `[data-testid="domain-definition-input"]`
- [ ] Layer selector: `[data-testid="domain-layer-selector"]`
- [ ] Submit button: `[data-testid="domain-submit-button"]`
- [ ] Actions dropdown: `[data-testid="domain-actions-dropdown"]`
- [ ] Delete action: `[data-testid="domain-delete-selected-action"]`
- [ ] Delete confirm: `[data-testid="domain-delete-confirm-button"]`
- [ ] Search input: `[data-testid="domain-search-input"]`

#### Terms
- [ ] Term table: `[data-testid="term-table"]`
- [ ] Term row: `[data-testid="term-row-{id}"]`
- [ ] Add button: `[data-testid="term-add-button"]`
- [ ] Title input: `[data-testid="term-title-input"]`
- [ ] Definition input: `[data-testid="term-definition-input"]`
- [ ] Domain selector: `[data-testid="term-domain-selector"]`
- [ ] Submit button: `[data-testid="term-submit-button"]`
- [ ] Actions dropdown: `[data-testid="term-actions-dropdown"]`
- [ ] Delete action: `[data-testid="term-delete-selected-action"]`
- [ ] Delete confirm: `[data-testid="term-delete-confirm-button"]`
- [ ] Search input: `[data-testid="term-search-input"]`

#### Predicates
- [ ] Predicate table: `[data-testid="predicate-table"]`
- [ ] Predicate row: `[data-testid="predicate-row-{id}"]`
- [ ] Add button: `[data-testid="predicate-add-button"]`
- [ ] Label input: `[data-testid="predicate-label-input"]`
- [ ] DBpedia mapping: `[data-testid="predicate-dbpedia-mapping"]`

#### Node Details
- [ ] Detail title: `[data-testid="node-detail-title"]`
- [ ] Detail definition: `[data-testid="node-detail-definition"]`
- [ ] Node type: `[data-testid="node-detail-type"]`
- [ ] Children section: `[data-testid="node-children-section"]`
- [ ] Relationships section: `[data-testid="node-relationships-section"]`
- [ ] Add relationship: `[data-testid="add-relationship-button"]`

#### Relationships
- [ ] Relationship list: `[data-testid="relationship-list"]`
- [ ] Source selector: `[data-testid="relationship-source-selector"]`
- [ ] Target selector: `[data-testid="relationship-target-selector"]`
- [ ] Predicate selector: `[data-testid="relationship-predicate-selector"]`

---

## Implementation Workflow

### For Each Test File:

1. **Add data-testid attributes** to the relevant components
2. **Write test skeleton** with describe blocks and test names
3. **Implement tests one at a time** following the layer test pattern
4. **Run tests frequently** using `npm run test:e2e:ui` for debugging
5. **Verify backend state** using `apiRequest()` helper
6. **Test edge cases** (validation, errors, empty states)
7. **Document any UI bugs found** during testing

### Running Tests During Development

```bash
# Run all e2e tests
npm run test:e2e

# Run with UI mode (recommended for development)
npm run test:e2e:ui

# Run specific test file
npx playwright test e2e/tests/domains.spec.ts

# Run in headed mode (see the browser)
npm run test:e2e:headed

# Debug a specific test
npm run test:e2e:debug
```

---

## Success Criteria

### Phase 1 Complete When:
- [ ] Domains: 10+ tests covering all CRUD operations
- [ ] Terms: 12+ tests covering CRUD with hierarchical filtering
- [ ] Node Details: 8+ tests covering all detail view features
- [ ] All tests pass reliably
- [ ] Backend state verified for all operations

### Phase 2 Complete When:
- [ ] Relationships: 8+ tests covering relationship CRUD
- [ ] Predicates: 8+ tests covering predicate management
- [ ] All tests pass reliably

### Phase 3 Complete When:
- [ ] Reference Search: 6+ tests covering search and linking
- [ ] RAG Experiments: 8+ tests covering annotation and testing

### Phase 4 Complete When:
- [ ] Pipeline Config: 6+ tests covering pipeline management

### Overall Success:
- **Target:** 60+ total e2e tests
- **Coverage:** All critical user workflows tested
- **Reliability:** All tests pass consistently in CI
- **Maintainability:** Tests follow consistent patterns from layers.spec.ts

---

## Estimated Timeline

- **Phase 1 (Core Graph):** 2 weeks
- **Phase 2 (Relationships):** 1 week
- **Phase 3 (Integration):** 1 week
- **Phase 4 (Admin):** 1 week

**Total:** 5 weeks for comprehensive e2e coverage

---

## Notes and Considerations

### Performance
- Tests run sequentially (1 worker) to avoid backend conflicts
- Current 13 tests complete in ~30 seconds
- Estimated 60 tests should complete in ~2-3 minutes
- Use `test.only()` during development to focus on specific tests

### CI/CD Integration
- Tests already configured for CI with retries
- Consider running e2e tests on PR creation
- May want to split tests into smoke (fast) and full (comprehensive) suites

### Maintenance
- Keep tests focused on user workflows, not implementation details
- Update tests when UI changes
- Add new tests for new features
- Review and refactor tests periodically to remove duplication

### Known Limitations
- LLM-dependent features may need mocked responses
- External API calls (reference data) may need mocking or caching
- Graph visualizations may be difficult to test thoroughly

---

## Getting Started

To begin implementing this plan:

1. Review the `e2e/tests/layers.spec.ts` test file as a reference
2. Start with Phase 1.1 (Domain Management Tests)
3. Add required `data-testid` attributes to domain components
4. Create `e2e/tests/domains.spec.ts` following the layer test pattern
5. Implement tests incrementally, running frequently
6. Move to Phase 1.2 (Terms) once domains are complete

---

## References

- [Playwright Documentation](https://playwright.dev/docs/intro)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [E2E Testing README](../e2e/README.md)
- [Existing Layer Tests](../e2e/tests/layers.spec.ts)
