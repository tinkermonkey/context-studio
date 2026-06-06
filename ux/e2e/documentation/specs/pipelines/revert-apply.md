# Test Plan: Pipeline Run Apply and Revert

## Overview

This test validates the complete workflow for applying pipeline run candidates to the ontology and subsequently reverting those applied changes. The user executes a pipeline, waits for completion with extracted candidates, applies the candidates to add new entities, verifies the ontology reflects the changes, navigates back to the run detail, and then reverts the apply operation to restore the ontology to its pre-apply state.

## Scope

- **Entities involved**: PipelineType, PipelineRun, OntologyClass, PropertyDefinition, Relationship, Individual
- **Pages involved**: `/app/pipelines`, `/app/pipelines/{pipelineType}/run`, `/app/pipelines/runs`, `/app/pipelines/runs/{runId}`, `/app/schema/classes`, `/app/data/individuals`
- **External dependencies**: Back-end API for pipeline execution, apply, and revert operations
- **API endpoints**:
  - `POST /api/pipeline-runs` (create and execute run)
  - `GET /api/pipeline-runs/{id}` (fetch run details and candidates)
  - `POST /api/pipeline-runs/{id}/apply` (apply selected candidates)
  - `POST /api/pipeline-runs/{id}/revert` (revert a previously applied run)
  - `GET /api/classes`, `GET /api/individuals` (verify entity state before and after operations)

## Test Cases

### Test Case 1: Execute a Pipeline Run and Wait for Completion

**Preconditions**:

- User is authenticated and has a workspace open
- A pipeline type with expected candidates is available (e.g., Schema Extraction, Individual Extraction, Grounding)
- Ontology has sufficient schema context for the pipeline (taxonomy, concept scheme, classes)

**Steps**:

1. Navigate to `/app/pipelines`
2. Wait for pipelines page to load (selector `pipelines-page`)
3. Locate and click the "Run" button on a pipeline type card that produces extractable candidates (e.g., `pipeline-run-button-individual_extraction`)
4. Wait for the wizard to open (selector varies by pipeline type, e.g., `individual-extraction-wizard`)
5. Configure the wizard inputs (source text, target ontology, etc.)
6. Click the Submit button to execute the pipeline
7. Wait for loading state to appear and then observe the run status transition to COMPLETED (do not use fixed timeout)
8. Verify the run completed without errors (no error messages visible)

**Expected Result**:

- Pipeline wizard opens and accepts input
- Submission triggers execution
- Loading state appears during processing
- Run completes with COMPLETED status
- No timeout or execution errors

**Selectors Used**: `pipelines-page`, `pipeline-run-button-individual_extraction`, `individual-extraction-wizard`, `individual-extraction-submit`, `individual-extraction-loading`

**Invariants Verified**:

- Pipeline execution framework completes runs to terminal state
- Loading state is visible to user during execution
- Run ID is generated and available for subsequent operations

---

### Test Case 2: Review Candidates and Select for Application

**Preconditions**:

- Pipeline run has completed with COMPLETED status (from Test Case 1)
- Run candidates are available in the review panel (not empty)
- Run detail view is displayed

**Steps**:

1. Verify the review panel is visible (selector for the pipeline type, e.g., `individual-extraction-review`)
2. Verify candidates are displayed in the review table/list (selector `individual-extraction-review` or type-specific)
3. Select one or more candidates using the select-all checkbox or individual row checkboxes (selector `individual-extraction-select-all`)
4. Verify the selected candidates are highlighted or marked as selected
5. Scroll through the candidates to confirm multiple are displayed and selectable

**Expected Result**:

- Review panel renders with candidate table
- Candidates are selectable via checkboxes
- Selection state is visible in the UI
- No candidates are unexpectedly filtered or hidden

**Selectors Used**: `individual-extraction-review`, `individual-extraction-select-all`

**Invariants Verified**:

- Candidates from run execution are accessible for review
- Selection mechanism works independently per row
- UI reflects selection state accurately

---

### Test Case 3: Click Apply Button and Confirm Application

**Preconditions**:

- Review panel is open with candidates selected (from Test Case 2)
- Apply controls section is visible (selector `run-apply-section`)

**Steps**:

1. Verify the Apply button is visible and enabled (selector `run-apply-button`)
2. Click the Apply button
3. Wait for confirmation dialog to appear (selector `run-apply-confirm-dialog`)
4. Verify the dialog shows a summary of entities to be applied (count of new individuals, classes, etc.)
5. Click the Confirm button in the dialog to proceed with application

**Expected Result**:

- Apply button appears below the review panel
- Confirmation dialog opens before application
- Dialog displays human-readable summary of changes
- Dialog is dismissible (Cancel button works)
- Clicking Confirm proceeds with application

**Selectors Used**: `run-apply-button`, `run-apply-confirm-dialog`

**Invariants Verified**:

- Apply operation requires explicit user confirmation
- Dialog prevents accidental data modification
- Summary accurately reflects what will be applied

---

