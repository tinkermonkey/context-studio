# Test Plan: Definition Refinement Run, Review, and Apply

## Overview

This test validates the complete golden path for executing a definition refinement pipeline, reviewing candidate definitions for a class, selecting a candidate definition to refine the class description, and applying the result to update the class definition in the ontology. The user navigates to the Definition Refinement pipeline type, configures with a class that needs definition refinement, waits for completion, reviews candidate definitions, selects one to apply, and verifies that the class definition is persisted.

## Scope

- **Entities involved**: PipelineType (definition_refinement), PipelineRun, OntologyClass (with updated definition)
- **Pages involved**: `/app/pipelines`, `/app/pipelines/{pipelineType}/run`, `/app/schema/classes`
- **External dependencies**: Back-end API for pipeline execution and definition refinement
- **API endpoints**:
  - `GET /api/pipeline-types` (list available pipeline types)
  - `POST /api/pipeline-runs` (create and execute run)
  - `GET /api/pipeline-runs/{id}` (fetch run details and definition candidates)
  - `POST /api/pipeline-runs/{id}/apply` (apply selected definition candidate)
  - `GET /api/classes/{id}` (verify class definition is updated)

## Test Cases

### Test Case 1: Navigate to Pipeline Hub and Locate Definition Refinement Pipeline Type

**Preconditions**:

- User is authenticated and has a workspace open
- The "Definition Refinement" pipeline type is available
- Ontology with at least one class exists (created via factory)

**Steps**:

1. Navigate to `/app/pipelines`
2. Wait for pipelines page to load (selector `pipelines-page`)
3. Verify the grid of pipeline type cards is visible (selector `pipeline-types-grid`)
4. Locate the "Definition Refinement" pipeline type card (selector `pipeline-type-card-definition_refinement`)
5. Verify the card displays the pipeline type name and description
6. Verify the "Run" button is visible and enabled (selector `pipeline-run-button-definition_refinement`)

**Expected Result**:

- Pipelines hub loads successfully
- Definition Refinement pipeline type card is visible with correct name
- Run button is ready to interact

**Selectors Used**: `pipelines-page`, `pipeline-types-grid`, `pipeline-type-card-definition_refinement`, `pipeline-run-button-definition_refinement`

**Invariants Verified**:

- Pipeline hub displays all available pipeline types
- Definition Refinement type is properly labeled and accessible
- Run button is located on the correct card

---

### Test Case 2: Open Definition Refinement Wizard and Select Class

**Preconditions**:

- User is on the pipelines hub (`/app/pipelines`)
- Definition Refinement pipeline type card is visible (from Test Case 1)
- A test ontology with at least one class exists (created via factory in preconditions)

**Steps**:

1. Click the "Run" button on the Definition Refinement card (selector `pipeline-run-button-definition_refinement`)
2. Wait for the wizard to open and load (selector `definition-refinement-wizard`)
3. Verify the wizard form is fully rendered
4. Locate the class entity picker (selector `definition-refinement-class`)
5. Click on the picker input to open the class selection dropdown
6. Select a test class from the dropdown
7. Verify the selected class is displayed in the picker

**Expected Result**:

- Wizard modal/page opens after clicking Run
- Form displays with expected fields
- Class picker dropdown opens and displays available classes
- Selected class is shown in the picker field
- Form is ready for next step

**Selectors Used**: `pipeline-run-button-definition_refinement`, `definition-refinement-wizard`, `definition-refinement-class`

**Invariants Verified**:

- Only one class can be selected at a time
- Selection is retained until explicitly changed
- Wizard state is preserved during form navigation

---

### Test Case 3: Review Current Definition and Neighborhood Context

**Preconditions**:

- Definition refinement wizard is open (from Test Case 2)
- A class has been selected

**Steps**:

1. Verify the neighborhood/context preview panel is visible (selector `definition-refinement-neighborhood`)
2. Verify the panel displays the class context (parent classes, related classes, properties)
3. Locate the current definition text area (selector `definition-refinement-definition`)
4. Verify the current definition is displayed (if one exists)
5. Confirm that the class and context information is loaded

**Expected Result**:

- Neighborhood panel displays the class context and relationships
- Current definition textarea shows existing definition (or is empty if new)
- Context helps inform the refinement process
- Form is ready for submission

**Selectors Used**: `definition-refinement-neighborhood`, `definition-refinement-definition`

**Invariants Verified**:

- Neighborhood context accurately reflects class relationships
- Current definition is accurately displayed
- Context is loaded and visible before submission

