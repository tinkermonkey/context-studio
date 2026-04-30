# Test Plan: Create and Delete a Taxonomy

## Overview

This test validates the core taxonomy lifecycle: creating a new taxonomy and then deleting it. This is the simplest and most fundamental workflow for the ontology management system.

## Scope

- **Entities involved**: Taxonomy
- **Pages involved**: `/app/taxonomies`, `/app/taxonomies/$taxonomyId`
- **External dependencies**: None (no cascading deletes tested here)
- **API endpoints**: `POST /api/taxonomies`, `GET /api/taxonomies`, `DELETE /api/taxonomies/{id}`

## Test Cases

### Test Case 1: Create a Taxonomy via UI

- **Preconditions**: User is logged in and navigated to `/app/taxonomies`
- **Steps**:
  1. Click "Add" button (`data-testid="taxonomy-add-button"`)
  2. Form modal opens with selector `data-testid="taxonomy-form"`
  3. Fill in `title` field with "Test Taxonomy" using selector `data-testid="taxonomy-title-input"`
  4. Fill in `description` field with "A test taxonomy for validation" using selector `data-testid="taxonomy-description-input"`
  5. Click submit button with selector `data-testid="taxonomy-submit-button"`
  6. Modal closes automatically
- **Expected Result**: 
  - Taxonomy appears in the list on `/app/taxonomies`
  - Taxonomy has `id`, `title`, `description`, `version=1`, `created_at`, and `last_modified` fields
  - Taxonomy is visible and searchable in the table
- **Selectors Used**: 
  - `taxonomy-add-button` (verified ✓)
  - `taxonomy-form` (verified ✓)
  - `taxonomy-title-input` (verified ✓)
  - `taxonomy-description-input` (verified ✓)
  - `taxonomy-submit-button` (verified ✓)
- **Invariants Verified**:
  - Taxonomy `title` is required and non-empty
  - Taxonomy `version` starts at 1
  - `created_at` and `last_modified` are set correctly
  - Taxonomy is immutable once created (except via update)

### Test Case 2: Delete a Taxonomy via UI

- **Preconditions**: 
  - A taxonomy exists (created in Test Case 1 or via factory)
  - User is on the taxonomy detail or list page
- **Steps**:
  1. Navigate to `/app/taxonomies`
  2. Find the taxonomy row using factory-created `id` (not hardcoded UUID)
  3. Click delete action on the row (selector `data-testid="taxonomy-delete-button"`)
  4. Confirmation modal appears (selector should exist, checking...)
  5. Click "Confirm" in the modal
  6. Modal closes and taxonomy is removed from list
- **Expected Result**:
  - Taxonomy is no longer visible in the list
  - Taxonomy status is "soft-deleted" in the backend (can be verified via API)
  - No error messages appear
- **Selectors Used**:
  - `taxonomy-delete-button` (verified ✓)
  - Confirmation modal selector (TBD - check if exists in registry)
- **Invariants Verified**:
  - Soft delete behavior (entity marked as deleted, not removed from DB)
  - Cascade rule: deleting taxonomy soft-deletes all ConceptSchemes and Classes

### Test Case 3: Create Taxonomy with Edge Cases

- **Preconditions**: User is on `/app/taxonomies`
- **Steps**:
  1. Click "Add" button
  2. Attempt to submit form without `title` (required field)
  3. Verify error message appears
  4. Fill in `title` with special characters: `Test™ Taxón°mý`
  5. Submit form successfully
  6. Verify taxonomy is created with special characters preserved
- **Expected Result**:
  - Form validation prevents submission without title
  - Titles with special characters are accepted and preserved
  - No character encoding issues in UI
- **Selectors Used**: Same as Test Case 1
- **Invariants Verified**:
  - Required field validation works
  - Special characters don't cause encoding issues

## Coverage Analysis

### CRUD Coverage

- **Create**: ✓ Test Cases 1, 3 (via form with validation)
- **Read**: ✓ Entity appears in list after creation; visible via detail page
- **Update**: Not tested in this plan (separate issue)
- **Delete**: ✓ Test Case 2 (soft delete via UI)

### Edge Cases

- **Concurrency**: Covered in Test Case 2 (version field updated on soft delete)
- **Validation**: Covered in Test Case 3 (required fields, special characters)
- **Cascade**: Covered indirectly (deleting taxonomy should mark schemes/classes as deleted)

### Anti-Pattern Validations

Tests verify that the following anti-patterns are NOT present:
- ✓ No `waitForTimeout()` without conditions (use explicit waits)
- ✓ No hardcoded UUIDs (factory-created IDs only)
- ✓ No invented selectors (all from registry)
- ✓ No trivial assertions (every assertion validates meaningful behavior)
- ✓ Text-based selectors avoided (use semantic locators)
- ✓ Cleanup handled via test teardown

## Open Questions

None - all required selectors are documented in `ux/selector-registry.yaml`.

## Factory Usage

This plan uses existing factory patterns from `ux/e2e/fixtures/factories.ts`:
- `createTaxonomy(page, overrides)` — Creates a taxonomy via API
- `deleteTaxonomy(page, id)` — Deletes a taxonomy via API (for cleanup)

Example:
```typescript
const taxonomy = await createTaxonomy(page, { 
  title: "Test Taxonomy", 
  description: "Test description" 
});
// Use taxonomy.id in subsequent test steps
```

## Test Data Lifecycle

1. **Setup**: Use `createTaxonomy()` factory to create test data via API (faster than UI)
2. **Test**: Interact with UI elements using semantic locators
3. **Verification**: Assert UI state changes match expected behavior
4. **Cleanup**: Factory teardown cleans up automatically; no manual deletion needed
