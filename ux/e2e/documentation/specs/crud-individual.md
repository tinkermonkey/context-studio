# Test Plan: Individual CRUD Operations

## Overview

This test validates the complete end-to-end CRUD operations for Individual entities, covering creation via modal form, verification in table, opening and editing via detail drawer with autosave feedback, deletion with confirmation, and restoration via the undo toast action.

## Scope

- **Entities involved**: Individual, Class
- **Pages involved**: `/app/data/individuals`
- **External dependencies**: Back-end API (no external services required)
- **API endpoints**:
  - `GET /api/classes` (read available classes)
  - `POST /api/individuals` (create individual)
  - `GET /api/individuals` (read individuals)
  - `GET /api/individuals/{individual_id}` (read individual detail)
  - `PATCH /api/individuals/{individual_id}` (update individual)
  - `DELETE /api/individuals/{individual_id}` (soft delete individual)

## Test Cases

### Test Case 1: Create Individual via Modal Form

**Preconditions**:

- User is logged in and navigated to `/app/data/individuals`
- At least one Class exists (created via factory)

**Steps**:

1. Click "Add Individual" button with selector `individual-add-button`
2. Modal opens with selector `individual-create-modal`
3. Locate form with selector `individual-form`
4. Fill in title field (selector `individual-title-input`) with "Test Individual"
5. Click class select input (selector `individual-class-select`)
6. Select a class from the dropdown (selector pattern `individual-class-option-{classId}`)
7. Verify the selected class appears as a chip
8. Fill in description field (selector `individual-description-input`) with "A test individual instance"
9. Click submit button with selector `individual-submit-button`
10. Modal closes automatically

**Expected Result**:

- Individual appears in the table on `/app/data/individuals`
- Individual has `id`, `title`, `description`, `class_ids` (containing selected class)
- Individual row selector follows pattern `individual-name-{id}`
- Table is refreshed and new individual is visible
- Autosave status shows "saved" state

**Selectors Used**: `individual-add-button`, `individual-create-modal`, `individual-form`, `individual-title-input`, `individual-class-select`, `individual-class-option-*` (pattern), `individual-description-input`, `individual-submit-button`, `individual-name-*` (pattern)

**Invariants Verified**:

- Individual `title` is required and non-empty
- Individual `class_ids` must contain at least one Class ID
- Individual is assigned a unique UUID
- Individual `created_at` is set to current timestamp

---

### Test Case 2: Verify Individual in Table and Click to Open Drawer

**Preconditions**:

- Individual created in Test Case 1 (factory-created `individual_id`)
- User is on `/app/data/individuals` page

**Steps**:

1. Locate the newly created individual in the table by title (e.g., "Test Individual")
2. Verify the row is visible with selector pattern `individual-name-{individualId}`
3. Verify class chip appears in the row with selector pattern `individual-class-chip-{classId}`
4. Click on the individual row (anywhere on the row or the name cell)
5. Detail drawer opens on the right side with selector `individual-detail-page`
6. Drawer title displays the individual's title ("Test Individual")

**Expected Result**:

- Individual row is visible and properly formatted in the table
- Class chip displays the selected class name
- Drawer opens when row is clicked
- Drawer has `schema-page-layout` parent container (split-pane layout)
- Drawer displays read-only ID field with selector `individual-drawer-id`
- All drawer form fields are visible and populated with current values

**Selectors Used**: `individual-name-*` (pattern), `individual-class-chip-*` (pattern), `individual-detail-page`, `individual-drawer-id`, `schema-page-layout`

**Invariants Verified**:

- Table uses split-pane layout with `schema-page-layout`
- Individual ID in drawer matches the factory-created ID
- Drawer displays all entity fields in correct state (read-only or editable)

---

### Test Case 3: Edit Individual Field in Drawer and Verify Autosave Indicator

**Preconditions**:

- Individual detail drawer is open (from Test Case 2)
- Individual is created and displayed with initial values

**Steps**:

