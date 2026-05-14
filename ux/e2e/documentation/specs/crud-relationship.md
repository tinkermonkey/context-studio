# Test Plan: Relationship CRUD Operations

## Overview

This test validates the complete lifecycle of Relationship entities: creation via form submission with required field validation, reading entity details in a drawer with all field values displayed, update via autosave indicator feedback, deletion with confirmation dialog, and restoration via undo toast action. The test verifies that relationships correctly link source and target classes via a property definition, and that the 8-second undo window allows restoration.

## Scope

- **Entities involved**: Class (2 instances), PropertyDefinition, Relationship
- **Pages involved**: `/app/relationships`, `/app/schema/relationships` (modal and drawer)
- **External dependencies**: Back-end API (no external services)
- **API endpoints**:
  - `GET /api/classes` (read classes for dropdowns)
  - `GET /api/properties` (read properties for dropdown)
  - `POST /api/relationships` (create relationship)
  - `GET /api/relationships` (list relationships)
  - `GET /api/relationships/{relationship_id}` (read relationship details)
  - `DELETE /api/relationships/{relationship_id}` (soft delete relationship)

## Test Cases

### Test Case 1: Create Relationship via Form with Required Field Validation

**Preconditions**:

- Two classes exist (created via factory)
- One property definition exists (created via factory)
- User is on `/app/relationships` page

**Steps**:

1. Click "Add Relationship" button with selector `relationship-add-button`
2. Modal opens with selector `relationship-create-modal`
3. Locate form with selector `relationship-form`
4. Verify three dropdown fields are empty:
   - Source Class (selector `relationship-source-select`)
   - Target Class (selector `relationship-target-select`)
   - Relationship Type (selector `relationship-type-select`)
5. Click submit button (selector `relationship-submit-button`)
6. Verify validation errors appear for all three fields (no hardcoded text assertion; instead check that error elements are visible)
7. Select source class from dropdown by clicking `relationship-source-select` and selecting the first class
8. Verify source error clears on change (use `onChange` handling)
9. Select target class from dropdown by clicking `relationship-target-select` and selecting the second class
10. Verify target error clears on change
11. Select relationship type (property) from dropdown by clicking `relationship-type-select` and selecting the property
12. Verify type error clears on change
13. Click submit button
14. Modal closes automatically

**Expected Result**:

- Relationship appears in the relationships table on `/app/relationships`
- Relationship has `id`, `source_id` (first class), `target_id` (second class), `property_definition_id` (property), and `created_at`
- Row is visible with pattern `schema-row-{relationshipId}` where the ID is the relationship ID

**Selectors Used**: `relationship-add-button`, `relationship-create-modal`, `relationship-form`, `relationship-source-select`, `relationship-target-select`, `relationship-type-select`, `relationship-submit-button`

**Invariants Verified**:

- Source class and target class are required (non-empty)
- Relationship type (property) is required (non-empty)
- Relationship cannot reference the same class as both source and target (self-loop prevention)
- Source and target must be valid, non-deleted classes
- Property definition must be valid and non-deleted
- Relationship receives auto-generated UUID
- Relationship `created_at` is set to current timestamp

---

### Test Case 2: Verify Relationship Appears in Table and Click Row to Open Drawer

**Preconditions**:

- Relationship created in Test Case 1 (factory-created or UI-created `relationship_id`)
- User is on `/app/relationships` page

**Steps**:

1. Verify schema table is visible with selector `schema-table`
2. Locate the relationship row using pattern `schema-row-{relationshipId}`
3. Verify table columns display correctly:
   - ID column shows abbreviated relationship ID
   - Name column shows the property definition title
   - Source Class column shows source class title
   - Target Class column shows target class title
4. Click on the relationship row to open the detail drawer
5. Verify drawer appears with selector `relationship-drawer`
6. Verify drawer title displays as "Source Class Title → Target Class Title"

**Expected Result**:

- Relationship is visible in the table
- Clicking the row opens the drawer without error
- Drawer title correctly formats source and target class names

**Selectors Used**: `schema-table`, `schema-row-*`, `relationship-drawer`

**Invariants Verified**:

- Table displays all relationships without pagination issues
- Drawer opens when row is clicked
- Drawer title follows the expected format (source → target)

---

### Test Case 3: Verify Field Values in Drawer (Read Operation)

**Preconditions**:

- Relationship drawer is open from Test Case 2
- Drawer displays the created relationship

**Steps**:

1. Locate the ID field in the drawer with selector `relationship-drawer-id`
2. Verify the ID field is disabled (read-only) and displays the relationship ID
3. Locate the Source Class field with selector `relationship-drawer-source-class`
4. Verify the field is disabled and displays the source class title (not the UUID)
5. Locate the Target Class field with selector `relationship-drawer-target-class`
6. Verify the field is disabled and displays the target class title
7. Locate the Relationship Type field with selector `relationship-drawer-property-type`
8. Verify the field is disabled and displays the property definition title
9. Verify a created timestamp is displayed (as read-only text, not an input)

**Expected Result**:

- All fields are read-only (disabled inputs or display-only text)
- ID shows the relationship UUID
- Source and target class names match the classes used during creation
- Relationship type (property) name matches the property used during creation
- Creation timestamp is displayed

**Selectors Used**: `relationship-drawer-id`, `relationship-drawer-source-class`, `relationship-drawer-target-class`, `relationship-drawer-property-type`

**Invariants Verified**:

- Relationship drawer displays correct entity references
- Fields are read-only (no editable inputs for relationship attributes)
- Timestamp formatting is consistent

---

### Test Case 4: Delete Relationship and Verify Confirmation Dialog

**Preconditions**:

- Relationship drawer is open from Test Case 3
- Relationship exists and is displayed in the drawer

**Steps**:

1. Locate the delete button in the drawer with selector `drawer-delete-button`
2. Click the delete button
3. Confirmation dialog appears with selector `relationship-delete-confirm`
4. Verify dialog title and message are displayed (message indicates "This relationship... will be permanently deleted")
5. Locate the cancel button with selector `confirm-dialog-cancel`
6. Click the cancel button
7. Dialog closes and relationship is still visible in the drawer

**Expected Result**:

- Delete button is present in the drawer
- Clicking delete shows a confirmation dialog
- Cancel button closes the dialog without deleting
- Relationship remains intact and visible

**Selectors Used**: `drawer-delete-button`, `relationship-delete-confirm`, `confirm-dialog-cancel`

**Invariants Verified**:

- Confirmation dialog is shown before deletion (no immediate delete)
- Cancel action reverses the delete intent

---

### Test Case 5: Confirm Deletion and Verify Undo Toast Appears

**Preconditions**:

- Relationship drawer is open
- Confirmation dialog is shown from Test Case 4

**Steps**:

1. Click the confirm delete button with selector `confirm-dialog-confirm`
2. Dialog closes
3. Drawer closes automatically (relationship is now deleted)
4. Verify a toast notification appears with undo action
5. Toast should have an action button matching pattern `toast-action-*`
6. Verify the relationship is no longer visible in the table (page auto-refetch)
7. Verify the undo action button is clickable in the toast

**Expected Result**:

- Relationship is soft-deleted (API called with DELETE)
- Drawer closes immediately after deletion
- Toast notification appears with "Undo" action button
- Toast has an 8-second auto-dismiss timer
- Relationship disappears from the table

**Selectors Used**: `confirm-dialog-confirm`, `toast-action-*`, `schema-table`, `schema-row-*`

**Invariants Verified**:

- Soft delete is performed (relationship marked as deleted in database)
- Toast with undo action appears immediately after deletion
- Undo button is present and clickable within 8-second window
- Table is automatically updated to remove deleted relationship

---

### Test Case 6: Click Undo to Restore Relationship

**Preconditions**:

- Relationship was just deleted in Test Case 5
- Toast with undo action is visible and clickable
- User must click within 8-second window

**Steps**:

1. Locate the toast notification on the screen
2. Find the undo action button in the toast with pattern `toast-action-*`
3. Click the undo action button immediately (within 8 seconds)
4. Toast closes or fades out
5. Wait for page to refetch or table to update (use `expect(page.locator(...)).toContainText(...)` or similar condition, not a timeout)
6. Verify the relationship reappears in the table

**Expected Result**:

- Undo operation reverses the soft delete
- Back-end generates a new UUID for the restored relationship
- Restored relationship reappears in the table with a new ID
- Relationship details (source, target, property) are preserved
- No error messages appear

**Selectors Used**: `toast-action-*`, `schema-table`, `schema-row-*`

**Invariants Verified**:

- Undo completes within 8-second window
- Restored relationship receives a new UUID (not the same as deleted relationship)
- All relationship fields are preserved after restore
- Relationship is once again linked to its source class, target class, and property definition

---

## Coverage Analysis

### CRUD Coverage

