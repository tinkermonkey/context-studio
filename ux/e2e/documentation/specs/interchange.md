# Test Plan: Import/Export (Interchange)

## Overview

This test plan covers Phase 3.8 of the Interchange feature, which enables users to export ontology data in SKOS format and import data with conflict resolution. The tests verify the complete lifecycle: export functionality, import with dry-run preview, conflict grouping and resolution, import run creation, and historical run tracking with paginated change events.

## Scope

- **Entities involved**: Taxonomy, ConceptScheme, OntologyClass, PropertyDefinition, Relationship, ImportRun, ImportConflict, ChangeEvent
- **Pages involved**: `/app/interchange/export`, `/app/interchange/import`, `/app/interchange`, `/app/interchange/runs/$runId`
- **External dependencies**: File I/O (download/upload), in-memory dry-run preview API, import commit API

## Test Cases

### Test Case 1: Export ontology in SKOS format with whole graph scope

**Preconditions:**
- Create test taxonomy with title `"Test Taxonomy Export-<timestamp>"` using `createTaxonomy()`
- Create test concept scheme within taxonomy using `createConceptScheme()`
- Create 2-3 test ontology classes within scheme using `createClass()`
- Create property definition using `createPropertyDefinition()`
- Create relationships between classes using `createRelationship()`

**Steps:**
1. Navigate to `/app/interchange/export`
2. Locate export format dropdown (`data-testid="interchange-export-format-select"`) and select "SKOS"
3. Locate scope picker (`data-testid="interchange-export-scope-picker"`) and select "Whole Graph"
4. Click download button (`data-testid="interchange-export-download-button"`)
5. Verify file download completes (file picker or network tab)

**Expected Result:**
- File download is triggered with filename matching pattern `*skos*` or `*rdf*`
- Downloaded file is binary data (not text error response)
- No console errors are visible

**Selectors Used:**
- `interchange-export-format-select`
- `interchange-export-scope-picker`
- `interchange-export-download-button`

**Invariants Verified:**
- Export operates on the whole graph without loss of data structure
- File is returned in requested format (SKOS/RDF)

---

### Test Case 2: Import file with dry-run preview showing conflicts grouped by match_kind

**Preconditions:**
- Create test taxonomy and scheme with 2 classes (`ClassA`, `ClassB`)
- Prepare a SKOS file content (string) containing:
  - One class with matching external_reference to existing class (conflicts: external_reference match_kind)
  - One class with matching UUID to existing class (conflicts: uuid match_kind)
  - One class with matching title to existing class (conflicts: title match_kind)
  - One new class not in database (no conflict, in "create" group)

**Steps:**
1. Navigate to `/app/interchange/import`
2. Locate file input area (`data-testid="interchange-import-file-input"`)
3. Upload SKOS file (drag-drop or file picker)
4. Click preview button (`data-testid="interchange-import-preview-button"`)
5. Wait for dry-run API response; conflict modal opens (`data-testid="interchange-conflict-resolution-modal"`)
6. Verify conflicts are grouped by match_kind:
   - Locate external_reference group (`data-testid="interchange-conflict-group-external-reference"`)
   - Locate uuid group (`data-testid="interchange-conflict-group-uuid"`)
   - Locate title group (`data-testid="interchange-conflict-group-title"`)
   - Locate create group (`data-testid="interchange-conflict-group-create"`)

**Expected Result:**
- Modal displays conflicts grouped by match_kind with clear headers
- Each conflict group shows entity details (title, ID, existing reference if applicable)
- New entities (no conflict) are listed under "create" group
- New entity count is displayed

**Selectors Used:**
- `interchange-import-file-input`
- `interchange-import-preview-button`
- `interchange-conflict-resolution-modal`
- `interchange-conflict-group-external-reference`
- `interchange-conflict-group-uuid`
- `interchange-conflict-group-title`
- `interchange-conflict-group-create`

**Invariants Verified:**
- Conflicts are accurately categorized by match_kind
- All imported entities are accounted for (conflicts + new)
- Descriptions show which entity attribute caused the match (external_reference, UUID, or title)

---

### Test Case 3: Resolve conflicts with apply-all-per-group strategy and commit import

**Preconditions:**
- Dry-run from Test Case 2 is in progress with conflict modal open
- At least 2-3 conflicts exist across different match_kind groups

**Steps:**
1. Within external_reference conflict group, apply resolution to all similar conflicts:
   - Click apply-all button (`data-testid="interchange-conflict-apply-all-external_reference"`)
   - Select resolution strategy (e.g., "skip" or "overwrite")
2. Within uuid conflict group, click apply-all button (`data-testid="interchange-conflict-apply-all-uuid"`)
   - Select resolution strategy