1. Locate the name input field in drawer with selector `individual-drawer-name-input`
2. Clear the field and type a new name (e.g., "Updated Test Individual")
3. Verify the field value changes on screen (onChange event fires)
4. Wait for autosave to trigger (typically 1–2 seconds after edit)
5. Observe autosave status indicator with selector `drawer-autosave-status`
6. Verify the status shows "saving" then transitions to "saved"
7. Confirm the save icon or text displays without errors

**Expected Result**:

- Field value updates immediately when typing (onChange behavior)
- Autosave status indicator appears and shows "saving" briefly
- Status indicator transitions to "saved" after API responds successfully
- No error message appears
- Back-end receives PATCH request with updated `title`
- Drawer remains open and editable state is preserved

**Selectors Used**: `individual-drawer-name-input`, `drawer-autosave-status`

**Invariants Verified**:

- Autosave is triggered after user stops typing (not before)
- Autosave status reflects the correct state (saving → saved)
- Edit is persisted to the back-end database
- Drawer does not close after successful autosave
- Multiple edits trigger multiple autosave cycles correctly

---

### Test Case 4: Delete Individual via Kebab Menu and Confirm Deletion

**Preconditions**:

- Individual is visible in the table on `/app/data/individuals`
- Drawer may be open or closed
- Individual exists in the database

**Steps**:

1. Locate the individual row in the table by the factory-created ID
2. Click the delete button for that row (selector pattern `individual-row-delete-{individualId}`)
3. A confirmation dialog appears with selector `confirm-dialog`
4. Verify dialog text mentions the individual's title
5. Click the confirm button with selector `confirm-dialog-confirm`
6. Dialog closes
7. Table updates and the individual row disappears from the visible list

**Expected Result**:

- Individual is soft-deleted (marked as deleted in the database)
- Individual no longer appears in the individuals table
- Toast notification appears at the bottom of the screen with selector pattern `toast-action-*`
- Toast contains an "Undo" action button
- Undo button has selector pattern `toast-action-*` (matches toast-action-{id})
- The individual can be restored within an 8-second window

**Selectors Used**: `individual-row-delete-*` (pattern), `confirm-dialog`, `confirm-dialog-confirm`, `toast-action-*` (pattern)

**Invariants Verified**:

- Soft delete behavior (entity is not removed from database, just marked as deleted)
- Confirmation dialog appears before deletion is committed
- Toast with undo action appears immediately after deletion
- Individual disappears from the table view after deletion
- Toast action button is clickable within the 8-second window

---

### Test Case 5: Click Undo Toast Action to Restore Individual

**Preconditions**:

- Individual was just soft-deleted in Test Case 4
- Toast with undo action is visible
- User has up to 8 seconds to click undo

**Steps**:

1. Locate the toast notification on the screen (typically at the bottom)
2. Verify the toast contains an "Undo" action button with selector pattern `toast-action-*`
3. Click the undo action button immediately (within 8 seconds of deletion)
4. Toast closes
5. Wait for the page to refresh or the table to update
6. Verify the individual reappears in the table with the same or similar properties

**Expected Result**:

- Toast disappears
- Undo operation is sent to the back-end
- Deletion is reversed
- Individual reappears in the individuals table
- Restored individual displays the same title and description as before deletion
- The individual retains its class membership
- No error messages appear

**Selectors Used**: `toast-action-*` (pattern)

**Invariants Verified**:

- Undo must complete within 8-second window
- Restored individual is visible in the table again
- Restored individual data matches the original (title, description, class_ids)
- No error messages appear after undo
- Table is properly refreshed to show the restored entity

---

## Coverage Analysis

### CRUD Coverage

- **Create**: ✓ Test Case 1 covers Individual creation via modal form with required fields (title, class_ids)
- **Read**: ✓ Test Case 2 covers reading Individual from table and opening detail drawer
- **Update**: ✓ Test Case 3 covers field editing with autosave indicator feedback
- **Delete**: ✓ Test Case 4 covers soft delete with confirmation dialog
- **Restore (Undo)**: ✓ Test Case 5 covers 8-second undo window with toast action

### Edge Cases

