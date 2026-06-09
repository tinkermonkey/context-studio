# Test Plan: Connection Refinement Run, Review, and Apply

## Overview

This test validates the complete golden path for executing a connection refinement pipeline, reviewing proposed relationship deltas (additions or updates to existing relationships), accepting or rejecting connection changes, and applying them to update the ontology's relationship graph. The user navigates to the Connection Refinement pipeline type, configures with a scope class that needs relationship refinement, waits for completion, reviews proposed connection deltas, accepts changes, and applies them to verify that relationships are added or updated.

## Scope

- **Entities involved**: PipelineType (connection_refinement), PipelineRun, Relationship (added or updated)
- **Pages involved**: `/app/pipelines`, `/app/pipelines/{pipelineType}/run`, `/app/schema/relationships`
- **External dependencies**: Back-end API for pipeline execution and connection refinement
- **API endpoints**:
  - `GET /api/pipeline-types` (list available pipeline types)
  - `POST /api/pipeline-runs` (create and execute run)
  - `GET /api/pipeline-runs/{id}` (fetch run details and connection deltas)
  - `POST /api/pipeline-runs/{id}/apply` (apply selected connection deltas)
  - `GET /api/relationships` (verify added/updated relationships)

## Test Cases

### Test Case 1: Navigate to Pipeline Hub and Locate Connection Refinement Pipeline Type

**Preconditions**:

- User is authenticated and has a workspace open
- The "Connection Refinement" pipeline type is available
- Ontology with at least one class exists (created via factory)

**Steps**:

1. Navigate to `/app/pipelines`
2. Wait for pipelines page to load (selector `pipelines-page`)
3. Verify the grid of pipeline type cards is visible (selector `pipeline-types-grid`)
4. Locate the "Connection Refinement" pipeline type card (selector `pipeline-type-card-connection_refinement`)
5. Verify the card displays the pipeline type name and description
6. Verify the "Run" button is visible and enabled (selector `pipeline-run-button-connection_refinement`)

**Expected Result**:

- Pipelines hub loads successfully
- Connection Refinement pipeline type card is visible with correct name
- Run button is ready to interact

**Selectors Used**: `pipelines-page`, `pipeline-types-grid`, `pipeline-type-card-connection_refinement`, `pipeline-run-button-connection_refinement`

**Invariants Verified**:

- Pipeline hub displays all available pipeline types
- Connection Refinement type is properly labeled and accessible
- Run button is located on the correct card

---

### Test Case 2: Open Connection Refinement Wizard and Select Scope Class

**Preconditions**:

- User is on the pipelines hub (`/app/pipelines`)
- Connection Refinement pipeline type card is visible (from Test Case 1)
- A test ontology with at least one class exists (created via factory in preconditions)

**Steps**:

1. Click the "Run" button on the Connection Refinement card (selector `pipeline-run-button-connection_refinement`)
2. Wait for the wizard to open and load (selector `connection-refinement-wizard`)
3. Verify the wizard form is fully rendered
4. Locate the scope class entity picker (selector `connection-refinement-scope`)
5. Click on the picker input to open the class selection dropdown
6. Select a test class as the scope for connection refinement
7. Verify the selected class is displayed in the picker

**Expected Result**:

- Wizard modal/page opens after clicking Run
- Form displays with expected fields
- Scope picker dropdown opens and displays available classes
- Selected class is shown in the picker field
- Form is ready for next step

**Selectors Used**: `pipeline-run-button-connection_refinement`, `connection-refinement-wizard`, `connection-refinement-scope`

**Invariants Verified**:

- Only one scope class can be selected at a time
- Selection is retained until explicitly changed
- Wizard state is preserved during form navigation

---

### Test Case 3: Review Current Connection Context

**Preconditions**:

- Connection refinement wizard is open (from Test Case 2)
- A scope class has been selected

**Steps**:

1. Verify the neighborhood/context preview panel is visible (selector `connection-refinement-neighborhood`)
2. Verify the panel displays current connections for the scope class in table format
3. Verify the table shows existing relationships (source, property type, target)
4. Scroll through the neighborhood table to see multiple current connections
5. Confirm that the context information is loaded

**Expected Result**:

- Neighborhood table displays current relationships for the scope class
- Each row shows source class, property type, and target class
- Table is readable and shows all current connections
- Context helps inform what connections might need refinement
- Form is ready for submission

**Selectors Used**: `connection-refinement-neighborhood`

**Invariants Verified**:

- Neighborhood context accurately reflects existing relationships
- Table properly displays relationship structure (source, property, target)
- Current connections are loaded and visible

---

### Test Case 4: Submit Wizard and Wait for Pipeline Execution

**Preconditions**:

- Connection refinement wizard is open with a scope class selected
- The backend is available and can process the request

**Steps**:

1. Verify the Submit button is enabled (selector `connection-refinement-submit`)
2. Click the Submit button
3. Wait for loading state to appear (selector `connection-refinement-loading`)
4. Verify the loading message indicates processing has begun
5. Wait for the run to complete by observing state changes (not fixed timeout)
6. Observe the run status transitions to COMPLETED

