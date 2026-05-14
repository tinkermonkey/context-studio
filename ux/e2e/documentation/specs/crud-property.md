# Test Plan: Property CRUD Operations

## Overview

This test validates the complete CRUD workflow for Property Definitions in Context Studio. Property Definitions are global predicates (relationship types) that can be used across all relationships in the ontology. The test covers creation, reading via drawer display, field editing with autosave feedback, deletion with confirmation handling, and undo restoration. The flow covers both properties that are in use (linked to relationships) and unused properties to validate conditional behavior.

## Scope

- **Entities involved**: PropertyDefinition, Relationship (for "in use" validation)
- **Pages involved**: `/app/schema/properties` (properties list page)
- **External dependencies**: Back-end API (`/api/properties`, `/api/relationships`)
- **API endpoints**:
  - `POST /api/properties` (create)
  - `GET /api/properties` (read/list)
  - `PUT /api/properties/{property_id}` (update)
  - `DELETE /api/properties/{property_id}` (soft delete)
  - `POST /api/properties/{property_id}/undo` (restore)
  - `GET /api/relationships` (fetch for "in use" check)

## Test Cases

### Test Case 1: Create a New Property via Modal

**Preconditions**:

- User is logged in and navigated to `/app/schema/properties`
- Properties table is visible (may be empty or populated)

**Steps**:

1. Click the "Add Property" button with selector `property-add-button`
2. Verify modal opens with selector `property-create-modal`
3. Locate the form with selector `property-create-form`
4. Fill the identifier input (selector `property-definition-identifier-input`) with `prop_test_crud_001` (snake_case, no spaces)
5. Fill the title input (selector `property-definition-title-input`) with `Test Property CRUD`
6. Fill the description input (selector `property-definition-description-input`) with `Property for testing CRUD operations`
7. Click the submit button with selector `property-definition-submit-button`
8. Verify modal closes automatically
9. Verify the newly created property appears in the table on the properties page

**Expected Result**:

- Modal closes without errors
- New property row appears in the table with:
  - Identifier: `prop_test_crud_001`
  - Title: `Test Property CRUD`
  - Description: `Property for testing CRUD operations`
  - Version: `1`
  - Status: `draft` (default)
  - Timestamps set (created_at, last_modified)
- Property is searchable by identifier or title

**Selectors Used**: `property-add-button`, `property-create-modal`, `property-create-form`, `property-definition-identifier-input`, `property-definition-title-input`, `property-definition-description-input`, `property-definition-submit-button`, `schema-table`

**Invariants Verified**:

- PropertyDefinition `identifier` is required, non-empty, and globally unique (snake_case)
- PropertyDefinition `title` is required and non-empty
- PropertyDefinition `description` is optional
- PropertyDefinition `version` starts at `1`
- PropertyDefinition `status` defaults to `draft`
- PropertyDefinition `created_at` and `last_modified` are set automatically

---

### Test Case 2: Open Property Drawer and Verify Field Values

**Preconditions**:

- Property created in Test Case 1 exists in the table
- User is on `/app/schema/properties`

**Steps**:

1. Locate the property row by identifier (selector pattern `schema-row-{propertyId}`)
2. Click the property row to select it
3. Verify the drawer opens on the right side (selector `properties-drawer`)
4. Verify the drawer displays the property details with selector `property-drawer`
5. Verify the identifier field (selector `property-drawer-identifier`) is read-only and displays `prop_test_crud_001`
6. Verify the title field (selector `property-drawer-title-input`) displays `Test Property CRUD`
7. Verify the description field (selector `property-drawer-description-input`) displays `Property for testing CRUD operations`
8. Verify the split layout is present (selector `schema-page-layout` indicates drawer+table arrangement)

**Expected Result**:

- Drawer opens in split-pane layout (table on left, drawer on right)
- All field values match the created property
- Identifier is displayed as read-only text (not an input)
- Title and description are displayed in editable input/textarea fields
- Drawer remains open while row is selected

**Selectors Used**: `properties-drawer`, `property-drawer`, `property-drawer-identifier`, `property-drawer-title-input`, `property-drawer-description-input`, `schema-page-layout`, `schema-row-*`

**Invariants Verified**:

- PropertyDefinition `identifier` is immutable (read-only in UI)
- PropertyDefinition `title` and `description` are editable in the drawer
- Drawer layout follows `SchemaPageLayout` pattern (split-2 grid)

