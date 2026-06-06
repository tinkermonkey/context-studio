# Test Plan: Schema Node Grounding Run, Review, and Apply

## Overview

This test validates the complete golden path for executing a schema node grounding pipeline, reviewing external reference candidates (groundings from DBpedia, ConceptNet, Wikidata, schema.org), accepting grounding candidates, and applying them to update entity groundings in the ontology. The user navigates to a Schema Grounding pipeline type, selects ontology elements to ground, configures external knowledge sources, waits for completion, reviews candidate groundings, and applies them while verifying that entity groundings are updated.

## Scope

- **Entities involved**: PipelineType (schema_grounding), PipelineRun, OntologyClass (with groundings), OntologyProperty
- **Pages involved**: `/app/pipelines`, `/app/pipelines/{pipelineType}/run`, `/app/schema/classes`
- **External dependencies**: Back-end API for pipeline execution, external knowledge sources (DBpedia, ConceptNet, Wikidata, schema.org)
- **API endpoints**:
  - `GET /api/pipeline-types` (list available pipeline types)
  - `POST /api/pipeline-runs` (create and execute grounding run)
  - `GET /api/pipeline-runs/{id}` (fetch run details and grounding candidates)
  - `POST /api/pipeline-runs/{id}/apply` (apply selected grounding candidates)
  - `GET /api/classes/{id}` (verify class groundings are updated)

## Test Cases

### Test Case 1: Navigate to Pipeline Hub and Locate Schema Grounding Pipeline Type

**Preconditions**:

- User is authenticated and has a workspace open
- The "Schema Node Grounding" pipeline type is available
- Ontology with at least one class exists (created via factory)

**Steps**:

1. Navigate to `/app/pipelines`
2. Wait for pipelines page to load (selector `pipelines-page`)
3. Verify the grid of pipeline type cards is visible (selector `pipeline-types-grid`)
4. Locate the "Schema Node Grounding" or "Schema Grounding" pipeline type card (selector `pipeline-type-card-schema_grounding`)
5. Verify the card displays the pipeline type name and description
6. Verify the "Run" button is visible and enabled (selector `pipeline-run-button-schema_grounding`)

**Expected Result**:

- Pipelines hub loads successfully
- Schema Grounding card is visible with correct name
- Run button is ready to interact

**Selectors Used**: `pipelines-page`, `pipeline-types-grid`, `pipeline-type-card-schema_grounding`, `pipeline-run-button-schema_grounding`

**Invariants Verified**:

- Pipeline hub displays all available pipeline types
- Schema Grounding type is properly labeled and accessible
- Run button is located on the correct card

---

### Test Case 2: Open Schema Grounding Wizard and Select Target Nodes

**Preconditions**:

- User is on the pipelines hub (`/app/pipelines`)
- Schema Grounding pipeline type card is visible (from Test Case 1)
- A test ontology with at least one class exists

**Steps**:

1. Click the "Run" button on the Schema Grounding card (selector `pipeline-run-button-schema_grounding`)
2. Wait for the wizard to open and load (selector `schema-grounding-wizard`)
3. Verify the wizard form is fully rendered
4. Locate the target nodes entity picker (selector `schema-grounding-nodes`)
5. Click on the nodes picker input to open the dropdown
6. Select one or more classes to be grounded (from the test ontology created in preconditions)
7. Verify the selected nodes are displayed in the picker

**Expected Result**:

- Wizard modal/page opens after clicking Run
- Form displays with expected fields
- Nodes picker dropdown opens and displays available classes
- Selected classes are shown in the picker field
- Form is ready for next step

**Selectors Used**: `pipeline-run-button-schema_grounding`, `schema-grounding-wizard`, `schema-grounding-nodes`

**Invariants Verified**:

- Multiple nodes can be selected
- Selection is retained until changed
- Wizard state is preserved during form navigation

---

### Test Case 3: Configure Knowledge Source Selection

