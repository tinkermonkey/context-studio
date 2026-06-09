# Test Plan: Schema Extraction Run, Review, and Apply

## Overview

This test validates the complete golden path for executing a schema extraction pipeline, reviewing extracted classes, properties, and relationships, and applying the results to the ontology. The user navigates to a pipeline type, configures and executes the run wizard, waits for completion, reviews the extracted candidates, and applies them to the knowledge graph while verifying that new entities are created.

## Scope

- **Entities involved**: PipelineType (schema_extraction), PipelineRun, OntologyClass, PropertyDefinition, Relationship
- **Pages involved**: `/app/pipelines`, `/app/pipelines/{pipelineType}/run`, `/app/pipelines/runs/{runId}`
- **External dependencies**: Back-end API for pipeline execution and schema extraction
- **API endpoints**:
  - `GET /api/pipeline-types` (list available pipeline types)
  - `POST /api/pipeline-runs` (create and execute run)
  - `GET /api/pipeline-runs/{id}` (fetch run details and candidates)
  - `POST /api/pipeline-runs/{id}/apply` (apply selected candidates)
  - `GET /api/classes`, `GET /api/properties`, `GET /api/relationships` (verify applied entities)

## Test Cases

### Test Case 1: Navigate to Pipeline Hub and Locate Schema Extraction Pipeline Type

**Preconditions**:

- User is authenticated and has a workspace open
- The "Schema Extraction" pipeline type is available in the system
- No prior runs are required

**Steps**:

1. Navigate to `/app/pipelines`
2. Wait for pipelines page to load (selector `pipelines-page`)
3. Verify the grid of pipeline type cards is visible (selector `pipeline-types-grid`)
4. Locate the "Schema Extraction" pipeline type card (selector `pipeline-type-card-schema_extraction`)
5. Verify the card displays the pipeline type name and description
6. Verify the "Run" button is visible on the card (selector `pipeline-run-button-schema_extraction`)

**Expected Result**:

- Pipelines hub loads successfully
- Schema Extraction pipeline type card is visible and contains expected information
- Run button is enabled and ready to interact

**Selectors Used**: `pipelines-page`, `pipeline-types-grid`, `pipeline-type-card-schema_extraction`, `pipeline-run-button-schema_extraction`

**Invariants Verified**:

- Pipeline hub displays all available pipeline types as cards
- Schema Extraction type is accessible and properly labeled
- Run button is located on the correct card and is interactive

---

### Test Case 2: Open Schema Extraction Wizard and Configure Input

**Preconditions**:

- User is on the pipelines hub (`/app/pipelines`)
- Schema Extraction pipeline type card is visible (from Test Case 1)

**Steps**:

1. Click the "Run" button on the Schema Extraction card (selector `pipeline-run-button-schema_extraction`)
2. Wait for the wizard to open and load (selector `schema-extraction-wizard`)
3. Verify the wizard form is fully rendered
4. Locate the document/source text input (selector `schema-extraction-document`)
5. Enter sample source text (e.g., "A Person is an entity. A Person has a name property. An Organization has employees who are Persons.")
6. Verify the text input field has accepted the input

**Expected Result**:

- Wizard modal/page opens after clicking Run button
- Form displays with all expected fields
- Document input accepts text without validation errors
- Input is retained when clicked elsewhere in the form

**Selectors Used**: `pipeline-run-button-schema_extraction`, `schema-extraction-wizard`, `schema-extraction-document`

**Invariants Verified**:

- Wizard state is preserved during navigation within the form
- Input does not auto-clear or reset unexpectedly
- Text area handles multi-line input correctly

---

### Test Case 3: Configure Taxonomy/Concept Scheme Target

**Preconditions**:

- Schema extraction wizard is open (from Test Case 2)
- A taxonomy and concept scheme exist in the workspace (created via factory in preconditions)
- Document input has been filled with sample text

**Steps**:

1. Locate the taxonomy/concept scheme picker (selector `schema-extraction-taxonomy-picker`)
2. Click on the picker input to open the entity selection dropdown
3. Select the test concept scheme from the dropdown
4. Verify the selected concept scheme is displayed in the picker
5. Confirm that the selection does not clear the document input

**Expected Result**:

- Picker dropdown opens and displays available concept schemes
- Selected scheme is displayed in the picker field
- Both document and scheme selections persist in the form
- Form is ready for submission

**Selectors Used**: `schema-extraction-taxonomy-picker`, `schema-extraction-document`

**Invariants Verified**:

- Only one concept scheme can be selected at a time
- Selection is retained until explicitly changed
- No auto-clearing of previous inputs when selecting a new field

---

### Test Case 4: Submit Wizard and Wait for Pipeline Execution

**Preconditions**:

- Schema extraction wizard is open with both document input and concept scheme selected
- The backend is available and can process the request

**Steps**:

1. Verify the Submit button is enabled (selector `schema-extraction-submit`)
2. Click the Submit button
3. Wait for loading state to appear (selector `schema-extraction-loading`)
4. Verify the loading message indicates processing has begun
5. Wait for the run to complete by polling the backend (waitForTimeout is anti-pattern, instead observe for: completion status change, candidate table appearance, or navigation to run detail)
6. Observe the run status transitions to COMPLETED

**Expected Result**:

- Submit button is enabled when form is valid
- Loading state appears immediately after submission
- Pipeline execution starts and progresses to completion
- UI updates to show run completion status (not stuck in loading state)
- No timeout or error appears during execution

**Selectors Used**: `schema-extraction-submit`, `schema-extraction-loading`

**Invariants Verified**:

- Loading state is displayed during execution (not hidden from user)
- Execution completes without hanging or exceeding reasonable timeout
- Run ID is generated and available for subsequent steps

---

### Test Case 5: Review Extracted Classes in Candidate Table

**Preconditions**:

- Pipeline run has completed successfully (status = COMPLETED)
- Extracted classes candidates are available in the run result
- Run detail view is displayed (either in drawer or dedicated page)

**Steps**:

1. Verify the schema extraction review panel is visible (selector `schema-extraction-review`)
2. Verify the Classes tab is active or click to activate the Classes tab
3. Locate the classes table container (selector `classes-table-container`)
4. Verify the table displays candidate classes with columns: name, description, etc.
5. Verify each candidate class row is selectable (checkboxes are present)
6. Select one or more classes by clicking the checkboxes or using select-all (selector `schema-extraction-select-all-classes`)

**Expected Result**:

- Schema extraction review panel renders with tabbed interface
- Classes tab displays extracted class candidates in table format
- Each row has a checkbox for selection
- Select-all checkbox works and selects/deselects all visible classes
- Selected rows are highlighted or visually indicated

**Selectors Used**: `schema-extraction-review`, `classes-table-container`, `schema-extraction-select-all-classes`

**Invariants Verified**:

- Only classes are shown in the Classes tab (not properties or relationships)
- Each candidate has required fields (name is always present)
- Selection state is independent per row (selecting one does not auto-select others)

---

### Test Case 6: Review Extracted Properties and Relationships

**Preconditions**:

- Schema extraction review panel is open from Test Case 5
- Classes tab has been reviewed and some classes are selected

**Steps**:

1. Click on the "Properties" tab in the review panel
2. Verify the properties table container is visible (selector `properties-table-container`)
3. Verify the table displays candidate property definitions
4. Scroll through the properties table to verify multiple properties are displayed
5. Use select-all checkbox to select properties (selector `schema-extraction-select-all-properties`)
6. Click on the "Relationships" tab
7. Verify the relationships table container is visible (selector `relationships-table-container`)
8. Verify the table displays candidate relationships with source and target class columns
9. Use select-all checkbox to select relationships (selector `schema-extraction-select-all-relationships`)

**Expected Result**:

