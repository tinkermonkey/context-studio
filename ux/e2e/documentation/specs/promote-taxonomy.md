# Test Plan: Promote a Draft Taxonomy

## Overview

This test validates the complete "Promote a draft taxonomy" user flow from UX.md § 2.3. The test covers the golden path: selecting a draft taxonomy, opening the Publish dialog with a diff summary, submitting with a commit message, and verifying the status transitions to published. It also covers two edge cases: cancelling the dialog leaves the taxonomy in draft state, and attempting to publish a taxonomy with no concept schemes shows an appropriate error state.

## Scope

- **Entities involved**: Taxonomy, ConceptScheme, Class
- **Pages involved**: `/app/schema/taxonomies` (taxonomies list page), drawer detail view for a draft taxonomy
- **External dependencies**: Back-end API endpoints for publish, diff stats, and schema queries
- **API endpoints**:
  - `GET /api/taxonomies` (read taxonomies)
  - `GET /api/taxonomies/{taxonomy_id}` (read single taxonomy)
  - `GET /api/taxonomies/{taxonomy_id}/publish-diff` (get diff stats for publish)
  - `POST /api/taxonomies/{taxonomy_id}/publish` (publish taxonomy)
  - `POST /api/taxonomies` (create taxonomy)
  - `POST /api/taxonomies/{taxonomy_id}/schemes` (create concept scheme)
  - `POST /api/schemes/{scheme_id}/classes` (create class)

## Test Cases

### Test Case 1: Golden Path — Publish a Draft Taxonomy with Changes

**Preconditions**:

- User is on `/app/schema/taxonomies` (taxonomies page)
- A draft taxonomy exists with at least one concept scheme containing classes
- Factories used:
  - `createTaxonomy()` — creates a draft taxonomy
  - `createConceptScheme()` — creates a concept scheme under that taxonomy
  - `createClass()` — creates at least one class in the scheme

**Steps**:

1. Click on the taxonomy name (selector `taxonomy-name-{taxonomyId}`) in the taxonomies table to select it
2. Drawer opens on the right (selector `taxonomy-drawer`) showing taxonomy details
3. Verify the drawer displays the status chip (inline text showing "draft") in the drawer body
4. Click the "Publish…" button in the drawer header (selector `taxonomy-drawer-publish-button`)
5. Publish dialog opens (selector `taxonomy-publish-dialog`)
6. Wait for the diff summary to load (selector contains diff text showing "X classes added" or similar)
7. Locate the publication message textarea (selector `taxonomy-publish-message-input`)
8. Type a commit-style message: "Add organism hierarchy to taxonomy"
9. Verify the "Publish" button is now enabled (selector `taxonomy-publish-confirm-button`)
10. Click the "Publish" button to submit
11. Dialog closes automatically
12. Drawer remains open; status text updates to "published"
13. Toast appears with message "Taxonomy published — `{taxonomy.title} · v{taxonomy.version}`"

**Expected Result**:

- Taxonomy status in the drawer changes from "draft" to "published"
- Drawer closes and taxonomy row in table is updated (status chip now shows "published" with green background)
- Toast confirms publish success with taxonomy name and version number
- Subsequent navigation to the taxonomy drawer shows the updated status

**Selectors Used**:

- `taxonomy-name-{taxonomyId}` (table cell to select taxonomy)
- `taxonomy-drawer` (drawer container)
- `taxonomy-drawer-publish-button` (Publish button in drawer header)
- `taxonomy-publish-dialog` (dialog modal)
- `taxonomy-publish-message-input` (message textarea)
- `taxonomy-publish-confirm-button` (Publish confirm button)
- `taxonomy-publish-cancel-button` (Cancel button, visible in dialog)

**Invariants Verified**:

- Taxonomy `status` transitions from "draft" to "published" (immutable after publish)
- Taxonomy `version` increments on successful publish
- Commit message is required and non-empty (button disabled until text entered)
- Publish operation shows diff summary before confirmation (reflects changes from current draft state)

---

### Test Case 2: Edge Case — Cancel Publish Dialog

**Preconditions**:

- User is on `/app/schema/taxonomies` page
- A draft taxonomy is selected and drawer is open (selector `taxonomy-drawer`)
- Drawer shows status "draft"
- Factories used: same as Test Case 1

**Steps**:

1. Click "Publish…" button in drawer header (selector `taxonomy-drawer-publish-button`)
2. Publish dialog opens (selector `taxonomy-publish-dialog`)
3. Optionally fill in the message field (selector `taxonomy-publish-message-input`) with some text
4. Click the "Cancel" button (selector `taxonomy-publish-cancel-button`)
5. Dialog closes
6. Drawer remains open and displays the original taxonomy (unchanged)

**Expected Result**:

- Dialog closes without mutation
- Taxonomy remains in "draft" status in the drawer (inline status text)
- No toast is displayed
- No API call to publish is made (verify no network traffic)
- Taxonomy in the table continues to show "draft" status chip

**Selectors Used**:

- `taxonomy-drawer-publish-button`
- `taxonomy-publish-dialog`
- `taxonomy-publish-message-input`
- `taxonomy-publish-cancel-button`

