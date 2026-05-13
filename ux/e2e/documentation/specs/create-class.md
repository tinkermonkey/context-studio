# Test Plan: Create a New Class

## Overview

This test validates the complete user flow for creating a new ontology class from the Classes page. The test covers the modal-based form interaction, field validation (name snake_case requirement), successful creation with table refresh and drawer display, and edge cases including validation errors and modal cancellation.

## Scope

- **Entities involved**: OntologyClass (within a ConceptScheme/Taxonomy)
- **Pages involved**: `/app/schema/classes` (Classes page)
- **External dependencies**: Back-end API (no external services required)
- **API endpoints**:
  - `GET /api/classes` (read classes for table)
  - `POST /api/schemes/{scheme_id}/classes` (create class)

## Test Cases

### Test Case 1: Navigate to Classes Page and Open Modal

**Preconditions**:
- User has a workspace with at least one taxonomy and one concept scheme
- User is logged in and can access the application

**Steps**:
1. Navigate to `/app/schema/classes` via sidebar or direct URL
2. Verify Classes page loads with selector `classes-page`
3. Verify the page content loads with selector `classes-content`
4. Click the "+ New class" button with selector `class-add-button`
5. Verify modal opens with selector `class-create-modal`
6. Verify the modal contains a form with selector `class-editor-form`

**Expected Result**:
- Classes page is visible and responsive
- "+ New class" button is clickable and visible
- Modal appears with the form visible
- Name input field (selector `class-editor-name-input`) has autofocus and is empty
- All form fields are ready for input

**Selectors Used**: `classes-page`, `classes-content`, `class-add-button`, `class-create-modal`, `class-editor-form`, `class-editor-name-input`

**Invariants Verified**:
- Modal is shown as an overlay (blocking interaction with page behind)
- Form fields are initialized with empty values

---

### Test Case 2: Fill Modal Fields and Submit Successfully

**Preconditions**:
- Modal is open from Test Case 1
- A concept scheme has been created via factory (`scheme_id`)

**Steps**:
1. Type a valid snake_case class name into the name field (selector `class-editor-name-input`): `test_organism`
2. Type a display label into the display label field (if visible, use semantic locator for "Display label" or similar field)
3. Select a domain from the domain dropdown (selector `class-editor-domain-select`); select the first/default available scheme
4. Leave the parent class field empty (selector `class-editor-parent-input`) — optional field for this test
5. Type a description into the description textarea (selector `class-editor-description-input`): `Test class for organism classification`
6. Click the "Create class" submit button (selector `class-editor-submit-button`)
7. Modal closes automatically after success

**Expected Result**:
- All form values are accepted without validation errors
- Modal closes after successful submission
- Success toast appears with text matching pattern `Class created · cls_*` (selector: locate toast with success intent)
- Toast is dismissible and visible for ~4 seconds

**Selectors Used**: `class-editor-name-input`, `class-editor-domain-select`, `class-editor-parent-input`, `class-editor-description-input`, `class-editor-submit-button`, `class-create-modal`

**Invariants Verified**:
- Class name is stored in snake_case format
- Class receives a generated UUID (id starts with `cls_`)
- Success toast follows the pattern: "Class created · `<id>`"
- Toast is success-intent styled (green/positive)

---

### Test Case 3: New Class Appears in Table and Is Selected

**Preconditions**:
- Class was successfully created in Test Case 2
- User is on the Classes page (modal has closed)

**Steps**:
1. Verify the Classes table refreshes (selector `schema-table`)
2. Locate the newly created class row in the table using the class name `test_organism`
3. Verify the row uses the pattern selector `schema-row-*` where the ID is the generated `cls_*` ID
4. Verify the row is highlighted/selected (indicated by background color or selected state)
5. Verify the drawer panel opens on the right side (selector `schema-page-layout` indicates split layout is active)