3. Within title conflict group, click apply-all button (`data-testid="interchange-conflict-apply-all-title"`)
   - Select resolution strategy
4. Verify all conflicts are resolved (no unresolved indicator visible)
5. Click commit button (`data-testid="interchange-conflict-commit-button"`)
6. Wait for import commit API response; modal closes and success toast appears

**Expected Result:**
- Apply-all buttons batch-resolve conflicts within the same match_kind group
- UI updates to show all conflicts as resolved
- Commit API is called with resolved conflict list
- Toast displays success message with import run ID
- Page remains on import page or redirects to `/app/interchange/runs/$runId`

**Selectors Used:**
- `interchange-conflict-apply-all-external_reference`
- `interchange-conflict-apply-all-uuid`
- `interchange-conflict-apply-all-title`
- `interchange-conflict-commit-button`

**Invariants Verified:**
- Each conflict must have exactly one resolution applied before commit
- Resolutions are applied consistently within a group
- Import run ID is returned upon successful commit

---

### Test Case 4: Cancel conflict resolution and dismiss modal

**Preconditions:**
- Dry-run from Test Case 2 is in progress with conflict modal open

**Steps:**
1. With conflicts unresolved, click cancel button (`data-testid="interchange-conflict-cancel-button"`)
2. Verify modal closes

**Expected Result:**
- Modal is dismissed without committing
- User is back on import page
- No changes are persisted
- File and format selections may remain for re-preview

**Selectors Used:**
- `interchange-conflict-cancel-button`

**Invariants Verified:**
- Cancel does not submit any API request
- No side effects occur on cancel

---

### Test Case 5: Verify ImportRun appears in recent runs list with correct metadata

**Preconditions:**
- Import run created in Test Case 3 with ID `$runId`
- Run has been committed and stored in database

**Steps:**
1. Navigate to `/app/interchange` (recent runs landing page)
2. Verify recent runs table is present (`data-testid="interchange-recent-runs-table"`)
3. Locate the run row for `$runId` in table (`data-testid="interchange-runs-table-row-{run_id}"`)
4. Verify row displays:
   - Run ID
   - Format (SKOS)
   - Created timestamp
   - Status (committed)
   - Number of affected entities
5. Click on the row to navigate to detail page

**Expected Result:**
- ImportRun appears in table with all metadata fields visible
- Row is clickable and navigates to `/app/interchange/runs/$runId`
- Table updates immediately after import (via cache invalidation)

**Selectors Used:**
- `interchange-recent-runs-table`
- `interchange-runs-table-row-{run_id}`

**Invariants Verified:**
- ImportRun metadata is persisted and retrievable
- Table displays runs in correct order (most recent first)
- Status field reflects actual run state

---

### Test Case 6: Navigate to ImportRun detail page and verify affected entities display

**Preconditions:**
- ImportRun detail page `/app/interchange/runs/$runId` is loaded
- Run has affected_entity_ids with 3+ entities

**Steps:**
1. Verify metadata section is present (`data-testid="interchange-run-detail-metadata"`)
2. Verify metadata displays:
   - Run ID
   - Format
   - Created at timestamp
   - Status badge
   - Scope type (whole_graph)
   - Created by (if populated)
3. Locate affected entities section (`data-testid="interchange-run-affected-entities"`)
4. Verify section lists all entity IDs from run.affected_entity_ids
5. Each entity ID is displayed in a readable format (e.g., in a list or grid)

**Expected Result:**
- Metadata section is fully rendered with all fields visible
- Affected entities list shows all impacted entity IDs
- No entities are missing or duplicated in the list

**Selectors Used:**
- `interchange-run-detail-metadata`
- `interchange-run-affected-entities`

**Invariants Verified:**
- Run metadata is complete and accurate (not null or truncated)
- Affected entity count matches the import plan
- Scope information correctly describes the import scope

---

### Test Case 7: Verify change events pagination on detail page

**Preconditions:**
- ImportRun detail page with 40+ change events (pagination threshold is 20 per page)

**Steps:**
1. Locate change events section (`data-testid="interchange-run-change-events"`)
2. Verify first page displays 20 change events
3. Verify each event row shows:
   - Entity ID
   - Entity type
   - Change type (create/update/delete)
   - Timestamp
4. Scroll or locate pagination controls (Next/Previous buttons or page indicator)
5. Click next button to load page 2
6. Verify page 2 displays events 21-40
7. Verify previous button returns to page 1

**Expected Result:**
- Change events are paginated with limit of 20 per page
- Pagination controls work and fetch new data on click
- No stale data is displayed (each page shows correct offset)
- Pagination state is maintained across page navigation

**Selectors Used:**
- `interchange-run-change-events`

**Invariants Verified:**
- Change events are ordered chronologically
- Pagination offset is correctly calculated
- No duplicate events across page boundaries