### Test Case 4: Verify Apply Completion and Result Summary

**Preconditions**:

- Apply confirmation dialog has been confirmed (from Test Case 3)
- Application is in progress

**Steps**:

1. Wait for the apply operation to complete (observe for result panel appearance, not fixed timeout)
2. Verify the apply result panel is visible (selector `run-apply-result`)
3. Verify the result displays a summary (e.g., "Applied 3 individuals" or "Created 2 classes, 1 relationship")
4. Verify the panel shows entity counts indicating success
5. Verify no error messages appear (success state only)
6. Verify the run status may update to reflect the applied state

**Expected Result**:

- Apply operation completes without errors
- Result panel displays applied entity counts
- Summary is human-readable and shows what was added
- No error banners appear
- Result panel persists in the run detail view

**Selectors Used**: `run-apply-result`

**Invariants Verified**:

- Applied count reflects selected candidates from review
- Result panel appears only after successful application
- Apply state is persisted in the run record

---

### Test Case 5: Navigate to Ontology and Verify Applied Entities Exist

**Preconditions**:

- Apply operation has completed successfully with result panel showing (from Test Case 4)
- Entities have been applied to the ontology

**Steps**:

1. Close the run detail drawer or navigate to the corresponding ontology page (e.g., `/app/data/individuals` for individual extraction)
2. Wait for the page to load
3. Search or filter for one of the newly applied entities by name (use search input)
4. Verify the entity appears in the table (selector `schema-row-*` or type-specific row selector)
5. Click on the entity row to open its detail view
6. Verify the entity details match the extracted/applied data

**Expected Result**:

- Ontology page loads successfully
- Newly applied entity is visible in the table
- Entity data matches the applied data
- Entity can be opened and inspected
- No orphaned or incomplete entries

**Selectors Used**: `individuals-page` or type-specific page, `schema-row-*`

**Invariants Verified**:

- Applied entities are persisted in the ontology
- Entity data is complete and correct
- No duplicate entities created
- Relationships to parent entities (classes, schemes) are correct

---

### Test Case 6: Navigate Back to Runs Page and Open the Applied Run Detail

**Preconditions**:

- Applied entities have been verified in the ontology (from Test Case 5)
- User is on an ontology page

**Steps**:

1. Navigate to `/app/pipelines/runs`
2. Wait for the runs page to load (selector `runs-page`)
3. Verify the pipeline runs table is visible (selector `runs-table`)
4. Locate the previously applied run by searching or scrolling (selector `run-row-{runId}`)
5. Click on the run row to open the run detail drawer

**Expected Result**:

- Runs page loads with all visible runs
- Previously applied run is visible in the table
- Run row is clickable and opens the detail drawer
- Run status may be updated to reflect the applied state

**Selectors Used**: `runs-page`, `runs-table`, `run-row-*`

**Invariants Verified**:

- Run history is retained after apply
- Run detail is accessible from runs page
- Run status or metadata reflects the applied state

---

### Test Case 7: Verify Apply Controls and Revert Button is Visible

**Preconditions**:

- Run detail drawer is open for the previously applied run (from Test Case 6)
- Run has applied changes (from Test Case 4)

**Steps**:

1. Verify the run detail drawer is displayed (selector `run-detail-drawer`)
2. Scroll down to the apply/revert controls section (selector `run-apply-section`)
3. Verify the Apply button is either disabled or shows "Already applied" state (selector `run-apply-button-disabled`)
4. Verify the Revert button is visible and enabled (selector `run-revert-button`)
5. Verify the revert controls indicate this run has been applied and can be reverted

**Expected Result**:

- Apply button is disabled (showing already applied state)
- Revert button is visible and enabled
- Controls clearly indicate the run has been applied
- UI prevents re-applying an already applied run

**Selectors Used**: `run-detail-drawer`, `run-apply-section`, `run-apply-button-disabled`, `run-revert-button`

**Invariants Verified**:

- Apply button state reflects that run has been applied
- Revert button is only available for applied runs
- UI prevents duplicate apply operations

---

### Test Case 8: Click Revert Button and Confirm Revert Operation

**Preconditions**:

- Revert button is visible and enabled (from Test Case 7)
- Run has been previously applied

**Steps**:

1. Click the Revert button (selector `run-revert-button`)
2. Wait for confirmation dialog to appear (selector `run-revert-confirm-dialog`)
3. Verify the dialog shows a summary like "Revert {count} changes?" or "This will remove {count} entities"
4. Click the Confirm button in the dialog to proceed with revert

**Expected Result**:

- Revert button is interactive and clickable
- Confirmation dialog opens before revert operation
- Dialog displays human-readable summary of changes to be reverted
- Dialog is dismissible (Cancel button works)
- Clicking Confirm proceeds with revert operation

**Selectors Used**: `run-revert-button`, `run-revert-confirm-dialog`

**Invariants Verified**:

- Revert operation requires explicit user confirmation
- Dialog prevents accidental data loss
- Summary accurately reflects what will be reverted

---

