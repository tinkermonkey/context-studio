# Test Plan: Ontology Management Full CRUD Chain

## Overview

This test validates the complete end-to-end CRUD chain for the ontology management system, covering the creation and interconnection of core entities: Taxonomy, ConceptScheme, Class, PropertyDefinition, and Relationship. The test also exercises the undo functionality to verify that soft-deleted entities can be restored within the 8-second undo window.

## Scope

- **Entities involved**: Taxonomy, ConceptScheme, Class, PropertyDefinition, Relationship
- **Pages involved**: `/app/taxonomies`, `/app/schemes`, `/app/schemes/{schemeId}`, `/app/properties`, `/app/relationships`, `/app/classes/{classId}`
- **External dependencies**: Back-end API (no external services required)
- **API endpoints**:
  - `POST /api/taxonomies` (create)
  - `GET /api/taxonomies` (read)
  - `POST /api/taxonomies/{taxonomy_id}/schemes` (create scheme)
  - `GET /api/schemes` (read schemes)
  - `POST /api/schemes/{scheme_id}/classes` (create class)
  - `GET /api/classes` (read classes)
  - `POST /api/properties` (create property)
  - `GET /api/properties` (read properties)
  - `POST /api/relationships` (create relationship)
  - `DELETE /api/classes/{class_id}` (soft delete class)

## Test Cases

### Test Case 1: Create a Taxonomy

**Preconditions**: User is logged in and navigated to `/app/taxonomies`

**Steps**:
1. Click "Add Taxonomy" button with selector `taxonomy-add-button`
2. Modal opens with selector `taxonomy-create-modal`
3. Locate form with selector `taxonomy-form`
4. Fill in title field (selector `taxonomy-title-input`) with "Test Taxonomy: Full CRUD Chain"
5. Fill in description field (selector `taxonomy-description-input`) with "Comprehensive test of ontology CRUD operations"
6. Click submit button with selector `taxonomy-submit-button`
7. Modal closes automatically

**Expected Result**:
- Taxonomy appears in the list on `/app/taxonomies`
- Taxonomy has `id`, `title`, `description`, and `version=1`
- Taxonomy is visible in the table and searchable

**Selectors Used**: `taxonomy-add-button`, `taxonomy-create-modal`, `taxonomy-form`, `taxonomy-title-input`, `taxonomy-description-input`, `taxonomy-submit-button`

**Invariants Verified**:
- Taxonomy `title` is required and non-empty
- Taxonomy `version` starts at 1
- Timestamps (`created_at`, `last_modified`) are set correctly

---

### Test Case 2: Create a Concept Scheme Under the Taxonomy

**Preconditions**:
- Taxonomy created in Test Case 1 (factory-created `taxonomy_id`)
- User is on `/app/schemes`

**Steps**:
1. Click "Add Scheme" button with selector `scheme-add-button`
2. Modal opens with selector `scheme-create-modal`
3. Locate form with selector `scheme-form`
4. Fill in title field (selector `scheme-title-input`) with "Test Concept Scheme"
5. Fill in description field (selector `scheme-description-input`) with "Scheme for testing class hierarchy"
6. Select the parent taxonomy from the dropdown (the taxonomy created in Test Case 1)
7. Click submit button with selector `scheme-submit-button`
8. Modal closes

**Expected Result**:
- ConceptScheme appears in the list on `/app/schemes`
- ConceptScheme is linked to the parent Taxonomy via `taxonomy_id`
- ConceptScheme is visible in the table

**Selectors Used**: `scheme-add-button`, `scheme-create-modal`, `scheme-form`, `scheme-title-input`, `scheme-description-input`, `scheme-submit-button`

**Invariants Verified**:
- ConceptScheme `title` is required
- ConceptScheme has a non-null `taxonomy_id`
- ConceptScheme `version` starts at 1

---

### Test Case 3: Create a Class in the Concept Scheme

**Preconditions**:
- ConceptScheme created in Test Case 2 (factory-created `scheme_id`)
- User navigates to `/app/schemes/{scheme_id}` (detail page for the scheme)

