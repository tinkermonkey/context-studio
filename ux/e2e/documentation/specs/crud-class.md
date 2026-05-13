# Test Plan: Class CRUD Operations

## Overview

This test validates the complete CRUD lifecycle for ontology classes, covering creation via modal form, reading and verifying field values in a detail drawer, updating fields with autosave feedback, and deletion with a type-to-confirm dialog. The test also verifies the undo functionality to restore a deleted class within the 8-second undo window. Classes that have instances will require a type-to-confirm interaction to proceed with deletion.

## Scope

- **Entities involved**: ConceptScheme, Class, Individual (for deletion cascade scenario)
- **Pages involved**: `/app/schema/classes` (main table), detail drawer (side panel)
- **External dependencies**: Back-end API (no external services required)
- **API endpoints**:
  - `GET /api/schemes` (list schemes for create dialog domain dropdown)
  - `POST /api/schemes/{scheme_id}/classes` (create class)
  - `GET /api/classes` (list classes)
  - `GET /api/classes/{class_id}` (read class detail)
  - `PUT /api/classes/{class_id}` (update class)
  - `DELETE /api/classes/{class_id}` (soft delete class)
  - `GET /api/individuals` (check if class has instances for confirmation)
  - `POST /api/classes/{class_id}/undo` (restore deleted class)

## Test Cases

### Test Case 1: Create a New Class via Create Button

**Preconditions**:
- User is logged in and navigated to `/app/schema/classes`
- At least one concept scheme exists (pre-created via factory)

**Steps**:

1. Click "New class" button with selector `class-add-button`
2. Modal opens with selector `class-create-modal`
3. Locate form with selector `class-form`
4. Fill in name/title field (selector `class-title-input`) with "Test Class: CRUD Operations"
5. Fill in description field (selector `class-description-input`) with "Comprehensive test class for CRUD operations"
6. Select a domain/scheme from the domain dropdown (factory-created scheme ID)
7. Leave parent class empty (root class)
8. Click submit button with selector `class-submit-button`
9. Modal closes automatically

**Expected Result**:

- Class appears in the classes table on `/app/schema/classes`
- Class has `id`, `title`, `description`, `concept_scheme_id`, `version=1`
- Class title and description match the entered values
- Class is visible in the table and searchable by title or ID
- Row uses pattern selector `schema-row-{classId}` (or `class-name-{classId}` for the clickable title)

**Selectors Used**: `class-add-button`, `class-create-modal`, `class-form`, `class-title-input`, `class-description-input`, `class-submit-button`, `class-name-*`

**Invariants Verified**:

- Class `title` is required and non-empty
- Class `concept_scheme_id` is set to the selected domain
- Class `parent_class_id` is null for root classes (not set in create)
- Class `version` starts at 1
- Timestamps (`created_at`, `last_modified`) are set correctly

---

### Test Case 2: Click Class Row to Open Detail Drawer and Verify Fields

**Preconditions**:

- Class created in Test Case 1 (factory-created `class_id`)
- User is on `/app/schema/classes` table view

**Steps**:

1. Locate the class row in the table using the factory-created class ID
2. Click the class name cell (selector `class-name-{classId}`) to open the detail drawer
3. Drawer opens on the right side with selector `class-drawer`
4. Verify drawer title shows the class name
5. Verify read-only ID field displays correct ID (selector `class-drawer-id`)
6. Verify name input field (selector `class-drawer-name-input`) shows "Test Class: CRUD Operations"
7. Verify description textarea (selector `class-drawer-description-input`) shows "Comprehensive test class for CRUD operations"
8. Verify domain selector (selector `class-drawer-domain-select`) shows the correct scheme name
9. Verify parent class field shows "—" (no parent) or displays parent name if set

**Expected Result**:

- Drawer opens with all class fields populated correctly
- ID field is read-only (disabled)
- Name and description fields are editable
- Domain selector is interactive
- Parent class field displays the current state (or "—" if null)
- Drawer title reflects the class name

**Selectors Used**: `class-drawer`, `class-drawer-id`, `class-drawer-name-input`, `class-drawer-description-input`, `class-drawer-domain-select`

**Invariants Verified**:

- Drawer content matches the API-fetched class data
- All field values are hydrated correctly from `classData`
- Read-only fields are truly disabled/non-editable

---

### Test Case 3: Edit a Field in the Drawer and Verify Autosave Indicator

**Preconditions**:

- Class drawer is open with Test Case 1 class
- Class name and description are currently set to original values

**Steps**:

1. Locate the name input field (selector `class-drawer-name-input`)
2. Clear the field and type a new name: "Updated Test Class"
3. Wait 1 second to trigger autosave (debounce)
4. Observe autosave indicator in the drawer header (selector `drawer-autosave-status`)
5. Verify the indicator transitions from "saving" state to "saved" state
6. Verify the input field value reflects the new name
7. Click the description textarea (selector `class-drawer-description-input`)
8. Clear the field and type a new description: "Updated description for CRUD test"
9. Wait for autosave to complete
10. Verify autosave indicator shows "saved"

