# Test Plan: Concept Scheme CRUD Operations

## Overview

This test validates the complete CRUD (Create, Read, Update, Delete) lifecycle for Concept Schemes, covering creation via modal form, viewing and editing in a detail drawer with autosave, and deletion with undo restoration. The test exercises the core workflows of concept scheme management: creation, field verification, in-drawer editing with autosave indicators, deletion with confirmation, and undo restoration within the 8-second window.

## Scope

- **Entities involved**: ConceptScheme (requires parent Taxonomy)
- **Pages involved**: `/app/schema/schemes/` (schemes list page with detail drawer)
- **External dependencies**: Back-end API, parent Taxonomy required
- **API endpoints**:
  - `POST /api/taxonomies/{taxonomy_id}/schemes` (create scheme)
  - `GET /api/schemes` (list schemes)
  - `GET /api/schemes/{scheme_id}` (read scheme)
  - `PUT /api/schemes/{scheme_id}` (update scheme)
  - `DELETE /api/schemes/{scheme_id}` (delete scheme)

## Test Cases

### Test Case 1: Create a Concept Scheme via Modal

**Preconditions**:
- Parent Taxonomy exists (created via factory)
- User is logged in and navigated to `/app/schema/schemes/`

**Steps**:

1. Click "Add Scheme" button with selector `scheme-add-button`
2. Create modal opens with selector `scheme-create-modal`
3. Locate form with selector `scheme-form`
4. Fill in title field (selector `scheme-title-input`) with "Test Concept Scheme"
5. Fill in description field (selector `scheme-description-input`) with "A test scheme for CRUD operations"
6. Click submit button with selector `scheme-submit-button`
7. Modal closes automatically and success toast appears

**Expected Result**:

- Concept Scheme is created and appears in the list on `/app/schema/schemes/`
- Scheme has `id`, `title`, `description`, `taxonomy_id`, and `version=1`
- Scheme is visible in the schema table with `data-testid="schema-row-{schemeId}"`
- Success toast confirms creation with the scheme ID

**Selectors Used**: `scheme-add-button`, `scheme-create-modal`, `scheme-form`, `scheme-title-input`, `scheme-description-input`, `scheme-submit-button`, `schema-table`, `schema-row-*`

**Invariants Verified**:

- ConceptScheme `title` is required and non-empty
- ConceptScheme `taxonomy_id` is automatically set to the first available taxonomy
- ConceptScheme `version` starts at 1
- ConceptScheme `status` defaults to "draft"
- Timestamps (`created_at`, `last_modified`) are set correctly

---

### Test Case 2: Click Row to Open Detail Drawer and Verify Field Values

**Preconditions**:

- Concept Scheme created in Test Case 1 (factory-created `scheme_id`)
- User is on `/app/schema/schemes/` list page
- Scheme is visible in the table

**Steps**:

1. Locate the scheme row in the schema table using `schema-row-{schemeId}`
2. Click the scheme name cell (clickable with selector `scheme-name-{schemeId}`) to select it
3. Detail drawer opens on the right side with selector `scheme-drawer`
4. Verify drawer title matches the scheme title
5. Verify read-only ID field (selector `scheme-drawer-id`) displays the correct scheme ID
6. Verify editable title field (selector `scheme-drawer-title-input`) displays "Test Concept Scheme"
7. Verify editable description field (selector `scheme-drawer-description-input`) displays "A test scheme for CRUD operations"
8. Verify read-only parent taxonomy field (selector `scheme-drawer-parent-taxonomy`) displays the parent taxonomy name

**Expected Result**:

- Drawer opens with correct scheme data
- All fields display the correct values
- Title and description fields are editable (not disabled)
- ID and parent taxonomy fields are read-only (disabled)
- Drawer uses `SchemaPageLayout` container with selector `schema-page-layout`

**Selectors Used**: `schema-row-*`, `scheme-name-*`, `schema-page-layout`, `scheme-drawer`, `scheme-drawer-id`, `scheme-drawer-title-input`, `scheme-drawer-description-input`, `scheme-drawer-parent-taxonomy`

**Invariants Verified**:

- Drawer renders when a row is selected
- All entity fields from the API response are displayed
- Read-only fields (ID, parent taxonomy) are properly disabled
- Editable fields are ready for input

---

### Test Case 3: Edit a Field in the Drawer and Verify Autosave Indicator Appears