**Preconditions**:

- Schema grounding wizard is open (from Test Case 2)
- Target nodes/classes have been selected

**Steps**:

1. Verify the knowledge sources checkboxes are visible (selector `schema-grounding-sources`)
2. Verify all available sources are displayed: DBpedia, ConceptNet, Wikidata, schema.org
3. Verify the DBpedia checkbox is visible (selector `schema-grounding-source-dbpedia`)
4. Verify the ConceptNet checkbox is visible (selector `schema-grounding-source-conceptnet`)
5. Verify the Wikidata checkbox is visible (selector `schema-grounding-source-wikidata`)
6. Verify the schema.org checkbox is visible (selector `schema-grounding-source-schema_org`)
7. Select at least one source (e.g., DBpedia and ConceptNet)

**Expected Result**:

- Knowledge sources section displays all four available sources
- Each source has a checkbox that can be toggled
- Selected sources are checked
- Multiple sources can be selected simultaneously
- Form is ready for submission

**Selectors Used**: `schema-grounding-sources`, `schema-grounding-source-dbpedia`, `schema-grounding-source-conceptnet`, `schema-grounding-source-wikidata`, `schema-grounding-source-schema_org`

**Invariants Verified**:

- At least one source must be selected (form validation)
- Sources can be toggled independently
- Selection state is retained

---

### Test Case 4: Submit Wizard and Wait for Grounding Execution

**Preconditions**:

- Schema grounding wizard is open
- Target nodes have been selected (from Test Case 2)
- At least one knowledge source has been selected (from Test Case 3)

**Steps**:

1. Verify the Submit button is enabled (selector `schema-grounding-submit`)
2. Click the Submit button
3. Wait for loading state to appear (selector `schema-grounding-loading`)
4. Verify the loading message indicates grounding is in progress
5. Wait for the run to complete by observing state changes (not fixed timeout)
6. Verify run status transitions to COMPLETED

**Expected Result**:

- Submit button is enabled when form is valid
- Loading state appears immediately after submission
- Pipeline execution starts and contacts external sources
- UI updates to show completion (not stuck in loading)
- No timeout or error during execution

**Selectors Used**: `schema-grounding-submit`, `schema-grounding-loading`

**Invariants Verified**:

- Loading state is visible during external API calls
- Execution completes within reasonable time
- Run ID is available for subsequent steps

---

### Test Case 5: Review Grounding Candidates

**Preconditions**:

- Pipeline run has completed successfully (status = COMPLETED)
- Grounding candidates are available in the run result
- Run detail view is displayed

**Steps**:

1. Verify the grounding review panel is visible (selector `grounding-review`)
2. Verify the panel displays grounding candidates organized by node/class
3. Verify each node shows candidate groundings from the selected sources
4. Verify each grounding candidate displays: source name, external reference URL, and confidence/relevance
5. Scroll through the grounding candidates to verify multiple candidates are displayed
6. Verify each grounding has accept/reject buttons visible (selectors match pattern `grounding-accept-*`, `grounding-reject-*`)

**Expected Result**:

- Grounding review panel renders with candidates organized by node
- Candidates display external references (URLs, IDs) from knowledge sources
- Accept/reject buttons are present for each candidate
- Panel is readable and scrollable
- Multiple candidates are shown for nodes

**Selectors Used**: `grounding-review`, `grounding-accept-*`, `grounding-reject-*`

**Invariants Verified**:

- Only candidates from selected sources are displayed
- External references are valid and properly formatted
- Each candidate has accept/reject controls

---

### Test Case 6: Accept Grounding Candidates

**Preconditions**:

- Grounding review panel is open (from Test Case 5)
- Grounding candidates are visible

**Steps**:

1. Select one or more grounding candidates by clicking the Accept button (selector pattern `grounding-accept-*`)
2. Verify the accepted candidate is highlighted or visually indicated as accepted
3. Verify the acceptance state persists as you scroll and review other candidates
4. For nodes with multiple candidates, verify you can accept one or reject others
5. Verify that accepting one candidate does not auto-accept others

