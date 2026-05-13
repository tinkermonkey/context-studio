# Test Plan: Taxonomy CRUD Operations

## Overview

This test validates the complete CRUD operations for Taxonomy entities, covering the full lifecycle: create, read, update, and delete (with undo restoration). The test exercises both modal-based creation, drawer-based editing with autosave, and soft-delete with undo functionality to ensure all core taxonomy workflows are covered.

## Scope

- **Entities involved**: Taxonomy
- **Pages involved**: `/app/schema/taxonomies` (taxonomy list page)
- **External dependencies**: Back-end API (no external services required)
- **API endpoints**:
  - `POST /api/taxonomies` (create)
  - `GET /api/taxonomies` (read/list)
  - `PUT /api/taxonomies/{taxonomy_id}` (update)
  - `DELETE /api/taxonomies/{taxonomy_id}` (soft delete)
  - Undo/restore via version control system

## Test Cases

### Test Case 1: Create a Taxonomy via Modal

**Preconditions**: User is logged in and navigated to `/app/schema/taxonomies`

**Steps**:

1. Click "Add" button with selector `taxonomy-add-button`
2. Modal opens with selector `taxonomy-create-modal`
3. Locate form with selector `taxonomy-form`
4. Fill in title field (selector `taxonomy-title-input`) with "E2E Test Taxonomy Create"
5. Fill in description field (selector `taxonomy-description-input`) with "Test taxonomy created via E2E test suite"
6. Click submit button with selector `taxonomy-submit-button`
7. Modal closes automatically

**Expected Result**:

- Modal closes after submission
- Taxonomy appears immediately in the list on `/app/schema/taxonomies` table
- Taxonomy row is visible with matching title
- Taxonomy row uses the pattern `schema-row-{taxonomyId}` where `{taxonomyId}` is the newly created ID
- Taxonomy has `id`, `title`, `description`, and `version=1`
- Timestamps (`created_at`, `last_modified`) are set

**Selectors Used**: `taxonomy-add-button`, `taxonomy-create-modal`, `taxonomy-form`, `taxonomy-title-input`, `taxonomy-description-input`, `taxonomy-submit-button`

**Invariants Verified**:

- Taxonomy `title` is required and non-empty
- Taxonomy `version` starts at 1
- Timestamps are automatically set by the backend
- Taxonomy is immediately visible in the list without page refresh

---

### Test Case 2: Open Detail Drawer and Verify Field Values

**Preconditions**:

- Taxonomy created in Test Case 1 (factory-created `taxonomy_id`)
- User is on `/app/schema/taxonomies` page
- Taxonomy row is visible in the table

**Steps**:

1. Locate the taxonomy row in the table using the row selector `schema-row-{taxonomyId}` (from Test Case 1)
2. Click the row to open the detail drawer
3. Drawer opens with selector `taxonomy-drawer`
4. Verify read-only ID field with selector `taxonomy-drawer-id` displays the correct `taxonomy_id`
5. Verify editable title field with selector `taxonomy-drawer-title-input` displays "E2E Test Taxonomy Create"
6. Verify editable description field with selector `taxonomy-drawer-description-input` displays "Test taxonomy created via E2E test suite"
7. Do NOT make any edits yet

**Expected Result**:

- Drawer opens on the right side of the page (split layout with table on left, drawer on right)
- Read-only ID field displays the taxonomy ID
- Title field shows "E2E Test Taxonomy Create"
- Description field shows "Test taxonomy created via E2E test suite"
- All field values match the values submitted in Test Case 1
- No autosave indicator is visible yet (no changes made)

**Selectors Used**: `taxonomy-drawer`, `taxonomy-drawer-id`, `taxonomy-drawer-title-input`, `taxonomy-drawer-description-input`

**Invariants Verified**:

- ID field is read-only (non-editable)
- Title and description fields are editable
- Drawer layout is split-pane (table + drawer, not stacked)
- Field values are correctly persisted

---

### Test Case 3: Edit a Field in the Drawer and Verify Autosave Indicator

**Preconditions**:

- Drawer opened in Test Case 2
- Taxonomy is displayed with all fields visible

**Steps**:

1. Locate the title field with selector `taxonomy-drawer-title-input`
2. Clear the current value (select all and delete or triple-click + type)
3. Type a new title: "E2E Test Taxonomy Updated"
4. Wait 500ms for autosave to trigger (form should fire `onChange` which initiates autosave)
5. Verify autosave indicator appears with selector `drawer-autosave-status`
6. Wait for autosave to complete (indicator should show "Saved" or disappear after 2-3 seconds)
7. Verify the title has been saved by checking the indicator state

**Expected Result**:

- Title field is updated to "E2E Test Taxonomy Updated"
- After typing, the autosave indicator appears with selector `drawer-autosave-status`
- The indicator briefly shows saving state, then completion state (e.g., "Saved", checkmark icon, or brief success message)
- The drawer remains open (no modal or interruption)
- The updated value persists in the field
- The updated value is reflected in the backend (verified by the autosave completing without error)

**Selectors Used**: `taxonomy-drawer-title-input`, `drawer-autosave-status`

**Invariants Verified**:

- Title field is editable
- Autosave triggers automatically without explicit "Save" button click
- Autosave indicator provides visual feedback to the user
- Field value persists after autosave completes
- No version conflict occurs (optimistic concurrency control succeeds)

---

### Test Case 4: Delete Taxonomy via Kebab Menu with Confirmation

**Preconditions**:

- Taxonomy created in Test Case 1 is displayed in the drawer
- User is viewing the taxonomy drawer
- Drawer is open on `/app/schema/taxonomies`

**Steps**:

1. Locate the delete button in the drawer with selector `drawer-delete-button`
2. Click the delete button
3. A confirmation dialog appears with selector `confirm-dialog`
4. Verify the dialog contains a message asking to confirm deletion
5. Click the "Confirm" button with selector `confirm-dialog-confirm` (or equivalent affirmative button)
6. Dialog closes
7. Wait for the deletion to complete and the drawer to close

**Expected Result**:

- Confirmation dialog appears with appropriate messaging
- User clicks confirm and the taxonomy is deleted
- Drawer closes automatically after successful deletion
- The deleted taxonomy no longer appears in the table list
- A toast notification appears with an undo action
- Toast displays with selector pattern `toast-action-*` for the undo button

**Selectors Used**: `drawer-delete-button`, `confirm-dialog`, `confirm-dialog-confirm`, `toast-action-*`

**Invariants Verified**:

- Delete action requires confirmation (prevents accidental deletion)
- Soft delete behavior (taxonomy is marked as deleted, not removed from database)
- Toast with undo action appears immediately after deletion
- Taxonomy is no longer visible in the list

---

### Test Case 5: Click Undo to Restore the Deleted Taxonomy

**Preconditions**:

- Taxonomy was just deleted in Test Case 4
- Toast with undo action is visible on screen
- User has up to 8 seconds to click undo (from the moment deletion completed)

**Steps**:

1. Locate the toast notification on the screen (appears at bottom or top, typically)
2. Find the undo action button in the toast using selector pattern `toast-action-*`
3. Click the undo action button
4. Toast closes
5. Wait for the page to refresh or the table to update
6. Verify the taxonomy reappears in the list

**Expected Result**:

- Toast disappears after clicking undo
- Undo operation is sent to the back-end
- Deletion is reversed
- Taxonomy reappears in the list on `/app/schema/taxonomies`
- The restored taxonomy is visible with the title "E2E Test Taxonomy Updated" (showing the edit from Test Case 3)
- The restored taxonomy may have a new `id` (fresh UUID), or the same `id` (depending on undo implementation)
- No error messages appear

**Selectors Used**: `toast-action-*`

**Invariants Verified**:

- Undo must complete within 8-second window
- Soft-deleted taxonomy is restored
- Restored taxonomy is visible in the table again
- All field values are preserved (title, description)
- No error messages appear

---

## Coverage Analysis

### CRUD Coverage

