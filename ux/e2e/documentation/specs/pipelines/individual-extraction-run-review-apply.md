# Test Plan: Individual Extraction Run, Review, and Apply

## Overview

This test validates the complete golden path for executing an individual extraction pipeline, reviewing extracted triples/individuals in the candidate table, and applying them to the graph. The user navigates to the Individual Extraction pipeline type, configures source data input, waits for completion, reviews extracted individual candidates, applies them, and verifies that new individuals are visible on the Individuals page.

## Scope

- **Entities involved**: PipelineType (individual_extraction), PipelineRun, Individual
- **Pages involved**: `/app/pipelines`, `/app/pipelines/{pipelineType}/run`, `/app/data/individuals`
- **External dependencies**: Back-end API for pipeline execution and individual extraction
- **API endpoints**:
  - `GET /api/pipeline-types` (list available pipeline types)
  - `POST /api/pipeline-runs` (create and execute run)
  - `GET /api/pipeline-runs/{id}` (fetch run details and candidates)
  - `POST /api/pipeline-runs/{id}/apply` (apply selected candidates)
  - `GET /api/individuals` (verify applied individuals)

## Test Cases

### Test Case 1: Navigate to Pipeline Hub and Locate Individual Extraction Type

**Preconditions**:

- User is authenticated and has a workspace open
- The "Individual Extraction" pipeline type is available
- Ontology with at least one class exists (created via factory)

**Steps**:

1. Navigate to `/app/pipelines`
2. Wait for pipelines page to load (selector `pipelines-page`)
3. Verify the grid of pipeline type cards is visible (selector `pipeline-types-grid`)
4. Locate the "Individual Extraction" pipeline type card (selector `pipeline-type-card-individual_extraction`)
5. Verify the card displays the pipeline type name and description
6. Verify the "Run" button is visible and enabled (selector `pipeline-run-button-individual_extraction`)

**Expected Result**:

- Pipelines hub loads successfully
- Individual Extraction card is visible with correct name and description
- Run button is ready to interact

**Selectors Used**: `pipelines-page`, `pipeline-types-grid`, `pipeline-type-card-individual_extraction`, `pipeline-run-button-individual_extraction`

**Invariants Verified**:

- Pipeline hub displays all available pipeline types
- Individual Extraction type is properly labeled and accessible
- Run button is located on the correct card

---

### Test Case 2: Open Individual Extraction Wizard and Configure Source Data

**Preconditions**:

- User is on the pipelines hub (`/app/pipelines`)
- Individual Extraction pipeline type card is visible (from Test Case 1)

**Steps**:

1. Click the "Run" button on the Individual Extraction card (selector `pipeline-run-button-individual_extraction`)
2. Wait for the wizard to open and load (selector `individual-extraction-wizard`)
3. Verify the wizard form is fully rendered
4. Locate the source text area (selector `individual-extraction-source`)
5. Enter sample source text (e.g., "John is a Person. Jane is a Person with the name Jane Doe. An Organization named Acme Inc. has employees John and Jane.")
6. Verify the text input has accepted the input

**Expected Result**:

- Wizard modal/page opens after clicking Run
- Form displays with expected fields
- Source input accepts multi-line text without errors
- Text is retained when interacting with other form fields

**Selectors Used**: `pipeline-run-button-individual_extraction`, `individual-extraction-wizard`, `individual-extraction-source`

**Invariants Verified**:

- Wizard state is preserved during form navigation
- Input does not auto-clear or reset
- Text area handles multi-line and special characters

---

### Test Case 3: Configure Target Ontology/Classes

**Preconditions**:

- Individual extraction wizard is open (from Test Case 2)
- A test ontology with classes exists (created via factory in preconditions)
- Source data input has been filled

**Steps**:

1. Locate the ontology/classes entity picker (selector `individual-extraction-ontology`)
2. Click on the picker input to open the class selection dropdown
3. Verify available classes are displayed in the dropdown
4. Select one or more classes that the extracted individuals should belong to
5. Verify the selected classes are displayed in the picker
6. Confirm that source data input is still populated

**Expected Result**:

- Picker dropdown opens and displays available classes
- Selected classes are shown in the picker field
- Form state is preserved (source data and class selections both retained)
- Form is ready for submission

**Selectors Used**: `individual-extraction-ontology`, `individual-extraction-source`

**Invariants Verified**:

- Multiple classes can be selected (if supported by the UI)
- Selection is retained until changed
- No auto-clearing of previous inputs

---