**Expected Result**:

- Accept buttons are clickable and trigger acceptance
- Accepted candidates are visually indicated (checkmark, highlight, etc.)
- Acceptance state is tracked independently per candidate
- User can mix accept/reject decisions across different candidates
- Form is ready for application

**Selectors Used**: `grounding-accept-*`, `grounding-reject-*`

**Invariants Verified**:

- Accept state is recorded for each candidate
- Rejecting a candidate clears its acceptance
- Multiple candidates can be accepted for different nodes

---

### Test Case 7: Click Apply Button and Confirm Application

**Preconditions**:

- Grounding review panel is open
- At least one grounding candidate has been accepted
- Apply controls section is visible (selector `run-apply-section`)

**Steps**:

1. Verify the Apply button is visible and enabled (selector `run-apply-button`)
2. Click the Apply button
3. Wait for confirmation dialog to appear (selector `run-apply-confirm-dialog`)
4. Verify the dialog displays the count of grounding candidates to be applied (e.g., "Apply 3 groundings?")
5. Click the Confirm button in the dialog to proceed

**Expected Result**:

- Apply button appears below the review panel
- Confirmation dialog opens before application
- Dialog shows human-readable summary of what will be applied
- Dialog can be dismissed (Cancel button available)
- Clicking Confirm proceeds with application

**Selectors Used**: `run-apply-button`, `run-apply-confirm-dialog`

**Invariants Verified**:

- Apply is only available when at least one candidate is accepted
- Apply button is disabled if no acceptances are made
- Confirmation step prevents accidental modification

---

### Test Case 8: Verify Apply Result Summary

**Preconditions**:

- Apply confirmation dialog has been confirmed from Test Case 7
- Application is in progress

**Steps**:

1. Wait for the apply operation to complete (observe result panel appearance)
2. Verify the apply result panel is visible (selector `run-apply-result`)
3. Verify the result displays a summary (e.g., "Applied 3 groundings to 2 nodes")
4. Verify the panel shows applied count and indicates success
5. Verify no error messages appear (success state)

**Expected Result**:

- Apply operation completes without errors
- Result panel displays applied grounding count
- Summary is human-readable
- No error banners or failure messages
- Result indicates successful completion

**Selectors Used**: `run-apply-result`

**Invariants Verified**:

- Applied count matches accepted candidates from review
- Result panel appears only after successful application
- Result persists (not cleared after brief delay)

---

### Test Case 9: Navigate to Classes Page and Verify Updated Groundings

**Preconditions**:

- Apply operation has completed successfully (from Test Case 8)
- Grounding candidates have been applied to classes
- User is on the run detail page/drawer

**Steps**:

1. Close the run detail drawer or navigate to `/app/schema/classes`
2. Wait for the classes page to load (selector `classes-page`)
3. Search or scroll to find one of the grounded classes by name
4. Verify the class appears in the classes table
5. Click on the class row to open its detail drawer
6. Verify the class detail drawer displays groundings section
7. Verify the applied grounding(s) are visible with external reference URL

**Expected Result**:

- Classes page loads successfully
- Grounded classes are visible in the table
- Class detail drawer displays the groundings that were applied
- Groundings show external references (URLs, IDs)
- All grounding data is present and valid

**Selectors Used**: `classes-page`, `class-inspector`

**Invariants Verified**:

- Applied groundings are persisted in the classes
- Groundings show correct external references
- No duplicate groundings are created
- Grounding data matches applied candidates

---

### Test Case 10: Verify Multiple Nodes Have Been Grounded

**Preconditions**:

- Applied groundings have been verified on the Classes page (from Test Case 9)
- Multiple nodes were selected in the grounding wizard (from Test Case 2)

**Steps**:

1. Close the first class detail drawer
2. Search for another class that was part of the grounding run
3. Click on the second class to open its detail drawer
4. Verify the second class also displays groundings
5. If the second class had multiple candidates and mixed accept/reject, verify only accepted candidates are shown
6. Verify grounding source matches the selected sources from the wizard

**Expected Result**:

- Multiple classes can be grounded in a single run
- Each grounded class displays only the accepted groundings
- Groundings are consistent with the knowledge sources selected in the wizard
- All applied groundings are persistent and queryable

**Selectors Used**: `class-inspector`

**Invariants Verified**:

- All targeted nodes that had accepted candidates are grounded
- Nodes without accepted candidates remain ungrounded
- Grounding data is consistent across nodes

---

## Coverage Analysis

### CRUD Coverage

- **Create**: Groundings are created via pipeline application (Test Cases 7-8)
- **Read**: Grounding candidates are read from run result (Test Cases 5-6), applied groundings are read from classes (Test Cases 9-10)
- **Update**: Not applicable in this test (groundings are new, not modified existing ones)
- **Delete**: Not covered in this plan
- **Execute**: Pipeline run is executed (Test Cases 2-4)

### Edge Cases

- **No grounding candidates**: Grounding might return no results for some or all nodes (empty state handling: selector `grounding-empty`)
- **Multiple sources conflict**: Different sources might propose different groundings for the same node (user must select one)
- **External source unavailability**: One or more external sources might be temporarily unavailable during execution
- **Mixed accept/reject**: User accepts some candidates and rejects others for the same node
- **Empty node selection**: Wizard should require at least one node to be selected

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions — all waits are tied to observable state (loading, result panel, class visibility)
- ✓ No hardcoded UUIDs — run IDs, class IDs, and candidate keys are retrieved from API responses
- ✓ No invented selectors — all selectors exist in registry or match registered patterns
- ✓ No vacuous assertions — all assertions verify specific, observable outcomes (grounding counts, URLs, source names)
- ✓ No text-based selectors for mutable content — all selectors use `data-testid` attributes
- ✓ Proper cleanup — test data (ontology, classes) created in preconditions should be cleaned up in `afterEach` via `clearTestData`

---

## Factory Usage

Factories needed for preconditions:

- **Taxonomy factory** (`createTaxonomy`): Create a test taxonomy
- **Concept Scheme factory** (`createConceptScheme`): Create a test concept scheme
- **Class factory** (`createClass`): Create one or more test classes in the scheme
- **Cleanup** (`clearTestData`): Delete all test data after test completes

Note: Pipeline types (schema_grounding) are assumed to exist as built-in system types. External knowledge sources (DBpedia, ConceptNet, etc.) are managed by the backend.

---

## Open Questions

1. **Source availability**: If an external knowledge source is unavailable during grounding execution, does the pipeline fail, retry, or skip that source gracefully?

2. **Candidate ranking**: How are multiple grounding candidates ranked for the same node? By relevance score, source priority, or alphabetical?

3. **Confidence scores**: Are grounding candidates displayed with confidence/relevance scores from the source? Should the user see these scores in the review panel?

4. **Batch grounding idempotency**: If the same run is applied twice, are groundings duplicated or is application idempotent?

5. **Existing groundings replacement**: If a class already has a grounding, does applying a new grounding overwrite it or add it as an additional grounding?

---

## Quality Gate Summary

- [x] Every selector listed exists in `ux/selector-registry.yaml` or matches a registered pattern
- [x] Every entity field referenced exists in API response types
- [x] The plan aligns with pipeline execution golden path workflows
- [x] CRUD coverage is explicit (Create, Read, Execute)
- [x] Invariant validation is named (grounding integrity, source handling, apply confirmation)
- [x] Anti-patterns acknowledged (no timeouts, no hardcoded IDs, no invented selectors)
- [x] Factory usage documented (taxonomy, scheme, class creation and cleanup)