**Steps**:
1. Verify scheme detail page loads with classes table
2. Click "Add Class" button with selector `scheme-detail-add-class-button`
3. Modal opens with class create form
4. Fill in class name field with "Parent Class"
5. Fill in description field with "A parent class for testing hierarchy"
6. Optionally select domain (leave empty for root class)
7. Optionally select parent class (leave empty since this is a root class)
8. Click submit button
9. Modal closes and new class appears in the classes table

**Expected Result**:
- Class appears in the classes table on the scheme detail page
- Class has `id`, `title`, `description`, `concept_scheme_id`, `taxonomy_id`, and `version=1`
- Class `concept_scheme_id` matches the current scheme
- Class is visible in the table with schema-row-* selector pattern: `schema-row-{classId}`

**Selectors Used**: `scheme-detail-add-class-button`, class form fields (from class-editor-form or similar)

**Invariants Verified**:
- Class `title` is required
- Class `concept_scheme_id` is set to the parent scheme
- Class `parent_class_id` is null for root classes
- Class `version` starts at 1

---

### Test Case 4: Create a Second Class and Add a Property to the First Class

**Preconditions**:
- First class created in Test Case 3 (factory-created `class_id_1`)
- User is on `/app/schemes/{scheme_id}` detail page

**Steps**:

**Part A: Create second class**:
1. Click "Add Class" button again
2. Fill in name with "Child Class"
3. Fill in description with "A child class for testing relationships"
4. Optionally select the first class as parent class
5. Submit
6. Second class now appears in the table

**Part B: Create a PropertyDefinition**:
1. Navigate to `/app/properties`
2. Click "Add Property" button with selector `property-add-button`
3. Modal opens with selector `property-create-modal`
4. Locate form with selector `property-create-form`
5. Fill in identifier field (selector `property-definition-identifier-input`) with "broader"
6. Fill in title field (selector `property-definition-title-input`) with "Broader"
7. Fill in description field (selector `property-definition-description-input`) with "Has a broader/parent concept"
8. Click submit button with selector `property-definition-submit-button`
9. Modal closes

**Part C: Verify property appears in drawer**:
1. On `/app/properties` page, find the newly created property in the list
2. Click on the property row to open the property drawer
3. Verify drawer appears with selector `property-drawer`
4. Verify read-only identifier field with selector `property-drawer-identifier`
5. Verify editable title field with selector `property-drawer-title-input`
6. Verify editable description field with selector `property-drawer-description-input`

**Expected Result**:
- Second class appears in the scheme detail page
- PropertyDefinition is created with `id`, `identifier`, `title`, `description`, `version=1`
- PropertyDefinition is visible in the properties list
- Property drawer displays all expected fields

**Selectors Used**:
- `property-add-button`, `property-create-modal`, `property-create-form`, `property-definition-identifier-input`, `property-definition-title-input`, `property-definition-description-input`, `property-definition-submit-button`
- `property-drawer`, `property-drawer-identifier`, `property-drawer-title-input`, `property-drawer-description-input`

**Invariants Verified**:
- PropertyDefinition `identifier` is required and globally unique
- PropertyDefinition `title` is required
- PropertyDefinition `version` starts at 1

---

### Test Case 5: Create a Relationship Between Classes

**Preconditions**:
- Two classes created in Test Cases 3 and 4 (factory-created `class_id_1`, `class_id_2`)
- PropertyDefinition created in Test Case 4 (factory-created `property_id`)
- User navigates to `/app/relationships`

**Steps**:
1. Click "Add Relationship" button with selector `relationship-add-button`
2. Dialog or modal opens
3. Select source class dropdown (selector `relationship-source-class-filter`) and choose the first class
4. Select target class dropdown (selector `relationship-target-class-filter`) and choose the second class
5. Select property type dropdown and choose the PropertyDefinition created in Test Case 4
6. Click "Save" or "Create" button
7. Dialog closes

**Expected Result**:
- Relationship appears in the relationships list
- Relationship has `id`, `source_id` (first class), `target_id` (second class), `property_definition_id` (the property)
- Relationship is visible in the table and can be found via the source/target filters

**Selectors Used**: `relationship-add-button`, `relationship-source-class-filter`, `relationship-target-class-filter`