**Preconditions**:

- Detail drawer is open with the scheme created in Test Case 1
- Scheme data is visible in all fields

**Steps**:

1. Locate the title input field (selector `scheme-drawer-title-input`)
2. Clear the current value and type a new title: "Updated Test Scheme"
3. Observe the autosave indicator (selector `drawer-autosave-status`) in the drawer header
4. Verify the indicator transitions through states: "saving" → "saved"
5. Wait for the autosave to complete (UI should show "saved" state briefly)
6. Close the drawer or navigate away to verify the change persisted

**Expected Result**:

- Title field updates immediately on input
- Autosave indicator appears and shows "saving" state
- Backend receives PUT request with updated title
- Autosave indicator transitions to "saved" state
- Title persists after close/reopen (verified in next step or by reopening drawer)

**Selectors Used**: `scheme-drawer-title-input`, `drawer-autosave-status`, `scheme-drawer`

**Invariants Verified**:

- Autosave triggers automatically after field edit (not on blur, not on explicit save)
- Autosave status indicator is visible and updates to reflect state
- No manual save button is required (autosave is automatic)
- Field changes persist on the backend

---

### Test Case 4: Delete the Scheme via Kebab Menu and Confirm Deletion

**Preconditions**:

- Scheme from Test Case 1 is visible in the table
- Scheme detail drawer may be open or closed

**Steps**:

1. If drawer is not open, locate the scheme row and click to open the drawer (selector `scheme-row-*` or `scheme-name-*`)
2. In the drawer header, locate the delete button (selector `drawer-delete-button`)
3. Click the delete button
4. Confirmation dialog appears with selector `scheme-delete-confirm`
5. Dialog displays the warning message
6. Click the confirm button (selector `confirm-dialog-confirm`) to proceed with deletion
7. Dialog closes and the scheme is deleted

**Expected Result**:

- Confirmation dialog appears with appropriate warning
- Scheme is soft-deleted from the database
- Drawer closes automatically
- Scheme is removed from the visible list on `/app/schema/schemes/`
- Toast notification appears with "Undo" action (selector `toast-action-*`)

**Selectors Used**: `scheme-drawer`, `drawer-delete-button`, `scheme-delete-confirm`, `confirm-dialog-confirm`, `toast-action-*`, `schema-row-*`

**Invariants Verified**:

- Soft delete behavior (entity marked as deleted, not physically removed)
- Confirmation dialog requires explicit confirmation before deletion
- Toast with undo action appears immediately after deletion
- Undo action is available for 8 seconds

---

### Test Case 5: Click Undo to Restore the Deleted Scheme

**Preconditions**:

- Scheme was just deleted in Test Case 4
- Toast notification with "Undo" action is visible
- User has up to 8 seconds to click undo

**Steps**:

1. Locate the toast notification on the screen
2. Find the undo action button in the toast (selector `toast-action-*` with appropriate ID)
3. Click the undo action button immediately (within 8 seconds of deletion)
4. Toast closes
5. Wait for the page to update and the scheme to reappear in the table

**Expected Result**:

- Toast disappears after undo is clicked
- Undo operation is sent to the backend
- Deletion is reversed
- Backend generates a new UUID for the restored scheme (restoration is not a simple undelete)
- Scheme reappears in the schemes list with a new ID
- The restored scheme maintains the original title and description

**Selectors Used**: `toast-action-*`, `schema-table`, `schema-row-*`

**Invariants Verified**:

- Undo must complete within 8-second window
- Restored entity receives a new UUID (not the same as the deleted entity)
- Restored scheme is visible in the table again
- Original data (title, description) is preserved in the restoration
- No error messages appear

---

## Coverage Analysis

### CRUD Coverage

- **Create**: ✓ Test Case 1 covers creation via modal form with required and optional fields
- **Read**: ✓ Test Cases 2–3 cover reading scheme data in table and drawer
- **Update**: ✓ Test Case 3 covers autosave editing of title field in drawer
- **Delete**: ✓ Test Case 4 covers soft delete with confirmation dialog
- **Restore (Undo)**: ✓ Test Case 5 covers 8-second undo window restoration

### Edge Cases