**Expected Result**:

- Submit button is enabled when form is valid
- Loading state appears immediately after submission
- Pipeline execution starts and progresses to completion
- UI updates to show run completion status (not stuck in loading state)
- No timeout or error appears during execution

**Selectors Used**: `connection-refinement-submit`, `connection-refinement-loading`

**Invariants Verified**:

- Loading state is displayed during execution
- Execution completes without hanging
- Run ID is generated and available for subsequent steps

---

### Test Case 5: Review Connection Deltas in Candidate Table

**Preconditions**:

- Pipeline run has completed successfully (status = COMPLETED)
- Connection delta candidates are available in the run result
- Run detail view is displayed

**Steps**:

1. Verify the connection refinement review panel is visible (selector `connection-refinement-review`)
2. Verify the panel displays connection deltas (proposed new or modified relationships)
3. Verify each delta row shows: operation type (add/update), source class, property type, target class
4. Verify each delta row is selectable (checkboxes are present)
5. Scroll through the delta table to verify multiple deltas are displayed
6. Verify each delta has accept/reject buttons (selectors match pattern `connection-accept-*`, `connection-reject-*`)

**Expected Result**:

- Connection refinement review panel renders with table interface
- Table displays relationship deltas organized by operation type (add, update, etc.)
- Each row has a checkbox for selection
- Accept/reject buttons are present for each delta
- Panel is readable and scrollable
- Multiple deltas are shown

**Selectors Used**: `connection-refinement-review`, `connection-accept-*`, `connection-reject-*`

**Invariants Verified**:

- Each delta clearly indicates its operation type (add vs. update)
- Relationship structure is complete (source, property, target)
- Each delta has accept/reject controls

---

### Test Case 6: Accept Connection Deltas

**Preconditions**:

- Connection refinement review panel is open (from Test Case 5)
- Connection deltas are visible

**Steps**:

1. Select one or more connection deltas by clicking the Accept button (selector pattern `connection-accept-*`)
2. Verify the accepted delta is highlighted or visually indicated as accepted
3. Verify the acceptance state persists as you scroll and review other deltas
4. For multiple deltas with mixed operations, verify you can accept some and reject others
5. Verify that accepting one delta does not auto-accept others

**Expected Result**:

- Accept buttons are clickable and trigger acceptance
- Accepted deltas are visually indicated (checkmark, highlight, etc.)
- Acceptance state is tracked independently per delta
- User can mix accept/reject decisions across different deltas
- Form is ready for application

**Selectors Used**: `connection-accept-*`, `connection-reject-*`

**Invariants Verified**:

- Accept state is recorded for each delta
- Rejecting a delta clears its acceptance
- Multiple deltas can be accepted for different relationships

---

### Test Case 7: Click Apply Button and Confirm Application

**Preconditions**:

- Connection refinement review panel is open
- At least one connection delta has been accepted
- Apply controls section is visible (selector `run-apply-section`)

**Steps**:

1. Verify the Apply button is visible and enabled (selector `run-apply-button`)
2. Click the Apply button
3. Wait for confirmation dialog to appear (selector `run-apply-confirm-dialog`)
4. Verify the dialog displays the count of deltas to be applied (e.g., "Apply 3 connection changes?")
5. Click the Confirm button in the dialog to proceed

**Expected Result**:

- Apply button appears below the review table
- Confirmation dialog opens before application
- Dialog shows human-readable summary of what will be applied
- Dialog can be dismissed (Cancel button available)
- Clicking Confirm proceeds with application

**Selectors Used**: `run-apply-button`, `run-apply-confirm-dialog`

**Invariants Verified**:

- Apply is only available when at least one delta is accepted
- Apply button is disabled if no acceptances are made
- Confirmation step prevents accidental relationship modification

---

### Test Case 8: Verify Apply Result Summary

**Preconditions**:

- Apply confirmation dialog has been confirmed from Test Case 7
- Application is in progress

**Steps**:

1. Wait for the apply operation to complete (observe result panel appearance)
2. Verify the apply result panel is visible (selector `run-apply-result`)
3. Verify the result displays a summary (e.g., "Applied 3 relationship changes")
4. Verify the panel shows applied delta count and indicates success
5. Verify the panel does not show error messages

**Expected Result**:

- Apply operation completes without errors
- Result panel displays applied delta count
- Summary is human-readable and indicates success
- No error banners or failure messages appear
- Result panel indicates successful completion

**Selectors Used**: `run-apply-result`

**Invariants Verified**:

- Applied count matches accepted deltas from review
- Result panel appears only after successful application
- Result persists in the run detail view

---

### Test Case 9: Navigate to Relationships Page and Verify Applied Changes

**Preconditions**:

- Apply operation has completed successfully (from Test Case 8)
- Connection deltas have been applied to the ontology
- User is on the run detail page/drawer

**Steps**:

1. Close the run detail drawer or navigate to `/app/schema/relationships`
2. Wait for the relationships page to load (selector `relationships-page`)
3. Search or filter for relationships involving the scope class from the wizard
4. Verify new relationships are visible in the table (for "add" deltas)
5. Click on a new relationship row to inspect its details
6. Verify the relationship shows correct source class, property type, and target class

**Expected Result**:

- Relationships page loads successfully
- Newly added/updated relationships are visible in the table
- Relationship data is complete and correct
- Relationships can be inspected and show correct details
- No orphaned or incomplete relationship entries

**Selectors Used**: `relationships-page`, `schema-row-*`

**Invariants Verified**:

- Applied relationships are persisted in the ontology
- Relationship data is complete (source, property, target)
- No duplicate relationships are created
- Relationship references are valid (classes exist)

---

### Test Case 10: Verify Updated Relationships on Class Page

**Preconditions**:

- Applied relationships have been verified on the Relationships page (from Test Case 9)
- Multiple deltas involving the scope class were applied

**Steps**:

1. Navigate to `/app/schema/classes`
2. Search for the scope class that was used in the connection refinement wizard
3. Click on the class row to open its detail drawer
4. Verify the class shows updated connections in the neighborhood or relationship section
5. Verify the new/updated relationships appear in the class context

**Expected Result**:

- Classes page loads successfully
- Scope class is visible in the table
- Class detail drawer shows updated relationships
- New relationships appear in the class context
- Relationship changes are consistent and persistent

**Selectors Used**: `classes-page`, `class-inspector`

**Invariants Verified**:

- Applied relationships are reflected in class views
- Class context shows all newly added relationships
- Relationship bidirectionality is maintained (if applicable)
- All applied changes are persistent

---

## Coverage Analysis

### CRUD Coverage

- **Create**: New relationships are created via pipeline application for "add" deltas (Test Cases 7-9)
- **Read**: Connection deltas are read from run result (Test Cases 5-6), applied relationships are read from pages (Test Cases 9-10)
- **Update**: Existing relationships are updated via pipeline application for "update" deltas (Test Cases 7-9)
- **Delete**: Not covered in this plan
- **Execute**: Pipeline run is executed (Test Cases 2-4)

### Edge Cases

- **No deltas generated**: Connection refinement might return no deltas (empty state handling: selector `connection-refinement-empty`)
- **Mixed operations**: Some deltas add new relationships, others update existing ones (Test Case 6)
- **Idempotent application**: If the same run is applied twice, should only apply once
- **Relationship cardinality**: Multiple relationships of the same type between classes might be proposed
- **Bidirectional relationships**: If relationships are bidirectional, both directions should be handled

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions — all waits are tied to observable state (loading state, result panel appearance, relationship visibility)
- ✓ No hardcoded UUIDs — run IDs, class IDs, and delta keys are retrieved from API responses
- ✓ No invented selectors — all selectors exist in registry or match registered patterns
- ✓ No vacuous assertions — all assertions verify specific, observable outcomes (delta counts, relationship structure, operation types)
- ✓ No text-based selectors for mutable content — all selectors use `data-testid` attributes
- ✓ Proper cleanup — test data (class, taxonomy, scheme) created in preconditions should be cleaned up in `afterEach` via `clearTestData`

---

## Factory Usage

Factories needed for preconditions:

- **Taxonomy factory** (`createTaxonomy`): Create a test taxonomy
- **Concept Scheme factory** (`createConceptScheme`): Create a test concept scheme
- **Class factory** (`createClass`): Create one or more test classes in the scheme
- **Property Definition factory** (`createPropertyDefinition`): Create property definitions for proposed relationships
- **Cleanup** (`clearTestData`): Delete all test data after test completes

Note: Pipeline types (connection_refinement) are assumed to exist as built-in system types.

---

## Open Questions

1. **Delta types**: Does the pipeline generate only "add" deltas, or also "update" and "delete" deltas?

2. **Cardinality constraints**: Can there be multiple relationships of the same property type between two classes?

3. **Bidirectionality**: If a relationship is refined, does the pipeline handle bidirectional updates automatically?

4. **Candidate ranking**: How are proposed deltas ranked or ordered in the review panel?

5. **Idempotency**: If the same run is applied twice, does the system allow duplicate relationship creation or prevent it?

6. **Existing relationship replacement**: If an "update" delta is applied to an existing relationship, does it modify the relationship in-place or create a new one?

---

## Quality Gate Summary

- [x] Every selector listed exists in `ux/selector-registry.yaml` or matches a registered pattern
- [x] Every entity field referenced exists in API response types
- [x] The plan aligns with pipeline execution golden path workflows
- [x] CRUD coverage is explicit (Create, Read, Update, Execute)
- [x] Invariant validation is named (delta acceptance, relationship integrity, apply confirmation)
- [x] Anti-patterns acknowledged (no timeouts, no hardcoded IDs, no invented selectors)
- [x] Factory usage documented (taxonomy, scheme, class, property creation and cleanup)