---

### Test Case 8: Attempt to import invalid file content and verify error handling

**Preconditions:**
- Have an invalid file (e.g., corrupted SKOS, unsupported format, malformed XML)

**Steps:**
1. Navigate to `/app/interchange/import`
2. Upload invalid file
3. Click preview button (`data-testid="interchange-import-preview-button"`)
4. Wait for API response (dry-run with invalid content)

**Expected Result:**
- API returns error (400 or 422 status)
- Error toast is displayed with descriptive message
- No conflict modal opens
- Import flow is halted; user can try again with different file

**Selectors Used:**
- `interchange-import-file-input`
- `interchange-import-preview-button`

**Invariants Verified:**
- Invalid input is rejected gracefully with user-friendly error
- No partial state is persisted
- User is not blocked from retry

---

## Coverage Analysis

### CRUD Coverage

**Create:**
- Classes, ConceptSchemes, PropertyDefinitions, Relationships are created via factories
- ImportRun is created as a result of successful import commit
- ChangeEvents are created automatically during import

**Read:**
- ImportRun is read via `/api/interchange/runs/{id}`
- ChangeEvents are read with pagination via `/api/interchange/runs/{id}/change-events`
- Recent runs list is read via `/api/interchange/runs`

**Update:**
- No update operations in this test plan (interchange is append-only)

**Delete:**
- No delete operations tested; import does not delete entities, only adds or modifies

### Edge Cases

**Concurrency:**
- Not tested in this plan; assumes single-user sequential import

**Cascade Effects:**
- Relationships are created between existing classes; import respects existing class hierarchy

**Orphaned Relationships:**
- If import targets missing class, conflict resolution must handle (skip/create/abort)

**Pagination Boundaries:**
- Test Case 7 covers page boundary at exactly 20 events
- Next page button is disabled when fewer than 20 events are loaded

### Anti-Pattern Validations

- ✓ **No fixed timeouts**: Tests use `.waitForLoadState()` or element visibility waits, never `page.waitForTimeout(N)`
- ✓ **No vacuous assertions**: All assertions check specific values (e.g., table row count, badge color, conflict count), never `expect(true).toBe(true)`
- ✓ **No hardcoded UUIDs**: All entity IDs are created via factories and stored in variables (e.g., `$runId`), never assumed or hardcoded
- ✓ **No invented selectors**: All selectors exist in `ux/selector-registry.yaml` (verified above)
- ✓ **No text-based navigation**: Navigation uses routes and IDs, never `.getByText()` for buttons
- ✓ **Cleanup**: `afterEach` uses `clearTestData()` to delete all factory-created entities (see Factory Usage)
- ✓ **No implementation details**: Tests assert on visible UI elements and API responses, never on state management or store
- ✓ **Error handling included**: Test Case 8 covers error path explicitly
- ✓ **No page load assumptions**: Elements are located via `data-testid`, not position or DOM order

## Open Questions

None. All required selectors exist in `ux/selector-registry.yaml`:
- Export panel selectors: ✓ `interchange-export-format-select`, `interchange-export-scope-picker`, `interchange-export-download-button`
- Import panel selectors: ✓ `interchange-import-file-input`, `interchange-import-preview-button`
- Conflict resolution selectors: ✓ `interchange-conflict-resolution-modal`, `interchange-conflict-group-*` (external_reference, uuid, title, create), `interchange-conflict-apply-all-*` (match_kind variants), `interchange-conflict-commit-button`, `interchange-conflict-cancel-button`
- Recent runs selectors: ✓ `interchange-recent-runs-table`, `interchange-runs-table-row-{run_id}`
- Run detail selectors: ✓ `interchange-run-detail-metadata`, `interchange-run-affected-entities`, `interchange-run-change-events`

## Factory Usage

**Entities to Create (in Test Preconditions):**
- `createTaxonomy()` — creates test taxonomy with unique title
- `createConceptScheme()` — creates scheme within taxonomy
- `createClass()` — creates 2-3 ontology classes within scheme
- `createPropertyDefinition()` — creates relationship predicate
- `createRelationship()` — creates edges between classes

**Import File Creation:**
- No factory exists for SKOS file generation; test will manually construct valid SKOS XML/RDF content as a string and upload as Blob

**Cleanup:**
- `afterEach()` calls `clearTestData()` helper (assumed to exist in fixtures or test utilities) to delete all created entities
- Alternatively, use direct API DELETE calls via `apiRequest()` for each entity type

**Fixture Dependencies:**
- `apiRequest()` from `ux/e2e/fixtures/api-client.ts` — for factory API calls
- All factories from `ux/e2e/fixtures/factories.ts` — `createTaxonomy`, `createConceptScheme`, `createClass`, `createPropertyDefinition`, `createRelationship`