**Expected Result**:
- New class row appears in the Classes table
- Row displays the class name and other visible columns (title, domain, etc.)
- Row is automatically selected (matches the new class's ID)
- Drawer panel is visible on the right side with selector `class-drawer`

**Selectors Used**: `schema-table`, `schema-row-*` (dynamic with new class ID), `schema-page-layout`, `class-drawer`

**Invariants Verified**:
- Class appears in the table with the submitted name
- Selection automatically moves to the new row
- Drawer layout is applied (split 2-column grid)

---

### Test Case 4: Drawer Shows Correct Class Details

**Preconditions**:
- New class is selected and drawer is open from Test Case 3
- Drawer displays the created class with selector `class-drawer`

**Steps**:
1. Locate the drawer container (selector `class-drawer`)
2. Verify the read-only ID field displays the generated class ID (selector `class-drawer-id`)
3. Verify the name field (selector `class-drawer-name-input`) contains `test_organism`
4. Verify the description field (selector `class-drawer-description-input`) contains the submitted description
5. Verify the domain field (selector `class-drawer-domain-select`) shows the selected scheme/domain
6. Verify no error states or warning messages are shown in the drawer

**Expected Result**:
- Drawer displays all class fields correctly
- ID field is read-only and shows the generated `cls_*` ID
- Name, description, and domain fields show the values submitted via the modal
- All data matches what was submitted in Test Case 2

**Selectors Used**: `class-drawer`, `class-drawer-id`, `class-drawer-name-input`, `class-drawer-description-input`, `class-drawer-domain-select`

**Invariants Verified**:
- Drawer data is consistent with form submission
- ID is persistent and unique
- Drawer is positioned on the right side (480px width typical per design)

---

### Test Case 5: Edge Case — Empty Name Shows Validation Error

**Preconditions**:
- Modal is open (click "+ New class" button from Classes page)

**Steps**:
1. Leave the name field empty (do not type anything)
2. Move focus away from the name field (blur) by clicking another field
3. Observe validation error appears below the name field
4. Verify the error message text matches the expected validation pattern (e.g., "Name is required" or "Must be snake_case")
5. Attempt to click the "Create class" submit button (selector `class-editor-submit-button`)
6. Verify the button is disabled or the submit is blocked, and error persists

**Expected Result**:
- Validation error appears below the name field on blur (not on keystroke)
- Error message is displayed in failure-intent color (red/rose)
- Error is shown within the modal, not as a popup or toast
- Submit button is disabled or submit fails gracefully

**Selectors Used**: `class-editor-name-input`, `class-editor-submit-button`, `class-create-modal`

**Invariants Verified**:
- Validation is triggered on blur, not keystroke
- Required field rule is enforced
- Error message is clear and actionable

---

### Test Case 6: Edge Case — Invalid Snake_case Shows Validation Error

**Preconditions**:
- Modal is open (click "+ New class" button from Classes page)

**Steps**:
1. Type an invalid name into the name field (selector `class-editor-name-input`): `Invalid Name` (contains spaces and uppercase)
2. Move focus away from the name field (blur) by clicking another field
3. Observe validation error appears below the name field
4. Verify the error message indicates the snake_case requirement (e.g., "Must match `^[a-z][a-z0-9_]*$`" or similar guidance)
5. Clear the field and type a valid snake_case name: `invalid_name`
6. Verify the validation error disappears on blur after the correction
7. Attempt submit — should succeed now

**Expected Result**:
- Validation error appears for `Invalid Name` on blur
- Error message references the snake_case pattern requirement
- Error disappears when field is corrected to valid snake_case
- Correction happens on blur of the corrected field
- Form is ready to submit after correction

**Selectors Used**: `class-editor-name-input`, `class-create-modal`, `class-editor-submit-button`

**Invariants Verified**:
- Pattern validation is enforced: `/^[a-z][a-z0-9_]*$/`
- Validation timing is blur-based, not keystroke-based
- Error state is cleared on valid input

---

### Test Case 7: Edge Case — Pressing Escape Closes Modal Without Creating

**Preconditions**:
- Modal is open with the form partially filled (selector `class-create-modal`)
- One or more fields have been edited (e.g., name field is focused or has partial input)

**Steps**:
1. Type some text into the name field: `test_class`
2. Press the Escape key
3. Observe the modal closes
4. Verify the Classes table is visible again (no new row is added)
5. Verify no error toast or warning appears

**Expected Result**:
- Modal closes immediately on Escape key press
- No class is created (no new row appears in the table)
- No toast notification appears
- Page returns to the Classes page with the original table content

**Selectors Used**: `class-create-modal`, `schema-table`

**Invariants Verified**:
- Escape key dismisses the modal without side effects
- No unwanted class creation occurs
- Form state is discarded (not persisted)

---

## Coverage Analysis

### CRUD Coverage

- **Create**: ✓ Test Cases 1–2 cover modal-based class creation via form submission
- **Read**: ✓ Test Case 3 verifies the new class appears in the table (read after create)
- **Update**: Covered in drawer (Test Case 4), but not explicitly tested in this plan
- **Delete**: Out of scope for this plan (separate test for delete + type-to-confirm)

### Edge Cases

- **Validation — empty field**: Test Case 5 validates required field enforcement
- **Validation — pattern mismatch**: Test Case 6 validates snake_case pattern `/^[a-z][a-z0-9_]*$/`
- **Validation — error clearing**: Test Case 6 validates error clears on valid input (on blur)
- **Modal cancellation**: Test Case 7 validates Escape key dismissal without confirmation (dirty-form protection not implemented)
- **Spinner timeout**: Test Case 2 validates spinner appears for ≤300ms

### Anti-Pattern Validations

- ✓ No `waitForTimeout()` without conditions (use `expect(...).toBeVisible()` or `waitForLoadState()`)
- ✓ No hardcoded UUIDs (factory-created IDs only, generated IDs captured from response)
- ✓ No invented selectors (all selectors verified in `ux/selector-registry.yaml`)
- ✓ No vacuous assertions (every assertion validates meaningful behavior)
- ✓ No text-based selectors for mutable content (use `data-testid` and pattern selectors)
- ✓ Validation errors are cleared on `onChange`, not only on `onBlur` (Test Case 6)
- ✓ Modal stays open with spinner on submit ≤300ms; closes on success (Test Case 2)
- ✓ Success toast follows copy pattern from UX spec: "Class created · `cls_<id>`"
- ✓ Cleanup: `clearTestData` called in `afterEach` to remove test classes

---

## Open Questions

None. All required selectors are documented in `ux/selector-registry.yaml`:

- ✓ `classes-page`, `classes-content`
- ✓ `class-add-button`
- ✓ `class-create-modal`
- ✓ `class-editor-form`, `class-editor-name-input`, `class-editor-domain-select`, `class-editor-parent-input`, `class-editor-description-input`, `class-editor-submit-button`
- ✓ `schema-table`, `schema-row-*` (pattern-based, dynamic with class ID)
- ✓ `schema-page-layout`
- ✓ `class-drawer`, `class-drawer-id`, `class-drawer-name-input`, `class-drawer-description-input`, `class-drawer-domain-select`

---

## Factory Usage

This plan uses factory patterns for setup and teardown:

**Setup**: Create a concept scheme via factory (required for the domain select):

```typescript
const taxonomy = await createTaxonomy(page, {
  title: "test-taxonomy-create-class",
  description: "Taxonomy for class creation tests",
});
const scheme = await createConceptScheme(page, taxonomy.id, {
  title: "test-scheme-create-class",
  description: "Scheme for class creation tests",
});
```

**Teardown**: Use `clearTestData(page)` in `test.afterEach()` to remove all test data:

```typescript
test.afterEach(async ({ page }) => {
  await clearTestData(page);
});
```

**Test Data Lifecycle**:
1. **Setup**: Create taxonomy and scheme via factory (deterministic, fast)
2. **Test Execution**: Follow UI interactions in steps 1–8 above
3. **Verification**: Assert UI state changes (table refresh, drawer display, toast)
4. **Cleanup**: `clearTestData` removes all created entities

---

## Notes for Generator

- **Navigation**: Use `page.goto("/app/schema/classes")` to navigate to the Classes page
- **Form validation timing**: Validate on blur, not keystroke. Use `await field.blur()` before checking error visibility
- **Error clearing**: After correcting a field, error should disappear on blur (Test Case 6)
- **Spinner duration**: Assert spinner is visible for ≤300ms (use `expect(spinner).toHaveClass("spinner")` or similar)
- **Toast assertion**: Locate toast by success-intent text pattern and verify copy: `Class created · cls_*`
- **Drawer assertion**: Verify `schema-page-layout` is present and `class-drawer` is open when class is selected
- **Class ID capture**: Extract the class ID from the generated response or table row for drawer verification
- **Pattern-based selectors**: For `schema-row-*`, use `page.locator('[data-testid^="schema-row-"]')` to find dynamic rows
- **Modal closure**: Use `expect(modal).not.toBeVisible()` to verify modal closes, not timeout-based checks
- **Escape key**: Use `page.press("Escape")` to simulate key press