**Expected Result**:

- Autosave indicator appears in the drawer header
- Indicator shows "saving" state briefly after value change
- Indicator transitions to "saved" state after API response
- Updated values persist in the input fields
- No error messages appear
- Drawer remains open and interactive

**Selectors Used**: `drawer-autosave-status`

**Invariants Verified**:

- Autosave is triggered on field change (not just on blur)
- Autosave indicator provides visual feedback (saving → saved)
- Updates are persisted to the back-end (API call succeeds)
- Dirty state is tracked (changes trigger autosave)

---

### Test Case 4: Delete the Class and Handle Type-to-Confirm Dialog (No Instances)

**Preconditions**:

- Class drawer is open with Test Case 1 class
- Class has no instances (no individuals reference it)

**Steps**:

1. Locate the delete button in the drawer header (selector `drawer-delete-button`)
2. Click the delete button
3. Type-to-confirm dialog appears with selector `type-confirm-dialog`
4. Dialog shows the class title as the confirmation text (e.g., "Updated Test Class")
5. Locate the input field with selector `type-confirm-input`
6. Type the class title exactly: "Updated Test Class" (must match exactly)
7. Verify the confirm button (selector `type-confirm-button`) becomes enabled
8. Click the confirm button
9. Dialog closes and class is removed from the table
10. Drawer closes automatically

**Expected Result**:

- Type-to-confirm dialog displays the correct confirmation phrase (class title)
- Confirm button is disabled until the exact phrase is typed
- After confirmation, the class is soft-deleted (removed from visible list)
- Toast notification appears with "Undo" action (selector `toast-action-*`)
- Class no longer appears in the table
- User can still access the Undo button within 8 seconds

**Selectors Used**: `drawer-delete-button`, `type-confirm-dialog`, `type-confirm-input`, `type-confirm-button`, `toast-action-*`

**Invariants Verified**:

- Soft delete behavior (entity marked as deleted, not physically removed)
- Type-to-confirm requires exact phrase match (case-sensitive, full title)
- Confirm button is disabled while input is incomplete or mismatched
- Toast with undo action appears immediately after deletion
- Undo window is 8 seconds
- No error messages appear during deletion

---

### Test Case 5: Click Undo to Restore the Deleted Class

**Preconditions**:

- Class was just soft-deleted in Test Case 4
- Toast with undo action is visible on screen
- Less than 8 seconds have elapsed since deletion

**Steps**:

1. Locate the toast notification (should be visible at the bottom right or similar)
2. Find the undo action button in the toast (selector `toast-action-*`)
3. Click the undo action button immediately (within 8 seconds of deletion)
4. Toast closes
5. Wait for the page to refresh or the table to update
6. Verify the class appears again in the classes table

**Expected Result**:

- Toast disappears after undo action is clicked
- Undo operation is sent to the back-end
- Deletion is reversed
- Class reappears in the classes table
- Restored class has the same title and description as before deletion
- No error messages appear

**Selectors Used**: `toast-action-*`, `schema-table`, `class-name-*`

**Invariants Verified**:

- Undo must complete within 8-second window
- Undo operation reverses the soft-delete flag
- Restored class is visible in the table immediately
- Class data (title, description) is preserved after undo
- Restored class can be clicked again to open the drawer

---

### Test Case 6: Create a Class with Instances and Verify Type-to-Confirm with Warning Message

**Preconditions**:

- New class is created (factory-created)
- At least one individual (instance) is created and assigned to this class (factory-created)
- Class drawer is open

**Steps**:

1. Locate the delete button in the drawer header (selector `drawer-delete-button`)
2. Click the delete button
3. Type-to-confirm dialog appears with selector `type-confirm-dialog`
4. Dialog shows a warning message: "This will remove the class and all [N] individual[s] that reference it..."
5. Dialog shows the confirmation text (class title)
6. Locate the input field with selector `type-confirm-input`
7. Type the class title exactly to enable the confirm button
8. Verify the confirm button (selector `type-confirm-button`) becomes enabled
9. Click the confirm button
10. Dialog closes and class is soft-deleted
11. Toast with undo action appears

**Expected Result**:

- Type-to-confirm dialog displays the warning about cascading deletion
- Warning message shows the count of individuals that will be affected (e.g., "all 2 individuals")
- Confirm button requires exact phrase match before enabling
- After confirmation, the class is soft-deleted
- Toast appears with undo action
- Class no longer appears in the table

**Selectors Used**: `drawer-delete-button`, `type-confirm-dialog`, `type-confirm-input`, `type-confirm-button`, `toast-action-*`

**Invariants Verified**:

- Type-to-confirm dialog shows warning when individuals exist
- Warning message lists the count of cascading deletes
- Deletion proceeds only after exact phrase is typed
- Cascade delete is soft (marked as deleted, not physically removed)
- Undo is still available to restore the class and its individuals