### Test Case 4: Submit Wizard and Wait for Pipeline Execution

**Preconditions**:

- Individual extraction wizard is open with source data and target classes configured
- Backend is available for processing

**Steps**:

1. Verify the Submit button is enabled (selector `individual-extraction-submit`)
2. Click the Submit button
3. Wait for loading state to appear (selector `individual-extraction-loading`)
4. Verify the loading message indicates processing
5. Wait for the run to complete by observing state changes (not fixed timeout)
6. Verify run status transitions to COMPLETED

**Expected Result**:

- Submit button is enabled when form is valid
- Loading state appears immediately after submission
- Pipeline execution starts and progresses
- UI updates to show completion (not stuck in loading)
- No timeout or error during execution

**Selectors Used**: `individual-extraction-submit`, `individual-extraction-loading`

**Invariants Verified**:

- Loading state is visible during execution
- Execution completes within reasonable time
- Run ID is available for subsequent steps

---

### Test Case 5: Review Extracted Individuals/Triples in Candidate Table

**Preconditions**:

- Pipeline run has completed successfully (status = COMPLETED)
- Extracted individual candidates are available in the run result
- Run detail view is displayed

**Steps**:

1. Verify the individual extraction review panel is visible (selector `individual-extraction-review`)
2. Verify the table displays extracted individual/triple candidates
3. Verify each candidate row has columns: individual name, class, properties, etc.
4. Verify each row is selectable (checkboxes are present)
5. Use the select-all checkbox to select all candidates (selector `individual-extraction-select-all`)
6. Verify all rows are highlighted/selected

**Expected Result**:

- Individual extraction review panel renders with table interface
- Table displays extracted individuals with proper columns
- Each row has a checkbox for selection
- Select-all checkbox works and toggles all visible rows
- Selected rows are visually indicated

**Selectors Used**: `individual-extraction-review`, `individual-extraction-select-all`

**Invariants Verified**:

- Each candidate has required fields (name is always present)
- Selection state is tracked independently per row
- Select-all works correctly (selects/deselects all)

---

### Test Case 6: Click Apply Button and Confirm Application

**Preconditions**:

- Individual extraction review panel is open
- At least one individual candidate is selected
- Apply controls section is visible (selector `run-apply-section`)

**Steps**:

1. Verify the Apply button is visible and enabled (selector `run-apply-button`)
2. Click the Apply button
3. Wait for confirmation dialog to appear (selector `run-apply-confirm-dialog`)
4. Verify the dialog displays the count of individuals to be applied (e.g., "Apply 5 individuals?")
5. Click the Confirm button in the dialog to proceed

**Expected Result**:

- Apply button appears below the review table
- Confirmation dialog opens before application
- Dialog shows human-readable summary of what will be applied
- Dialog can be dismissed (Cancel button available)
- Clicking Confirm proceeds with application

**Selectors Used**: `run-apply-button`, `run-apply-confirm-dialog`

**Invariants Verified**:

- Apply is only available when at least one entity is selected
- Apply button is disabled if no selections are made
- Confirmation step prevents accidental modification

---

### Test Case 7: Verify Apply Result Summary

**Preconditions**:

- Apply confirmation dialog has been confirmed from Test Case 6
- Application is in progress

**Steps**:

1. Wait for the apply operation to complete (observe result panel appearance)
2. Verify the apply result panel is visible (selector `run-apply-result`)
3. Verify the result displays a summary (e.g., "Applied 5 individuals")
4. Verify the panel shows applied count and indicates success
5. Verify no error messages appear (success state)

**Expected Result**:

- Apply operation completes without errors
- Result panel displays applied individual count
- Summary is human-readable
- No error banners or failure messages
- Result indicates successful completion

**Selectors Used**: `run-apply-result`

**Invariants Verified**:

- Applied count matches selected count from review
- Result panel appears only after successful application
- Result persists (not cleared after brief delay)

---

### Test Case 8: Navigate to Individuals Page and Verify Applied Individuals Exist

**Preconditions**:

- Apply operation has completed successfully (from Test Case 7)
- Extracted individuals have been applied
- User is on the run detail page/drawer

**Steps**:

1. Close the run detail drawer or navigate to `/app/data/individuals`
2. Wait for the individuals page to load (selector `individuals-page`)
3. Verify the individuals table is visible (selector `schema-page-layout` is present when individuals exist)
4. Search or scroll to find one of the newly applied individuals by name
5. Verify the individual appears in the table (selector pattern `individual-name-*`)
6. Click on the individual row to open its detail drawer
7. Verify the individual details match the extracted data (name, classes, properties)