**Invariants Verified**:
- Relationship `source_id` and `target_id` must reference existing, non-deleted Classes
- Relationship `property_definition_id` must reference an existing PropertyDefinition
- Relationship has only `created_at` (no version field)

---

### Test Case 6: Delete the First Class with Type-to-Confirm

**Preconditions**:
- First class created in Test Case 3 (factory-created `class_id_1`)
- User navigates to the scheme detail page and finds the class in the table

**Steps**:
1. Locate the class row using the factory-created ID
2. Click the actions button for that row (selector `class-row-actions-{classId}` where `{classId}` is the factory ID)
3. A context menu or dropdown appears (may not have explicit selector, use semantic locator for "Delete")
4. Click "Delete" option in the menu
5. Type-to-confirm dialog appears with selector `type-confirm-dialog`
6. User must type a confirmation phrase (e.g., "Delete") into the input field with selector `type-confirm-input`
7. Confirm button (selector `type-confirm-button`) becomes enabled after typing the correct phrase
8. Click the confirm button
9. Dialog closes and class is removed from the visible list

**Expected Result**:
- Class is soft-deleted (marked as deleted in the database)
- Class no longer appears in the classes table on the scheme detail page
- Toast notification appears with an undo action

**Selectors Used**: `class-row-actions-*`, `type-confirm-dialog`, `type-confirm-input`, `type-confirm-button`

**Invariants Verified**:
- Soft delete behavior (entity is not removed from database, just marked as deleted)
- Type-to-confirm dialog requires exact phrase match before deletion
- Toast with undo action appears immediately after deletion

---

### Test Case 7: Undo the Deletion Within 8 Seconds

**Preconditions**:
- Class was just soft-deleted in Test Case 6
- Toast with undo action is visible
- User has up to 8 seconds to click undo

**Steps**:
1. Locate the toast notification on the screen
2. Find the undo action button in the toast with selector pattern `toast-action-*`
3. Click the undo action button immediately (within 8 seconds of deletion)
4. Toast closes
5. Wait for the page to refresh or the table to update

**Expected Result**:
- Toast disappears
- Undo operation is sent to the back-end
- Deletion is reversed
- Back-end generates a new UUID for the restored class
- Class reappears in the classes table with a new ID

**Selectors Used**: `toast-action-*`

**Invariants Verified**:
- Undo must complete within 8-second window
- Restored entity receives a new UUID (not the same as the deleted entity)
- Restored class is visible in the table again
- No error messages appear

---

### Test Case 8: Verify the Restored Class Appears in the Table

**Preconditions**:
- Undo action completed in Test Case 7
- User is on the scheme detail page