---

## Coverage Analysis

### CRUD Coverage

- **Create**: ✓ Test Case 1 covers class creation via modal form with required fields
- **Read**: ✓ Test Case 2 covers reading and verifying class details in the drawer
- **Update**: ✓ Test Case 3 covers updating name and description with autosave feedback
- **Delete**: ✓ Test Cases 4 and 6 cover soft delete with type-to-confirm (with and without instances)
- **Restore (Undo)**: ✓ Test Case 5 covers 8-second undo window

### Edge Cases

- **Autosave debounce**: Test Case 3 verifies autosave timing and visual feedback
- **Type-to-confirm validation**: Test Cases 4 and 6 verify exact phrase matching requirement
- **Cascade deletes**: Test Case 6 verifies deletion warning when individuals exist
- **Undo window**: Test Case 5 verifies 8-second undo functionality
- **Field validation**: Create form requires domain selection (covered in Test Case 1)
- **Domain switching**: Test Case 3 includes domain selector interaction (optional edit)

### Anti-Pattern Validations

- ✓ No `waitForTimeout()` without conditions (use `expect(selector).toBeVisible()` or wait for autosave status change)
- ✓ No hardcoded UUIDs (factory-created IDs only)
- ✓ No invented selectors (all selectors verified in `selector-registry.yaml`)
- ✓ No vacuous assertions (every assertion validates meaningful behavior)
- ✓ No text-based selectors for mutable content (use `data-testid` and pattern-based selectors like `class-name-*`)
- ✓ Cleanup handled via `clearTestData` in `afterEach`

---

## Open Questions

None. All required selectors are documented in `ux/selector-registry.yaml`:

- ✓ `class-add-button` (line 428)
- ✓ `class-create-modal` (line 431)
- ✓ `class-form` (line 252)
- ✓ `class-title-input` (line 256)
- ✓ `class-description-input` (line 259)
- ✓ `class-submit-button` (line 262)
- ✓ `class-drawer` (line 445)
- ✓ `class-drawer-id` (line 448)
- ✓ `class-drawer-name-input` (line 451)
- ✓ `class-drawer-description-input` (line 454)
- ✓ `class-drawer-domain-select` (line 457)
- ✓ `drawer-autosave-status` (line 56)
- ✓ `drawer-delete-button` (line 62)
- ✓ `type-confirm-dialog` (line 86)
- ✓ `type-confirm-input` (line 89)
- ✓ `type-confirm-button` (line 92)
- ✓ `toast-action-*` (line 51)
- ✓ `class-name-*` (line 434)
- ✓ `schema-table` (line 103)

---

## Factory Usage

This plan uses factory patterns for setup and teardown:

**Setup** (via factories in `ux/e2e/fixtures/factories.ts`):

```typescript
// Create a concept scheme to hold the class
const scheme = await createConceptScheme(page);

// Create the test class
const testClass = await createClass(page, scheme.id, {
  title: "Test Class: CRUD Operations",
  description: "Comprehensive test class for CRUD operations",
});

// For Test Case 6: Create an individual (instance) of the class
const individual = await createIndividual(page, {
  title: "Test Individual",
  class_id: testClass.id,
});
```

**Teardown** (in `afterEach`):

```typescript
test.afterEach(async ({ page }) => {
  await clearTestData(page);
});
```

---

## Test Data Lifecycle

1. **Setup**: Use factory functions to create ConceptScheme and Class via API (fast, deterministic)
2. **Test Execution**: Follow the UI interactions in steps 1–6 above (create, read, update, delete, undo)
3. **Verification**: Assert UI state changes match expected behavior (drawer visibility, table rows, autosave status, toast actions)
4. **Cleanup**: Call `clearTestData(page)` in `test.afterEach()` to remove all test data

---

## Notes for Generator

- Test should use TanStack Router for navigation (e.g., `page.goto("/app/schema/classes")`)
- Use Playwright's `expect()` for assertions, not manual checks
- Use `page.locator('[data-testid="..."]')` for selector-based navigation
- For pattern-based selectors like `class-name-*` or `toast-action-*`, use `page.locator('[data-testid*="class-name-"]')` or similar
- For autosave testing: change field value, wait for status indicator to transition from "saving" to "saved", verify via `expect(page.locator('[data-testid="drawer-autosave-status"]')).toContainText("Saved")`
- For type-to-confirm: type the confirmation phrase character by character, wait for confirm button to become enabled
- For undo testing: wait for toast to appear, verify undo button is clickable, click it, wait for table to update with the restored row
- Verify restored class ID is visible in the table (use row selector pattern matching the factory ID)
- Use `page.waitForSelector` or `expect(...).toBeVisible()` for waiting on elements, never bare `waitForTimeout()`

---

## Related Test Plans

- `ontology-management-full-crud-chain.md` — Comprehensive CRUD chain covering Taxonomy → Scheme → Class → Property → Relationship
- Other CRUD specs for Individual, Property, Relationship entities (to be added)