---

### Test Case 3: Edit a Field and Verify Autosave Indicator

**Preconditions**:

- Property drawer is open (from Test Case 2)
- Property row is selected
- Drawer displays editable fields

**Steps**:

1. Locate the title input field in the drawer (selector `property-drawer-title-input`)
2. Clear the current value and type a new title: `Test Property CRUD - Updated`
3. Verify the autosave status indicator becomes visible (selector `drawer-autosave-status`)
4. Verify the status indicator shows "Saving..." or similar state
5. Wait for the autosave to complete (indicator shows success or clears)
6. Verify the server update succeeds (no error messages)
7. Verify the property version increments from `1` to `2` (visible in drawer or table)

**Expected Result**:

- Title field value changes to `Test Property CRUD - Updated`
- Autosave indicator appears on `onChange` event
- Autosave completes without errors
- Updated property persists (refresh verification in subsequent tests)
- Version increments to `2`

**Selectors Used**: `property-drawer-title-input`, `drawer-autosave-status`, `properties-drawer`

**Invariants Verified**:

- PropertyDefinition `version` increments on update
- PropertyDefinition `last_modified` timestamp updates
- Autosave feedback is provided to the user (visual indicator)
- Form validation errors clear on `onChange` (if validation error was present, it clears)

---

### Test Case 4: Delete Property (Unused) and Verify Undo Toast

**Preconditions**:

- Property is updated and drawer still shows the latest version
- Property is NOT linked to any relationships (unused)
- User can see delete action in the drawer

**Steps**:

1. Locate the delete button in the drawer (selector `drawer-delete-button`)
2. Click the delete button
3. Verify that NO confirmation dialog appears (since property is unused, no "in use" warning required)
4. Property row disappears from the table immediately
5. Verify an undo toast appears at the bottom of the screen (selector `toast-action-*`)
6. Verify toast message indicates the property was deleted
7. Verify the undo button/action is visible on the toast (selector pattern `toast-action-*`)
8. Drawer closes automatically when property is deleted

**Expected Result**:

- Property is soft-deleted (removed from visible list)
- Undo toast appears with action button
- Drawer closes
- Property no longer visible in the table
- Toast persists for ~8 seconds before auto-dismissing

**Selectors Used**: `drawer-delete-button`, `properties-drawer`, `toast-action-*`, `properties-table`

**Invariants Verified**:

- PropertyDefinition soft delete removes entity from list view
- Undo toast appears for all deletions (standard UX pattern)
- Undo action is clickable and triggers restoration

---

### Test Case 5: Click Undo and Restore the Deleted Property

**Preconditions**:

- Property was deleted in Test Case 4
- Undo toast is still visible (within 8-second window)
- Drawer is closed, table is visible

**Steps**:

1. Verify the undo toast is still visible with selector `toast-action-*`
2. Locate and click the undo action button on the toast (selector `toast-action-*`)
3. Verify the toast dismisses
4. Verify the deleted property reappears in the table
5. Verify the property row is visible with all original data intact
6. Optionally click the property row to open drawer and verify the title still shows the updated value `Test Property CRUD - Updated`
7. Verify the version remains at `2` (undo does not reset version)

**Expected Result**:

- Property is restored to the list
- All field values persist (title update from Test Case 3 is preserved)
- Version remains `2` (unchanged)
- Undo toast clears
- Property is immediately usable again

**Selectors Used**: `toast-action-*`, `schema-row-*`, `properties-table`, `property-drawer`, `property-drawer-title-input`

**Invariants Verified**:

- PropertyDefinition soft delete is reversible within undo window
- Undo restores field values correctly
- Undo does not reset version or timestamps

---

### Test Case 6: Delete Property (In Use) with Confirmation Dialog

**Preconditions**:

- A new property has been created (separate from Test Cases 1-5, e.g., `prop_in_use`)
- A relationship exists that references this property (via `property_definition_id`)
- User navigates to properties page and opens drawer for this property

**Steps**:

1. Create a second property via factory in precondition: `createPropertyDefinition(page, { identifier: "prop_in_use", title: "In Use Property" })`
2. Create a relationship that uses this property (via factory, linking two classes)
3. Navigate to `/app/schema/properties`
4. Find and click the `prop_in_use` property row
5. Open drawer (selector `properties-drawer`)
6. Click delete button (selector `drawer-delete-button`)
7. Verify a confirmation dialog appears (selector `confirm-dialog`)
8. Verify the dialog message mentions the property is in use or linked to relationships
9. Verify two buttons: "Cancel" (selector `confirm-dialog-cancel`) and "Delete" (selector `confirm-dialog-confirm`)
10. Click the "Delete" button to confirm
11. Verify the property is deleted and undo toast appears

**Expected Result**:

- Confirmation dialog appears before deletion (different from unused property behavior)
- Dialog warns user about relationships
- After confirmation, property is soft-deleted
- Undo toast appears
- Drawer closes

**Selectors Used**: `property-drawer`, `drawer-delete-button`, `confirm-dialog`, `confirm-dialog-cancel`, `confirm-dialog-confirm`, `toast-action-*`, `properties-drawer`

**Invariants Verified**:

- Deletion of properties in use triggers a warning dialog
- User can cancel the operation
- After confirmation, deletion proceeds normally
- Undo restoration works the same for in-use properties

---

## Coverage Analysis

### CRUD Coverage

- **Create**: ✓ Test Case 1 — Property created via modal form with required fields
- **Read**: ✓ Test Case 2 — Property opened in drawer, all fields displayed correctly
- **Update**: ✓ Test Case 3 — Property title edited, autosave indicator shown, version incremented
- **Delete**: ✓ Test Cases 4 & 6 — Property deleted (unused and in-use variants), soft delete confirmed, undo available
- **Restore**: ✓ Test Case 5 — Deleted property restored via undo within window

### Edge Cases

- **Property in Use**: Test Case 6 validates that deletion of a property linked to relationships triggers a confirmation dialog
- **Property Unused**: Test Case 4 validates that deletion of unused properties may not require confirmation (or user experience differs)
- **Autosave**: Test Case 3 validates that edits trigger autosave with visual feedback
- **Undo Window**: Test Cases 4-5 validate undo functionality and timing
- **Field Immutability**: Test Cases 2-3 validate that identifier is read-only while title and description are editable
- **Version Concurrency**: Test Case 3 validates version increment on update
- **Cascading Relationships**: Test Case 6 assumes relationships exist; cleanup must delete relationships before properties in `afterEach`

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions: Autosave completion is verified via element visibility (drawer-autosave-status), not `waitForTimeout()`
- ✓ No hardcoded UUIDs: All property IDs are generated by factories; navigation uses returned `id` from creation response
- ✓ No invented selectors: All selectors verified in `/workspace/ux/selector-registry.yaml`
- ✓ No vacuous assertions: All assertions verify specific field values, not generic truthy checks
- ✓ No mutable content text-based selectors: Property data is identified by ID (selector pattern `schema-row-{id}`), not text matching
- ✓ Cleanup in afterEach: `clearTestData()` factory function deletes all properties and relationships created during test
- ✓ No undocumented selectors: All selectors are in the registry and components are identified in registry

## Open Questions

None. All required selectors exist in the registry. All entity fields are defined in `/workspace/ux/src/api/client/types.ts`.

## Factory Usage

The following factories from `/workspace/ux/e2e/fixtures/factories.ts` will be used:

- **`createPropertyDefinition(page, overrides)`**: Create test properties
  - Generates unique identifier (`prop-{timestamp}`) and title (`test-property-{timestamp}`)
  - Supports overrides for custom identifier, title, and description
  - Returns `PropertyDefinition` object with `id`, `identifier`, `title`, `description`, `version`, `created_at`, etc.

- **`createConceptScheme(page, taxonomyId, overrides)`**: Create prerequisite concept scheme for relationships
  - Used in precondition for Test Case 6 (property in use)

- **`createClass(page, schemeId, overrides)`**: Create prerequisite classes for relationships
  - Used in precondition for Test Case 6 to create source and target classes

- **`createRelationship(page, sourceClassId, targetClassId, propertyDefinitionId)`**: Link property to relationship
  - Used in precondition for Test Case 6 to create a relationship that uses the test property

- **`clearTestData(page)`**: Delete all test data in `afterEach`
  - Clears relationships, properties, taxonomies, and schemes
  - Called after all test cases to ensure clean state

**Cleanup Strategy** (in `afterEach`):

```
await clearTestData(page);
```

This single call handles deletion of all entities created during the test, respecting deletion order (relationships before properties before taxonomies).