**Invariants Verified**:

- Cancellation leaves taxonomy in original state (no side effects)
- Dirty form state (message entered) is discarded
- No partial mutations occur

---

### Test Case 3: Edge Case — Publish Fails When Taxonomy Has No Concept Schemes

**Preconditions**:

- User is on `/app/schema/taxonomies` page
- A draft taxonomy exists but has no concept schemes (empty taxonomy with zero schemes)
- Factories used:
  - `createTaxonomy()` — creates a draft taxonomy
  - No scheme or class creation

**Steps**:

1. Click on the empty taxonomy name (selector `taxonomy-name-{taxonomyId}`) in the table to select it
2. Drawer opens (selector `taxonomy-drawer`) showing taxonomy with no classes listed
3. Click the "Publish…" button (selector `taxonomy-drawer-publish-button`)
4. Publish dialog opens (selector `taxonomy-publish-dialog`)
5. Diff summary area displays an error message or "No changes to publish" (no classes in the taxonomy)
6. Enter a message in the textarea (selector `taxonomy-publish-message-input`)
7. Attempt to click "Publish" button (selector `taxonomy-publish-confirm-button`)

**Expected Result**:

- Publish button is disabled (or if clicked, the API rejects with a validation error)
- Error banner or toast appears with a message like "Cannot publish taxonomy with no concept schemes" or "Cannot publish taxonomy with no classes"
- Dialog remains open with form state preserved
- Taxonomy remains in "draft" status
- No publish mutation succeeds

**Selectors Used**:

- `taxonomy-name-{taxonomyId}`
- `taxonomy-drawer`
- `taxonomy-drawer-publish-button`
- `taxonomy-publish-dialog`
- `taxonomy-publish-message-input`
- `taxonomy-publish-confirm-button`

**Invariants Verified**:

- Publish is prevented when taxonomy has zero concept schemes (validation rule enforced)
- Error messaging is clear and actionable (guides user to add schemes before publishing)
- Form state and taxonomy state remain unchanged after failed attempt

---

## Coverage Analysis

### CRUD Coverage

- **Create**: Taxonomy created via factory; concept schemes and classes created to populate the taxonomy for publishing
- **Read**: Taxonomy read from table, detail page, drawer
- **Update**: Taxonomy status updated from "draft" to "published" via publish endpoint
- **Delete**: Not covered in this plan (out of scope for promote flow)

### Edge Cases

- **Cancellation**: Publishing dialog can be cancelled without side effects
- **Validation**: Empty taxonomy (no concept schemes) cannot be published
- **Diff Summary**: Publish dialog displays a summary of what will be published (added/modified/removed classes)
- **Immutability**: Status "published" is final; unpublish is not supported
- **Message Required**: Publication message must be non-empty; button disabled until text entered
- **Version Increment**: Taxonomy version increments on successful publish

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions (all waits use `.waitFor()` and inspect DOM for expected state, e.g., dialog opening, status chip update)
- ✓ No hardcoded UUIDs (factory-created IDs only; selectors use dynamic {taxonomyId} patterns)
- ✓ No invented selectors (all selectors verified in `ux/selector-registry.yaml`)
- ✓ No vacuous assertions (all assertions verify actual state changes: status text, chip color, toast message, button enablement)
- ✓ No text-based selectors for mutable content (taxonomy title/description used via data-testid, not text matching)
- ✓ Cleanup via `clearTestData()` in afterEach to remove created taxonomies

## Factory Usage

**Required factories**:
- `createTaxonomy(page, overrides?: {title?, description?})` — creates a draft taxonomy
- `createConceptScheme(page, taxonomyId?, overrides?: {title?, description?})` — creates a concept scheme under the given taxonomy
- `createClass(page, schemeId, overrides?: {title?, description?, parent_class_id?})` — creates a class in the scheme

**Cleanup**:
- `clearTestData(page)` called in `afterEach` to delete all created taxonomies, schemes, and classes

---

## Open Questions

**Missing selector registration**: The selector pattern `taxonomy-name-*` is used in the code at `/workspace/ux/src/routes/app/schema/taxonomies.tsx` (line 74) to create selectors like `taxonomy-name-{taxonomyId}`, but this pattern is **not registered** in `ux/selector-registry.yaml`. 

Similar patterns for other entities (e.g., `class-name-*`, `individual-name-*`, `scheme-name-link-*`) are already registered in the registry. This test plan assumes `taxonomy-name-*` will be added to the registry following the same pattern.

**Required action**: Add the following entry to `ux/selector-registry.yaml` (after line 334, in the Taxonomies Page section):

```yaml
  - selector: taxonomy-name-*
    component: routes/app/schema/taxonomies.tsx
    description: Clickable taxonomy name cell in table with dynamic ID suffix
```

All other selectors are verified and registered:
- `taxonomy-drawer` (line 283)
- `taxonomy-drawer-publish-button` (line 295)
- `taxonomy-publish-dialog` (line 303)
- `taxonomy-publish-message-input` (line 306)
- `taxonomy-publish-cancel-button` (line 309)
- `taxonomy-publish-confirm-button` (line 312)