### Test Case 9: Verify Revert Completion and Result Summary

**Preconditions**:

- Revert confirmation dialog has been confirmed (from Test Case 8)
- Revert operation is in progress

**Steps**:

1. Wait for the revert operation to complete (observe for result panel appearance, not fixed timeout)
2. Verify the revert result panel is visible (selector `run-revert-result`)
3. Verify the result displays a summary (e.g., "Reverted 3 individuals" or "Removed 2 classes")
4. Verify the panel shows entity counts indicating revert success
5. Verify no error messages appear (success state only)
6. Verify the run status updates to reflect the reverted state

**Expected Result**:

- Revert operation completes without errors
- Result panel displays reverted entity counts
- Summary is human-readable and shows what was removed
- No error banners appear
- Result panel persists in the run detail view

**Selectors Used**: `run-revert-result`

**Invariants Verified**:

- Reverted count reflects previously applied entities
- Result panel appears only after successful revert
- Revert state is persisted in the run record

---

### Test Case 10: Navigate to Ontology and Verify Applied Entities Are Reverted

**Preconditions**:

- Revert operation has completed successfully with result panel showing (from Test Case 9)
- Entities should be removed or restored to pre-apply state

**Steps**:

1. Close the run detail drawer or navigate to the corresponding ontology page (e.g., `/app/data/individuals`)
2. Wait for the page to load
3. Search for one of the entities that was applied and then reverted
4. Verify the entity is no longer present in the table (if it was newly created) OR verify the entity data has been restored to pre-apply state (if it was modified)
5. Verify the table counts or entity statistics reflect the reverted state

**Expected Result**:

- Ontology page loads successfully
- Previously applied and then reverted entities are no longer present (or restored)
- Table data is consistent with the reverted state
- No orphaned or inconsistent entries remain

**Selectors Used**: `individuals-page` or type-specific page, search inputs

**Invariants Verified**:

- Revert operation successfully removes/restores applied entities
- Ontology state is consistent after revert
- No duplicate or orphaned entities remain
- Relationships are properly cleaned up

---

## Coverage Analysis

### CRUD Coverage

- **Create**: Entities are created via pipeline apply (Test Cases 1-5)
- **Read**: Applied entities are read from ontology to verify (Test Case 5), run details are read (Test Cases 6-7)
- **Update**: Not applicable in this test flow
- **Delete/Revert**: Applied entities are deleted/reverted via revert operation (Test Cases 8-10)
- **Execute**: Pipeline runs are executed (Test Case 1)

### Edge Cases

- **Apply idempotency**: Once applied, a run shows "already applied" state and cannot be re-applied (Test Case 7)
- **Revert completeness**: All entities from an apply are removed when reverted (Test Cases 9-10)
- **State consistency**: Run status and entity counts remain consistent across navigation and reload
- **Cascade behavior**: Removing applied entities properly cleans up relationships
- **Empty revert**: If a run was partially applied, revert handles only the applied subset

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions — all waits tied to observable state (result panel appearance, status changes)
- ✓ No hardcoded UUIDs — run IDs and entity IDs retrieved from API responses or UI
- ✓ No invented selectors — all selectors exist in registry or match registered patterns
- ✓ No vacuous assertions — all assertions verify specific, observable outcomes (button states, result visibility, entity presence)
- ✓ No text-based selectors for mutable content — uses `data-testid` attributes
- ✓ Proper cleanup — ontology is tested in final state; test data cleanup via `clearTestData` if needed

---

## Factory Usage

Factories needed for preconditions:

- **Ontology setup** (`createTaxonomy`, `createConceptScheme`, `createClass`): Create schema context for pipeline to extract against
- **Cleanup** (`clearTestData`): Delete all test-created entities after test completes (optional if revert test itself verifies cleanup)

Note: Pipeline types are assumed to exist as built-in system types.

---

## Open Questions

1. **Run status updates**: After apply and revert operations, does the run status field update to reflect "APPLIED" or "REVERTED" state, or does status remain COMPLETED with separate metadata?

2. **Partial revert**: If only some candidates were applied, does revert restore the original selection state in the run, or does it operate on all previously applied entities from that run?

3. **Revert idempotency**: Can a run be reverted multiple times, or is revert a one-time operation?

4. **Entity modification**: If an applied entity was subsequently modified in the ontology by the user, does revert restore it to the original extracted state or fail to revert?

5. **Run history retention**: Are applied and reverted runs retained indefinitely in the run history, or pruned after a period?

---

## Quality Gate Summary

- [x] Every selector listed exists in `ux/selector-registry.yaml` or matches a registered pattern
- [x] Every entity field exists in API response types
- [x] Plan aligns with pipeline apply/revert user workflows
- [x] CRUD coverage explicit (Create via apply, Delete via revert, Read throughout)
- [x] Invariant validation named (apply confirmation, revert confirmation, state consistency)
- [x] Anti-patterns acknowledged (no timeouts, no hardcoded IDs, no invented selectors)
- [x] Factory usage documented (ontology setup, cleanup)