- **Create**: ✓ Test Case 1 — taxonomy created via modal form submission
- **Read**: ✓ Test Case 2 — taxonomy displayed in drawer and table
- **Update**: ✓ Test Case 3 — taxonomy title updated via drawer with autosave
- **Delete**: ✓ Test Case 4 — taxonomy soft-deleted via drawer delete button
- **Restore (Undo)**: ✓ Test Case 5 — deleted taxonomy restored via undo toast action

### Edge Cases

- **Autosave behavior**: Test Case 3 validates autosave indicator and completion
- **Soft delete confirmation**: Test Case 4 validates confirmation dialog before deletion
- **Undo window**: Test Case 5 validates 8-second undo window
- **Drawer lifecycle**: Test Cases 2–4 validate drawer open/close behavior
- **Field persistence**: Test Cases 2–3 validate field values persist across operations
- **Table visibility**: Test Cases 1, 4–5 validate table visibility after create, delete, and restore

### Anti-Pattern Validations

- ✓ No `waitForTimeout()` without conditions (use `expect(drawer-autosave-status).toBeVisible()` or similar)
- ✓ No hardcoded UUIDs (factory-created IDs only; new ID generated on restore if applicable)
- ✓ No invented selectors (all selectors verified in `selector-registry.yaml`)
- ✓ No vacuous assertions (every assertion validates meaningful behavior change)
- ✓ No text-based selectors for mutable content (use `data-testid` and pattern-based selectors)
- ✓ Cleanup handled via `clearTestData` in `afterEach`

---

## Open Questions

None. All required selectors are documented in `ux/selector-registry.yaml`:

- ✓ `taxonomy-add-button`
- ✓ `taxonomy-create-modal`
- ✓ `taxonomy-form`
- ✓ `taxonomy-title-input`
- ✓ `taxonomy-description-input`
- ✓ `taxonomy-submit-button`
- ✓ `taxonomy-drawer`
- ✓ `taxonomy-drawer-id`
- ✓ `taxonomy-drawer-title-input`
- ✓ `taxonomy-drawer-description-input`
- ✓ `drawer-autosave-status`
- ✓ `drawer-delete-button`
- ✓ `confirm-dialog`
- ✓ `confirm-dialog-confirm`
- ✓ `toast-action-*` (pattern-based, dynamic suffix)
- ✓ `schema-row-*` (pattern-based, dynamic suffix)

---

## Factory Usage

This plan uses minimal factory setup — the test primarily exercises the UI. Cleanup is handled via `clearTestData`:

- **Setup**: Test creates taxonomy via UI (no factory setup needed for this test)

- **Teardown**: Use `clearTestData(page)` in `test.afterEach()`:
  ```typescript
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });
  ```

---

## Test Data Lifecycle

1. **Setup**: Navigate to `/app/schema/taxonomies` (no factory setup needed)
2. **Test Execution**: Follow UI interactions in steps 1–5 above
3. **Verification**: Assert UI state changes match expected behavior
4. **Cleanup**: Call `clearTestData(page)` in `test.afterEach()` to remove all test data created during the test

---

## Notes for Generator

- Test should use TanStack Router for navigation (e.g., `page.goto("/app/schema/taxonomies")`)
- Use Playwright's `expect()` for assertions
- Use `page.locator('[data-testid="..."]')` for selector-based navigation
- For pattern-based selectors like `schema-row-*`, use `page.locator('[data-testid^="schema-row-"]')` or filter by visible row content
- For `schema-row-{taxonomyId}`, capture the `taxonomy_id` from the API response and use it to locate the exact row: `page.locator(`[data-testid="schema-row-${taxonomyId}"]`)`
- Autosave indicator may disappear or show "Saved" — wait for it to show completion before proceeding to next step
- Toast with undo should appear automatically; poll for its appearance with a reasonable timeout (e.g., 2 seconds)
- When clicking undo, wait for table to update before verifying restored taxonomy is visible
- Do not assume drawer closes immediately after delete; use `expect(drawer).not.toBeVisible()` or similar to verify