**Expected Result**:

- Individuals page loads successfully
- Newly applied individuals are visible in the table
- Individual data matches the extracted candidate data
- Individual can be opened and inspected
- No orphaned or incomplete individual entries

**Selectors Used**: `individuals-page`, `schema-page-layout`, `individual-name-*`

**Invariants Verified**:

- Applied individuals are persisted in the graph
- Individual data is complete (name, class memberships, properties)
- No duplicate individuals are created
- Class memberships are correctly assigned

---

### Test Case 9: Verify Individual Class Memberships and Properties

**Preconditions**:

- Applied individuals have been verified on the Individuals page (from Test Case 8)
- An individual detail drawer is open

**Steps**:

1. Locate the individual drawer showing detail of one applied individual
2. Verify the individual's class chips are visible (selector pattern `individual-class-chip-*`)
3. Verify each class chip displays the correct class name
4. Verify the individual's properties are displayed (selector `individual-properties-panel`)
5. Close the drawer and open another applied individual
6. Verify the second individual also displays correct classes and properties

**Expected Result**:

- Individual drawer displays all class memberships as chips
- Each class chip shows the correct class name
- Properties panel displays inherited properties from classes
- Multiple individuals can be inspected
- All data is consistent with extracted candidates

**Selectors Used**: `individual-class-chip-*`, `individual-properties-panel`

**Invariants Verified**:

- Class memberships are correctly assigned to individuals
- Properties are inherited from assigned classes
- No class or property data is missing or truncated

---

## Coverage Analysis

### CRUD Coverage

- **Create**: Individuals are created via pipeline application (Test Cases 6-7)
- **Read**: Extracted candidates are read from run result (Test Case 5), applied individuals are read from graph (Test Cases 8-9)
- **Update**: Not applicable in this test (applied individuals are new)
- **Delete**: Not covered in this plan
- **Execute**: Pipeline run is executed (Test Cases 2-4)

### Edge Cases

- **No extracted candidates**: Individual extraction might return no results (empty state handling: selector `individual-extraction-empty`)
- **Partial selection**: User selects only some individuals for application (Test Case 6)
- **Duplicate prevention**: System should not create duplicate individuals if run is applied twice
- **Class membership validation**: Individuals must have valid class assignments
- **Property inheritance**: Individuals should inherit properties from their assigned classes

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions — all waits are tied to observable state (loading, result panel, table visibility)
- ✓ No hardcoded UUIDs — run IDs and entity IDs are retrieved from API responses
- ✓ No invented selectors — all selectors exist in registry or match registered patterns
- ✓ No vacuous assertions — all assertions verify specific, observable outcomes (individual counts, table content, class assignments)
- ✓ No text-based selectors for mutable content — all selectors use `data-testid` attributes
- ✓ Proper cleanup — test data (ontology, classes) created in preconditions should be cleaned up in `afterEach` via `clearTestData`

---

## Factory Usage

Factories needed for preconditions:

- **Taxonomy factory** (`createTaxonomy`): Create a test taxonomy
- **Concept Scheme factory** (`createConceptScheme`): Create a test concept scheme
- **Class factory** (`createClass`): Create one or more test classes in the scheme
- **Cleanup** (`clearTestData`): Delete all test data after test completes

Note: Pipeline types (individual_extraction) are assumed to exist as built-in system types.

---

## Open Questions

1. **Multiple class selection**: Does the individual extraction wizard support selecting multiple target classes, or only one?

2. **Run completion detection**: Should we rely on UI state observation (result panel) or poll a backend endpoint for run status?

3. **Individual deduplication**: If the same individual is extracted and applied in multiple runs, does the system detect and prevent duplication?

4. **Class requirements**: Are individuals required to have at least one class assignment, or are class-less individuals allowed?

5. **Batch apply idempotency**: If the same run is applied twice, are individuals duplicated or is application idempotent?

---

## Quality Gate Summary

- [x] Every selector listed exists in `ux/selector-registry.yaml` or matches a registered pattern
- [x] Every entity field referenced exists in API response types
- [x] The plan aligns with pipeline execution golden path workflows
- [x] CRUD coverage is explicit (Create, Read, Execute)
- [x] Invariant validation is named (extraction integrity, apply confirmation, individual verification)
- [x] Anti-patterns acknowledged (no timeouts, no hardcoded IDs, no invented selectors)
- [x] Factory usage documented (taxonomy, scheme, class creation and cleanup)