- **Autosave timing**: Test Case 3 validates that autosave triggers after user pauses typing, not during
- **Confirmation before deletion**: Test Case 4 validates the confirmation dialog gate
- **Undo window**: Test Case 5 validates the 8-second undo window
- **Table refresh after delete/restore**: Tests verify table visibility updates match deletion and restoration
- **Class membership**: Tests verify class_ids are retained through all operations

### Anti-Pattern Validations

- ✓ No `waitForTimeout()` without conditions (use `expect(selector).toBeVisible()` or `waitForLoadState()`)
- ✓ No hardcoded UUIDs (factory-created IDs and generated IDs only)
- ✓ No invented selectors (all selectors verified in `selector-registry.yaml`)
- ✓ No vacuous assertions (every assertion validates meaningful behavior)
- ✓ No text-based selectors for mutable content (use `data-testid` and pattern-based selectors like `individual-name-*`)
- ✓ Cleanup handled via `clearTestData` in `afterEach`
- ✓ Form validation errors clear on `onChange`, not only on `onBlur`
- ✓ Autosave status is observable and asserted (not just time-based waiting)

---

## Open Questions

None. All required selectors are documented in `ux/selector-registry.yaml`:

- ✓ `individual-add-button`, `individual-create-modal`, `individual-form`
- ✓ `individual-title-input`, `individual-class-select`, `individual-class-option-*`
- ✓ `individual-description-input`, `individual-submit-button`
- ✓ `individual-name-*` (pattern-based, dynamic suffix)
- ✓ `individual-class-chip-*` (pattern-based, dynamic suffix)
- ✓ `individual-detail-page`, `individual-drawer-id`, `individual-drawer-name-input`, `individual-drawer-description-input`
- ✓ `individual-row-delete-*` (pattern-based, dynamic suffix)
- ✓ `drawer-autosave-status`
- ✓ `confirm-dialog`, `confirm-dialog-confirm`
- ✓ `toast-action-*` (pattern-based, dynamic suffix)
- ✓ `schema-page-layout` (parent container for split-pane layout)

---

## Factory Usage

This plan uses factory patterns for setup and teardown:

### Setup

Create test data via factories (faster than UI):

```typescript
// Create required class first
const scheme = await createConceptScheme(page);
const testClass = await createClass(page, scheme.id, {
  title: "Test Class for Individual",
  description: "A class for testing Individual CRUD",
});

// Individual is created via UI in Test Case 1, not via factory
// (since the test flow specifically requires creation via the modal form)
```

### Teardown

Use `clearTestData(page)` in `test.afterEach()` at the describe level:

```typescript
test.afterEach(async ({ page }) => {
  await clearTestData(page);
});
```

---

## Test Data Lifecycle

1. **Setup**: Use factory functions to create Class via API (fast, deterministic). Create Individual via UI form in Test Case 1.
2. **Test Execution**: Follow the UI interactions in steps 1–5 above
3. **Verification**: Assert UI state changes match expected behavior (visibility, form values, table updates, toast appearance)
4. **Cleanup**: Call `clearTestData(page)` in `test.afterEach()` to remove all test data

---

## Notes for Generator

- Test should use TanStack Router for navigation (e.g., `page.goto("/app/data/individuals")`)
- Use Playwright's `expect()` for assertions, not manual checks
- Use `page.locator('[data-testid="..."]')` for selector-based navigation
- For pattern-based selectors like `individual-name-*`, use `page.locator('[data-testid^="individual-name-"]')` or similar
- Wait for autosave status using `expect(page.locator('[data-testid="drawer-autosave-status"]')).toContainText("saved")`
- Wait for table updates after delete/restore using `expect(page.locator('[data-testid^="individual-name-"]')).toContainText(...)`
- Capture the individual ID from the created entity for use in subsequent test cases
- Verify toast action button exists before clicking it to ensure the undo window is still active
- Assertion on drawer layout: verify `container.querySelector('[data-testid="schema-page-layout"]')` is present when row is selected
- Form validation error clearing must assert `expect(screen.queryByText("...error...")).not.toBeInTheDocument()` after value change
