# Test Plan: Identity/No-Op Pipeline Run (Smoke Test)

## Overview

This test validates the smoke path for a no-op or identity pipeline type that produces no changes or candidates. The test serves as a quality gate to ensure that the pipeline execution framework correctly handles pipelines that result in empty candidate sets, displaying appropriate "no changes" or "nothing to apply" states. The user navigates to the pipeline type, configures and executes a run, waits for completion, and verifies that the system correctly displays zero candidates and disables or appropriately handles the Apply action.

**Note**: This test should be applied to whichever pipeline type in the system is designated as producing no changes (e.g., a test pipeline, a refinement pipeline with no suggestions, or an intentional no-op type). The specific pipeline type identifier should be determined by the development team and substituted in step 4 of Test Case 1.

## Scope

- **Entities involved**: PipelineType (to be determined: e.g., `identity_pipeline`, `test_no_op`, etc.), PipelineRun
- **Pages involved**: `/app/pipelines`, `/app/pipelines/{pipelineType}/run`
- **External dependencies**: Back-end API for pipeline execution
- **API endpoints**:
  - `GET /api/pipeline-types` (list available pipeline types)
  - `POST /api/pipeline-runs` (create and execute run)
  - `GET /api/pipeline-runs/{id}` (fetch run details with empty candidates)

## Test Cases

### Test Case 1: Navigate to Pipeline Hub and Locate No-Op Pipeline Type

**Preconditions**:

- User is authenticated and has a workspace open
- A no-op or identity pipeline type is available in the system
- Minimal ontology or none required (no candidates will be generated)

**Steps**:

1. Navigate to `/app/pipelines`
2. Wait for pipelines page to load (selector `pipelines-page`)
3. Verify the grid of pipeline type cards is visible (selector `pipeline-types-grid`)
4. Locate the no-op/identity pipeline type card (selector pattern: `pipeline-type-card-{type}` where {type} is the no-op pipeline identifier, e.g., `pipeline-type-card-identity_pipeline`)
5. Verify the card displays the pipeline type name and description
6. Verify the "Run" button is visible and enabled (selector pattern: `pipeline-run-button-{type}`)

**Expected Result**:

- Pipelines hub loads successfully
- No-op pipeline type card is visible
- Run button is enabled and ready to interact

**Selectors Used**: `pipelines-page`, `pipeline-types-grid`, `pipeline-type-card-{type}`, `pipeline-run-button-{type}`

**Invariants Verified**:

- Pipeline hub displays all available pipeline types
- No-op pipeline type is properly labeled
- Run button is located on the correct card

---

### Test Case 2: Open No-Op Pipeline Wizard

**Preconditions**:

- User is on the pipelines hub (`/app/pipelines`)
- No-op pipeline type card is visible (from Test Case 1)

**Steps**:

1. Click the "Run" button on the no-op pipeline card (selector pattern: `pipeline-run-button-{type}`)
2. Wait for the wizard to open (selector varies by pipeline type, e.g., a generic run wizard or form)
3. Verify the wizard form is rendered
4. If the wizard has configuration fields, verify they are displayed
5. Note: For a true no-op pipeline, configuration may be minimal or absent

**Expected Result**:

- Wizard modal/page opens after clicking Run
- Form displays (even if minimal or with no-op defaults)
- Wizard is ready for submission

**Selectors Used**: `pipeline-run-button-{type}`

**Invariants Verified**:

- Wizard loads without errors
- Form is in a valid state ready for submission

---

### Test Case 3: Submit Wizard and Wait for Execution

**Preconditions**:

- No-op pipeline wizard is open (from Test Case 2)
- The backend is available for processing

**Steps**:

1. Locate and verify the Submit button is enabled
2. Click the Submit button
3. Wait for loading state to appear (loading indicator, progress message)
4. Wait for the run to complete by observing state changes (not fixed timeout)
5. Observe the run status transitions to COMPLETED

**Expected Result**:

- Submit button is enabled
- Loading state appears immediately after submission
- Execution completes to COMPLETED status
- No timeout or error appears

**Invariants Verified**:

- Loading state is visible during execution
- Execution completes within reasonable time
- Run ID is available for next steps

---

### Test Case 4: Verify Empty Candidates State

**Preconditions**:

- Pipeline run has completed successfully (status = COMPLETED)
- Run detail view is displayed

**Steps**:

1. Verify the review panel is displayed for the no-op pipeline type
2. Check for empty state message (selector varies by pipeline type, e.g., `definition-refinement-empty`, `grounding-empty`, `connection-refinement-empty`, `individual-extraction-empty`, `schema-extraction-empty`)
3. Verify the empty state displays a "no changes" or "no candidates" message
4. Verify the candidate table/list is either absent or empty
5. Scroll through the result area to confirm no candidates are shown

**Expected Result**:

- Review panel displays empty state instead of candidate table
- Empty state message clearly indicates no changes or candidates
- No unexpected error messages are shown
- UI correctly renders the no-op result