- **Autosave timing**: Test Case 3 validates autosave indicator behavior
- **Soft delete with confirmation**: Test Case 4 validates confirmation before deletion
- **Undo window constraint**: Test Case 5 validates 8-second undo window
- **UUID restoration**: Test Case 5 validates that restored schemes receive new UUIDs
- **Drawer lifecycle**: Test Cases 2–5 validate drawer open/close/update behavior

### Anti-Pattern Validations

- ✓ No `waitForTimeout()` without conditions (use `expect(selector).toBeVisible()` or `expect(selector).toHaveText()`)
- ✓ No hardcoded UUIDs (factory-created IDs only)
- ✓ No invented selectors (all selectors verified in `ux/selector-registry.yaml`)
- ✓ No vacuous assertions (every assertion validates meaningful behavior)
- ✓ No text-based selectors for mutable content (use `data-testid` and pattern-based selectors like `schema-row-*`)
- ✓ Cleanup handled via `clearTestData` in `afterEach`

---

## Open Questions

None. All required selectors are documented in `ux/selector-registry.yaml`:

- ✓ `scheme-add-button` — Create scheme button
- ✓ `scheme-create-modal` — Creation modal
- ✓ `scheme-form` — Create form container
- ✓ `scheme-title-input` — Title input in create form
- ✓ `scheme-description-input` — Description textarea in create form
- ✓ `scheme-submit-button` — Submit button in create form
- ✓ `schema-page-layout` — Split-pane layout with table and drawer
- ✓ `schema-table` — Main table container
- ✓ `schema-row-*` — Table row with dynamic ID suffix
- ✓ `scheme-name-*` — Clickable scheme name cell (pattern matches `scheme-name-{schemeId}`)
- ✓ `scheme-drawer` — Detail drawer container
- ✓ `scheme-drawer-id` — Read-only ID field in drawer
- ✓ `scheme-drawer-title-input` — Editable title field in drawer
- ✓ `scheme-drawer-description-input` — Editable description field in drawer
- ✓ `scheme-drawer-parent-taxonomy` — Read-only parent taxonomy field in drawer
- ✓ `drawer-autosave-status` — Autosave status indicator
- ✓ `drawer-delete-button` — Delete button in drawer
- ✓ `scheme-delete-confirm` — Confirmation dialog for deletion
- ✓ `confirm-dialog-confirm` — Confirm button in dialog
- ✓ `toast-action-*` — Undo action in toast (pattern matches dynamic ID)

---

## Factory Usage

This plan uses factory patterns for setup and teardown:

**Setup**: Create test data via factories (faster than UI):

```typescript
const taxonomy = await createTaxonomy(page, {
  title: "Test Taxonomy for Scheme CRUD",
  description: "Parent taxonomy for concept scheme tests",
});

const scheme = await createConceptScheme(page, taxonomy.id, {
  title: "Test Concept Scheme",
  description: "A test scheme for CRUD operations",
});
```

**Teardown**: Use `clearTestData(page)` in `test.afterEach()`:

```typescript
test.afterEach(async ({ page }) => {
  await clearTestData(page);
});
```

---

## Test Data Lifecycle

1. **Setup**: Use factory functions to create parent Taxonomy and ConceptScheme via API (fast, deterministic)
2. **Test Execution**: Follow the UI interactions in steps 1–5 above
3. **Verification**: Assert UI state changes match expected behavior (visibility, field values, autosave states, table updates)
4. **Cleanup**: Call `clearTestData(page)` in `test.afterEach()` to remove all test data

---

## Notes for Generator

- Test should use TanStack Router for navigation (e.g., `page.goto("/app/schema/schemes/")`)
- Use Playwright's `expect()` for assertions
- Use `page.locator('[data-testid="..."]')` for selector-based navigation
- For pattern-based selectors like `schema-row-*`, use `page.locator('[data-testid^="schema-row-"]').first()` to find rows
- For finding by ID suffix like `scheme-name-{schemeId}`, construct the selector dynamically: `page.locator(`[data-testid="scheme-name-${schemeId}"]`)`
- Wait for autosave completion using `expect(drawer.locator('[data-testid="drawer-autosave-status"]')).toContainText("saved")`
- Capture the restored scheme ID from the table after undo to verify it's a new UUID
- Use `waitForLoadState()` after deletion/undo to ensure UI updates complete
- Assert drawer visibility using `expect(page.locator('[data-testid="schema-page-layout"]')).toBeVisible()`