- Properties tab displays extracted property candidates with name, description columns
- Properties are separate from classes and relationships
- Relationships tab displays relationships with source class, property type, and target class columns
- All tabs can be navigated without losing selection state
- Select-all checkboxes work independently per tab

**Selectors Used**: `properties-table-container`, `relationships-table-container`, `schema-extraction-select-all-properties`, `schema-extraction-select-all-relationships`

**Invariants Verified**:

- Each tab displays only its entity type (no mixing of classes/properties/relationships)
- Switching tabs preserves previous tab selections
- Select-all on one tab does not affect other tabs

---

### Test Case 7: Click Apply Button and Confirm Application

**Preconditions**:

- Schema extraction review panel is open
- At least one entity (class, property, or relationship) is selected across the tabs
- Apply controls section is visible (selector `run-apply-section`)

**Steps**:

1. Verify the Apply button is visible and enabled (selector `run-apply-button`)
2. Click the Apply button
3. Wait for confirmation dialog to appear (selector `run-apply-confirm-dialog`)
4. Verify the dialog shows the count of entities to be applied (e.g., "Apply 3 classes, 2 properties, 1 relationship?")
5. Click the Confirm button in the dialog to proceed with application

**Expected Result**:

- Apply button appears below the review tables
- Confirmation dialog opens before application (prevents accidental applies)
- Dialog displays human-readable summary of what will be applied
- Dialog is dismissible (Cancel button works)
- Clicking Confirm proceeds with application

**Selectors Used**: `run-apply-button`, `run-apply-confirm-dialog`

**Invariants Verified**:

- Apply is only available when at least one entity is selected
- Apply button is disabled if no entities are selected
- Confirmation step prevents accidental data modification

---

### Test Case 8: Verify Apply Result Summary

**Preconditions**:

- Apply confirmation dialog has been confirmed from Test Case 7
- Application is in progress

**Steps**:

1. Wait for the apply operation to complete (observe for result panel appearance)
2. Verify the apply result panel is visible (selector `run-apply-result`)
3. Verify the result displays a summary like "Applied 3 classes, 2 properties, 1 relationship"
4. Verify the panel shows entity counts and indicates success
5. Verify the panel does not show error messages (success state)

**Expected Result**:

- Apply operation completes without errors
- Result panel displays applied entity counts
- Summary is human-readable and shows what was added to the graph
- No error banners or failure messages appear
- Result panel indicates successful completion

**Selectors Used**: `run-apply-result`

**Invariants Verified**:

- Applied count matches selected count from review step
- Result panel appears only after successful application
- Result persists in the run detail view (not cleared after brief delay)

---

### Test Case 9: Navigate to Ontology and Verify Applied Entities Exist

**Preconditions**:

- Apply operation has completed successfully (from Test Case 8)
- Extracted classes, properties, and relationships have been applied
- User is on the run detail page/drawer

**Steps**:

1. Close the run detail drawer or navigate to the Classes page (`/app/schema/classes`)
2. Wait for the classes page to load
3. Search or filter for one of the newly applied classes by name (use search input)
4. Verify the class appears in the classes table (selector `schema-row-*` for the specific class)
5. Click on the class row to open its detail drawer
6. Verify the class details are visible and match the extracted definition

**Expected Result**:

- Classes page loads successfully
- Newly applied class is visible in the table
- Class data matches the extracted candidate data
- Class can be opened and inspected in detail view
- No orphaned or incomplete class entries

**Selectors Used**: `classes-page`, `schema-row-*`

**Invariants Verified**:

- Applied classes are persisted in the ontology
- Class data is complete (name, description, concept scheme)
- No duplicate classes are created
- Class relationships to concept scheme are correct

---

### Test Case 10: Verify Applied Properties and Relationships

**Preconditions**:

- Applied classes have been verified (from Test Case 9)
- User has navigated to properties and relationships pages

**Steps**:

1. Navigate to `/app/schema/properties`
2. Wait for properties page to load (selector `properties-page`)
3. Verify one or more of the newly applied properties are visible in the table
4. Click on a property row to open its detail drawer
5. Verify the property name and description match the extracted data
6. Navigate to `/app/schema/relationships`
7. Wait for relationships page to load (selector `relationships-page`)
8. Verify one or more of the newly applied relationships are visible in the table
9. Verify relationship rows show correct source class, property type, and target class

**Expected Result**:

- Applied properties appear in the properties table with correct metadata
- Applied relationships appear in the relationships table with correct connections
- All entity data is consistent with the extracted candidates
- No missing or truncated data fields

**Selectors Used**: `properties-page`, `relationships-page`, `schema-row-*`

**Invariants Verified**:

- All applied properties are persisted and queryable
- All applied relationships reference existing classes
- No orphaned properties or relationships exist
- Relationship integrity is maintained (source and target classes exist)

---

## Coverage Analysis

### CRUD Coverage

- **Create**: Classes, properties, and relationships are created via pipeline application (Test Cases 7-10)
- **Read**: Extracted candidates are read from run result (Test Cases 5-6), applied entities are read from ontology (Test Cases 9-10)
- **Update**: Not applicable in this test (applied entities are new, not modified)
- **Delete**: Not covered in this plan
- **Execute**: Pipeline run is executed (Test Cases 2-4)

### Edge Cases

- **No extracted candidates**: Schema extraction might return no results (empty state handling: selector `schema-extraction-empty`)
- **Partial selection**: User selects only some candidates for application (Test Case 7)
- **Duplicate prevention**: System should not create duplicate entities if run is applied twice (idempotency)
- **Concept scheme requirement**: All classes must be assigned to the selected concept scheme
- **Property uniqueness**: Properties with same identifier should not be duplicated

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions — all waits are tied to observable state (loading state, result panel appearance, entity visibility)
- ✓ No hardcoded UUIDs — run IDs and entity IDs are retrieved from API responses
- ✓ No invented selectors — all selectors exist in registry or match registered patterns
- ✓ No vacuous assertions — all assertions verify specific, observable outcomes (entity counts, table visibility, data content)
- ✓ No text-based selectors for mutable content — all selectors use `data-testid` attributes, not UI text
- ✓ Proper cleanup — test data (taxonomy, scheme) created in preconditions should be cleaned up in `afterEach` via `clearTestData`

---

## Factory Usage

Factories needed for preconditions:

- **Taxonomy factory** (`createTaxonomy`): Create a test taxonomy
- **Concept Scheme factory** (`createConceptScheme`): Create a test concept scheme within the taxonomy
- **Cleanup** (`clearTestData`): Delete all test data after test completes

Note: Pipeline types (schema_extraction) are assumed to exist as built-in system types and do not need to be created via factory.

---

## Open Questions

1. **Run completion detection**: The test currently relies on observable state changes (loading state ending, result panel appearing). Should we add a backend endpoint to poll run status directly, or rely on UI state observation?

2. **Apply button state**: Is the Apply button disabled when no entities are selected, or is it always enabled and the confirmation dialog handles validation?

3. **Batch apply behavior**: If user applies the same run multiple times, should the system detect and prevent re-application, or allow idempotent application?

4. **Entity deduplication**: If a class with the same name is extracted twice and applied, does the system create two classes or update the existing one?

5. **Run retention**: After applying a run, is the run history retained indefinitely, or does it expire after a certain period?

---

## Quality Gate Summary

- [x] Every selector listed exists in `ux/selector-registry.yaml` or matches a registered pattern
- [x] Every entity field referenced exists in API response types
- [x] The plan aligns with pipeline execution golden path workflows
- [x] CRUD coverage is explicit (Create, Read, Execute)
- [x] Invariant validation is named (schema extraction integrity, apply confirmation, entity verification)
- [x] Anti-patterns acknowledged (no timeouts, no hardcoded IDs, no invented selectors)
- [x] Factory usage documented (taxonomy, scheme creation and cleanup)