**Steps**:
1. Locate the schema table with selector `schema-table`
2. Search or filter to find the class by title (use schema-search-input if needed)
3. Verify the class appears as a new row in the table
4. Verify the row uses the pattern `schema-row-{classId}` where the ID is different from the original (because it's a new UUID from undo)

**Expected Result**:
- Class appears in the classes table
- Row is visible and interactive
- The class title matches the original class title ("Parent Class")
- Description is preserved ("A parent class for testing hierarchy")
- The ID in the row is NOT the same as the pre-deletion ID (it's a fresh restoration with a new UUID)

**Selectors Used**: `schema-table`, `schema-search-input`, `schema-row-*`

**Invariants Verified**:
- Restored entity has a new UUID
- All fields except ID and created_at are preserved from the original
- Class is once again linked to its parent scheme and taxonomy

---

## Coverage Analysis

### CRUD Coverage

- **Create**: ✓ Test Cases 1–5 cover creation of Taxonomy, ConceptScheme, Class (2 instances), PropertyDefinition, and Relationship
- **Read**: ✓ Entities are read/displayed in tables and detail views throughout the test chain
- **Update**: Partially tested (drawer fields are editable, but not explicitly updated in this plan)
- **Delete**: ✓ Test Case 6 covers soft delete with type-to-confirm
- **Restore (Undo)**: ✓ Test Case 7 covers 8-second undo window

### Edge Cases

- **Cascade deletes**: Not explicitly tested (would require separate plan)
- **Orphaned relationships**: Test Case 6 deletion of a class orphans the relationship created in Test Case 5 (implicit coverage)
- **Type-to-confirm validation**: Test Case 6 validates the confirmation phrase mechanism
- **Undo window**: Test Case 7 validates the 8-second undo window
- **UUID restoration**: Test Case 8 validates that restored entities receive new UUIDs

### Anti-Pattern Validations

- ✓ No `waitForTimeout()` without conditions (use `expect(selector).toBeVisible()` or `waitForLoadState()`)
- ✓ No hardcoded UUIDs (factory-created IDs only)
- ✓ No invented selectors (all selectors verified in `selector-registry.yaml`)
- ✓ No vacuous assertions (every assertion validates meaningful behavior)
- ✓ No text-based selectors for mutable content (use `data-testid` and pattern-based selectors like `schema-row-*`)
- ✓ Cleanup handled via `clearTestData` in `afterEach`

---

## Open Questions

None. All required selectors are documented in `ux/selector-registry.yaml`:

- ✓ `taxonomy-add-button`, `taxonomy-create-modal`, `taxonomy-form`, `taxonomy-title-input`, `taxonomy-description-input`, `taxonomy-submit-button`
- ✓ `scheme-add-button`, `scheme-create-modal`, `scheme-form`, `scheme-title-input`, `scheme-description-input`, `scheme-submit-button`
- ✓ `scheme-detail-add-class-button`
- ✓ `property-add-button`, `property-create-modal`, `property-create-form`, `property-definition-identifier-input`, `property-definition-title-input`, `property-definition-description-input`, `property-definition-submit-button`
- ✓ `property-drawer`, `property-drawer-identifier`, `property-drawer-title-input`, `property-drawer-description-input`
- ✓ `relationship-add-button`, `relationship-source-class-filter`, `relationship-target-class-filter`
- ✓ `class-row-actions-*` (pattern-based, dynamic suffix)
- ✓ `type-confirm-dialog`, `type-confirm-input`, `type-confirm-button`
- ✓ `toast-action-*` (pattern-based, dynamic suffix)
- ✓ `schema-table`, `schema-search-input`, `schema-row-*` (pattern-based, dynamic suffix)

---

## Factory Usage

This plan uses factory patterns for setup and teardown:

- **Setup**: Create test data via factories (faster than UI):
  ```typescript
  const taxonomy = await createTaxonomy(page, {
    title: "Test Taxonomy: Full CRUD Chain",
    description: "Comprehensive test of ontology CRUD operations",
  });
  const scheme = await createConceptScheme(page, {
    taxonomy_id: taxonomy.id,
    title: "Test Concept Scheme",
    description: "Scheme for testing class hierarchy",
  });
  const class1 = await createClass(page, {
    concept_scheme_id: scheme.id,
    title: "Parent Class",
    description: "A parent class for testing hierarchy",
  });
  const class2 = await createClass(page, {
    concept_scheme_id: scheme.id,
    title: "Child Class",
    description: "A child class for testing relationships",
  });
  const property = await createPropertyDefinition(page, {
    identifier: "broader",
    title: "Broader",
    description: "Has a broader/parent concept",
  });
  ```

- **Teardown**: Use `clearTestData(page)` in `test.afterEach()` at the describe level:
  ```typescript
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });
  ```

---

## Test Data Lifecycle

1. **Setup**: Use factory functions to create Taxonomy, ConceptScheme, Classes, PropertyDefinition via API (fast, deterministic)
2. **Test Execution**: Follow the UI interactions in steps 1–8 above
3. **Verification**: Assert UI state changes match expected behavior (visibility, table rows, etc.)
4. **Cleanup**: Call `clearTestData(page)` in `test.afterEach()` to remove all test data

---

## Notes for Generator

- Test should use TanStack Router for navigation (e.g., `page.goto("/app/taxonomies")`)
- Use Playwright's `expect()` for assertions, not manual checks
- Use `page.locator('[data-testid="..."]')` for selector-based navigation
- For pattern-based selectors like `schema-row-*`, use `page.locator('[data-testid^="schema-row-"]')` or similar
- Wait for table updates after undo using `expect(page.locator('[data-testid="schema-row-*"]')).toContainText(...)`
- Capture the restored class ID from the table row for verification (use `getAttribute` on the row)
- Ensure the restored class ID is different from the original (print both IDs for debugging)