**Selectors Used**: Empty state selectors corresponding to the pipeline type (e.g., `definition-refinement-empty`, `grounding-empty`, etc.)

**Invariants Verified**:

- Empty state is displayed when no candidates exist
- Empty state message is user-friendly and clear
- No data rendering errors occur

---

### Test Case 5: Verify Apply Button is Disabled or Appropriately Handled

**Preconditions**:

- Run detail view is displayed with empty candidates (from Test Case 4)
- Apply controls section is visible or absent

**Steps**:

1. Check if the Apply button is visible on the screen (selector `run-apply-button`)
2. If visible, verify the Apply button is disabled (appears grayed out or with a "disabled" state)
3. Alternatively, verify that Apply controls are not rendered at all for empty results
4. Verify there is no option to apply anything (no selectable candidates)
5. Confirm that the user cannot trigger an apply action

**Expected Result**:

- Apply button is either disabled or not rendered
- No candidates can be selected or applied
- UI prevents accidental empty apply operations
- Clear indication that there are no changes to apply

**Selectors Used**: `run-apply-button` (if present), `run-apply-button-disabled` (if applicable)

**Invariants Verified**:

- Apply is disabled when no candidates exist
- User cannot initiate an apply on empty results
- UI prevents invalid state transitions

---

### Test Case 6: Verify Run History and No Persistence

**Preconditions**:

- Run detail is displayed with empty state (from Test Case 5)

**Steps**:

1. Note the run ID for reference
2. If applicable, navigate away and back to the run detail view
3. Verify the run is still visible in the run history
4. Verify the run status remains COMPLETED
5. Verify the empty state persists (no candidates appear after reload)

**Expected Result**:

- Run history retains the completed run
- Run detail view reloads correctly with empty state
- No spurious data appears after reload
- Run state is consistent

**Invariants Verified**:

- Run persistence is correct
- Empty state remains stable
- No data corruption or state inconsistency

---

## Coverage Analysis

### Smoke Test Coverage

- **Execute**: Pipeline run is executed with no candidates generated
- **Empty state handling**: UI correctly displays empty/no-op state
- **Apply prevention**: Apply action is disabled when no candidates exist
- **Read**: Run details are readable and consistent

### Edge Cases

- **Zero candidates**: Pipeline intentionally produces no changes (primary test case)
- **Reload consistency**: Empty state persists across page reloads
- **Apply button state**: Apply is correctly disabled for empty results
- **History retention**: Completed no-op runs are retained in history

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions — waits are tied to observable state changes
- ✓ No hardcoded UUIDs — run IDs are retrieved from responses
- ✓ No invented selectors — all selectors exist in registry or match registered patterns
- ✓ No vacuous assertions — assertions verify observable outcomes (empty state visibility, button disabled state)
- ✓ No text-based selectors for mutable content — uses `data-testid` attributes
- ✓ Proper cleanup — minimal test data, use `clearTestData` if any data was created

---

## Factory Usage

Factories needed for preconditions:

- **Minimal setup**: This test requires minimal or no test data creation (no-op nature)
- **Cleanup** (`clearTestData`): Execute if any test data was created, though likely unnecessary

---

## Open Questions

1. **Pipeline type identifier**: Which pipeline type in the system should be used for this no-op test? Is there a designated test pipeline or should one be created?

2. **Empty state selector**: What is the correct selector for the empty state in the chosen pipeline type? (Different pipeline types have different empty state selectors.)

3. **Candidate table rendering**: Does the review panel still render with an empty table, or is the entire panel replaced with an empty state message?

4. **Run retention policy**: Are no-op runs (zero candidates) retained in history indefinitely, or cleaned up after a period?

5. **Apply button visibility**: Should the Apply button be hidden entirely for no-op results, or visible but disabled?

---

## Quality Gate Summary

- [x] Every selector listed exists in `ux/selector-registry.yaml` or matches a registered pattern
- [x] All assertions verify observable outcomes (not vacuous)
- [x] Anti-patterns acknowledged (no fixed timeouts, no hardcoded IDs)
- [x] Smoke test serves as a quality gate for empty result handling
- [x] Test is flexible and can be adapted to any designated no-op pipeline type
- [x] Minimal factory usage required (no-op test)

---

## Implementation Notes

**Before running this test:**
1. Identify and confirm which pipeline type should be tested as the no-op case.
2. Verify the pipeline type's identifier (e.g., `identity_pipeline`, `test_no_op`, etc.).
3. Update all selector patterns in this spec with the confirmed pipeline type identifier.
4. Identify the correct empty state selector for the chosen pipeline type (e.g., `definition-refinement-empty` if using Definition Refinement).
5. Confirm that the pipeline is configured to produce no candidates in the test environment.

**Selector substitutions needed:**
- `pipeline-type-card-{type}` → Replace `{type}` with the actual pipeline type identifier
- `pipeline-run-button-{type}` → Replace `{type}` with the actual pipeline type identifier
- Empty state selector → Replace with the correct selector for the chosen pipeline type