---

### Test Case 4: Submit Wizard and Wait for Pipeline Execution

**Preconditions**:

- Definition refinement wizard is open with a class selected
- The backend is available and can process the request

**Steps**:

1. Verify the Submit button is enabled (selector `definition-refinement-submit`)
2. Click the Submit button
3. Wait for loading state to appear (selector `definition-refinement-loading`)
4. Verify the loading message indicates processing has begun
5. Wait for the run to complete by observing state changes (not fixed timeout)
6. Observe the run status transitions to COMPLETED

**Expected Result**:

- Submit button is enabled when form is valid
- Loading state appears immediately after submission
- Pipeline execution starts and progresses to completion
- UI updates to show run completion status (not stuck in loading state)
- No timeout or error appears during execution

**Selectors Used**: `definition-refinement-submit`, `definition-refinement-loading`

**Invariants Verified**:

- Loading state is displayed during execution
- Execution completes without hanging
- Run ID is generated and available for subsequent steps

---

### Test Case 5: Review Candidate Definitions

**Preconditions**:

- Pipeline run has completed successfully (status = COMPLETED)
- Definition candidate(s) are available in the run result
- Run detail view is displayed

**Steps**:

1. Verify the definition refinement review panel is visible (selector `definition-refinement-review`)
2. Verify the panel displays the current (non-candidate) definition as a radio option (selector `definition-refinement-radio-current`)
3. Verify one or more candidate definitions are displayed as radio options (selector pattern `definition-refinement-radio-candidate-*`)
4. Verify each candidate shows the proposed definition text
5. Verify radio buttons are present for selection

**Expected Result**:

- Definition refinement review panel renders with radio button interface
- Current definition is displayed as the first option
- One or more candidate definitions are visible below
- Each definition is selectable via radio button
- Form is ready for selection and application

**Selectors Used**: `definition-refinement-review`, `definition-refinement-radio-current`, `definition-refinement-radio-candidate-*`

**Invariants Verified**:

- Current definition is always shown as an option
- Candidate definitions are clearly distinct from current
- Radio button interface prevents multi-selection
- All definition text is displayed fully (no truncation)

---

### Test Case 6: Select a Candidate Definition

**Preconditions**:

- Definition refinement review panel is open (from Test Case 5)
- Multiple definition options are visible (current + candidates)

**Steps**:

1. Verify at least one candidate definition radio button is visible
2. Click on a candidate definition radio button (using selector pattern `definition-refinement-radio-candidate-{index}`)
3. Verify the selected radio button is now checked
4. Verify that only one definition is selected at a time (radio button behavior)
5. Confirm the Apply button is now enabled (selector `run-apply-button`)

**Expected Result**:

- Candidate definition radio button is clickable
- Only one definition can be selected at a time
- Selected state is visually indicated (checked radio)
- Apply button becomes enabled when a selection is made
- Form is ready for application

**Selectors Used**: `definition-refinement-radio-candidate-*`, `run-apply-button`

**Invariants Verified**:

- Only one definition can be selected (radio button invariant)
- Selection is retained until changed
- Apply is only enabled when a definition is selected

---

### Test Case 7: Click Apply Button and Confirm Application

**Preconditions**:

- Definition refinement review panel is open
- A candidate definition has been selected (from Test Case 6)
- Apply controls section is visible (selector `run-apply-section`)

**Steps**:

1. Verify the Apply button is visible and enabled (selector `run-apply-button`)
2. Click the Apply button
3. Wait for confirmation dialog to appear (selector `run-apply-confirm-dialog`)
4. Verify the dialog shows a confirmation message (e.g., "Apply this definition update?")
5. Click the Confirm button in the dialog to proceed

**Expected Result**:

- Apply button appears below the review panel
- Confirmation dialog opens before application
- Dialog displays human-readable confirmation message
- Dialog is dismissible (Cancel button works)
- Clicking Confirm proceeds with application

**Selectors Used**: `run-apply-button`, `run-apply-confirm-dialog`

**Invariants Verified**:

- Apply is only available when a definition is selected
- Confirmation step prevents accidental definition modification
- Dialog content clearly indicates what action is being confirmed

---

### Test Case 8: Verify Apply Result Summary

**Preconditions**:

- Apply confirmation dialog has been confirmed from Test Case 7
- Application is in progress

**Steps**:

1. Wait for the apply operation to complete (observe result panel appearance)
2. Verify the apply result panel is visible (selector `run-apply-result`)
3. Verify the result displays a summary (e.g., "Definition updated")
4. Verify the panel shows success state and updated entity count
5. Verify the panel does not show error messages

**Expected Result**:

- Apply operation completes without errors
- Result panel displays applied definition update
- Summary is human-readable and indicates success
- No error banners or failure messages appear
- Result panel indicates successful completion

**Selectors Used**: `run-apply-result`

**Invariants Verified**:

- Result panel appears only after successful application
- Result indicates success state (not error)
- Result persists in the run detail view

---

### Test Case 9: Navigate to Classes Page and Verify Updated Definition

**Preconditions**:

- Apply operation has completed successfully (from Test Case 8)
- Definition has been applied to the class
- User is on the run detail page/drawer

**Steps**:

1. Close the run detail drawer or navigate to `/app/schema/classes`
2. Wait for the classes page to load (selector `classes-page`)
3. Search or scroll to find the class whose definition was refined
4. Click on the class row to open its detail drawer
5. Verify the class detail drawer displays the updated definition
6. Verify the definition matches the candidate definition that was applied

**Expected Result**:

- Classes page loads successfully
- Target class is visible in the table
- Class detail drawer displays the updated definition
- Definition content matches the applied candidate definition
- No orphaned or incomplete class entries

**Selectors Used**: `classes-page`, `class-inspector`

**Invariants Verified**:

- Applied definition is persisted in the ontology
- Definition data is complete and not truncated
- Definition change is reflected immediately in the class inspector
- No duplicate class entries are created

---

## Coverage Analysis

### CRUD Coverage

- **Create**: Definition refinement candidates are generated by pipeline (Test Cases 4-5)
- **Read**: Definition candidates are read from run result (Test Cases 5-6), updated definition is read from class (Test Case 9)
- **Update**: Class definition is updated via pipeline application (Test Cases 7-9)
- **Delete**: Not covered in this plan
- **Execute**: Pipeline run is executed (Test Cases 2-4)

### Edge Cases

- **No candidates generated**: Definition refinement might return no candidates (empty state handling: selector `definition-refinement-empty`)
- **Current definition selection**: User selects current (non-refined) definition to keep existing (Test Case 6)
- **Idempotent application**: If the same run is applied twice, should only update once
- **Definition persistence**: Definition changes should persist across sessions
- **Class integrity**: Applying definition should not modify other class fields (name, domain, etc.)

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions — all waits are tied to observable state (loading state, result panel appearance, class visibility)
- ✓ No hardcoded UUIDs — run IDs and class IDs are retrieved from API responses
- ✓ No invented selectors — all selectors exist in registry or match registered patterns
- ✓ No vacuous assertions — all assertions verify specific, observable outcomes (definition content, selection state, result visibility)
- ✓ No text-based selectors for mutable content — all selectors use `data-testid` attributes, not UI text
- ✓ Proper cleanup — test data (class, taxonomy, scheme) created in preconditions should be cleaned up in `afterEach` via `clearTestData`

---

## Factory Usage

Factories needed for preconditions:

- **Taxonomy factory** (`createTaxonomy`): Create a test taxonomy
- **Concept Scheme factory** (`createConceptScheme`): Create a test concept scheme
- **Class factory** (`createClass`): Create a test class with an initial definition
- **Cleanup** (`clearTestData`): Delete all test data after test completes

Note: Pipeline types (definition_refinement) are assumed to exist as built-in system types.

---

## Open Questions

1. **Multiple candidates handling**: How many definition candidates does the pipeline typically generate? One, several, or many?

2. **Current definition display**: Should the current definition always be shown as the first radio option, or can user choose to keep it?

3. **Candidate ranking**: How are candidate definitions ranked or ordered in the review panel?

4. **Idempotency**: If the same run is applied twice, does the system allow it or prevent re-application?

5. **Definition versioning**: After applying a definition refinement, is the old definition retained in version history?

---

## Quality Gate Summary

- [x] Every selector listed exists in `ux/selector-registry.yaml` or matches a registered pattern
- [x] Every entity field referenced exists in API response types
- [x] The plan aligns with pipeline execution golden path workflows
- [x] CRUD coverage is explicit (Create, Read, Update, Execute)
- [x] Invariant validation is named (definition selection, refinement integrity, apply confirmation)
- [x] Anti-patterns acknowledged (no timeouts, no hardcoded IDs, no invented selectors)
- [x] Factory usage documented (taxonomy, scheme, class creation and cleanup)