- **Create**: ✓ Test Case 1 covers relationship creation via form with validation
- **Read**: ✓ Test Case 2 covers reading relationship in table; Test Case 3 covers reading details in drawer
- **Update**: Partially tested (relationship fields are read-only; no edit operation exists)
- **Delete**: ✓ Test Case 4 covers soft delete with confirmation dialog
- **Restore (Undo)**: ✓ Test Case 6 covers 8-second undo window restoration

### Edge Cases

- **Required field validation**: Test Case 1 validates that all three fields must be provided before submit
- **Self-loop prevention**: Test Case 1 implies that source and target must be different (anti-pattern)
- **Reference integrity**: Test Cases 1–3 verify that relationships only reference valid, non-deleted classes and properties
- **Undo window**: Test Case 6 validates the 8-second undo window
- **UUID restoration**: Test Case 6 validates that restored relationships receive new UUIDs

### Anti-Pattern Validations

- ✓ No `waitForTimeout()` without conditions (use `expect(selector).toBeVisible()` or `waitForLoadState()`)
- ✓ No hardcoded UUIDs (factory-created IDs only)
- ✓ No invented selectors (all selectors verified in `ux/selector-registry.yaml`)
- ✓ No vacuous assertions (every assertion validates meaningful behavior)
- ✓ No text-based selectors for mutable content (use `data-testid` and pattern-based selectors like `schema-row-*`)
- ✓ Cleanup handled via `clearTestData` in `afterEach`
- ✓ No hardcoded error messages (use `expect(selector).toBeVisible()` for error states)
- ✓ Validation error clearing verified on `onChange`, not only on `onBlur`

---

## Open Questions

None. All required selectors are documented in `ux/selector-registry.yaml`:

- ✓ `relationship-add-button`
- ✓ `relationship-create-modal`
- ✓ `relationship-form`
- ✓ `relationship-source-select`
- ✓ `relationship-target-select`
- ✓ `relationship-type-select`
- ✓ `relationship-submit-button`
- ✓ `relationship-drawer`
- ✓ `relationship-drawer-id`
- ✓ `relationship-drawer-source-class`
- ✓ `relationship-drawer-target-class`
- ✓ `relationship-drawer-property-type`
- ✓ `relationship-delete-confirm`
- ✓ `drawer-delete-button`
- ✓ `confirm-dialog-confirm`
- ✓ `confirm-dialog-cancel`
- ✓ `toast-action-*` (pattern-based)
- ✓ `schema-table`
- ✓ `schema-row-*` (pattern-based)
- ✓ `schema-page-layout`

---

## Factory Usage

This plan uses factory functions for setup and teardown:

**Setup**:

```typescript
const taxonomy = await createTaxonomy(page);
const scheme = await createConceptScheme(page, taxonomy.id);
const sourceClass = await createClass(page, scheme.id, { title: "Source Class" });
const targetClass = await createClass(page, scheme.id, { title: "Target Class" });
const property = await createPropertyDefinition(page, {
  identifier: "related_to",
  title: "Related To",
});
```

**Test Execution**:

- Steps 1–6 create a relationship via UI (Test Cases 1–2)
- Steps 7–9 verify drawer display and delete via UI (Test Cases 3–5)
- Steps 10–11 restore via undo (Test Case 6)

**Teardown**:

```typescript
test.afterEach(async ({ page }) => {
  await clearTestData(page);
});
```

---

## Test Data Lifecycle

1. **Setup**: Use factory functions to create 2 Classes, 1 PropertyDefinition via API (fast, deterministic)
2. **Test Execution**: Follow the UI interactions in Test Cases 1–6 above
3. **Verification**: Assert UI state changes match expected behavior (visibility, table updates, undo action)
4. **Cleanup**: Call `clearTestData(page)` in `test.afterEach()` to remove all test data

---

## Notes for Generator

- Test should use TanStack Router for navigation (e.g., `page.goto("/app/relationships")`)
- Use Playwright's `expect()` for assertions, not manual checks
- Use `page.locator('[data-testid="..."]')` for selector-based navigation
- For pattern-based selectors like `schema-row-*`, use `page.locator('[data-testid^="schema-row-"]')` with appropriate ID filtering
- For validation error verification in Test Case 1, assert that error elements become visible after failed submit, not specific error text
- For undo in Test Case 6, wait for the relationship row to reappear by asserting `expect(page.locator('[data-testid="schema-table"]')).toContainText(...)` before verifying ID matches
- Capture the deleted relationship ID and restored relationship ID to verify they are different (print both for debugging)
- In Test Case 4, verify that cancel button closes dialog by checking `expect(relationship-delete-confirm).not.toBeVisible()`
- In Test Case 5, use `page.waitForLoadState("networkidle")` after deletion to allow the table to refetch and update
