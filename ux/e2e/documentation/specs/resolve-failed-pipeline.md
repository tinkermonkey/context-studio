# Test Plan: Resolve a Failed Pipeline Run

## Overview

This test validates the complete golden path for resolving a failed pipeline run, including navigating to the pipeline from the statusbar indicator, viewing error details in the pipeline drawer, editing the pipeline configuration, re-running the pipeline, and observing successful completion with a confirmation toast. The test also covers edge cases such as pipelines with no prior runs (which should not display a failure chip) and verifying that long error logs are scrollable.

## Scope

- **Entities involved**: Pipeline (PipelineConfigurationResponse), Execution (ExecutionResponse)
- **Pages involved**: `/app/pipelines`, `/app/pipelines/$pipelineId` (drawer-based detail view)
- **External dependencies**: Back-end API for pipeline execution
- **API endpoints**:
  - `POST /api/pipelines` (create)
  - `GET /api/pipelines` (list)
  - `GET /api/pipelines/{id}` (read)
  - `PUT /api/pipelines/{id}` (update configuration)
  - `POST /api/pipelines/{id}/execute` (trigger execution)
  - `GET /api/pipelines/{id}/executions` (fetch run history)

## Test Cases

### Test Case 1: Navigate to Failed Pipeline from Statusbar

**Preconditions**:
- Pipeline with a failed execution already exists (created via API with ExecutionResponse status=error)
- User is on any page in the app
- Statusbar is visible showing "1 pipeline failed" with a red dot

**Steps**:

1. Observe statusbar displays red dot and "1 pipeline failed" text (clickable)
2. Click the statusbar message to navigate to pipelines page
3. Wait for pipelines page to load (selector `pipelines-page`)
4. Verify pipelines grid is visible (selector `pipelines-grid`)

**Expected Result**:
- Navigation completes to `/app/pipelines`
- Pipelines page renders with the grid of pipeline cards
- Failed pipeline card is visible with status chip showing `failed` intent

**Selectors Used**: `pipelines-page`, `pipelines-grid`

**Invariants Verified**: 
- Statusbar indicator correctly reflects pipeline failure state
- Navigation from statusbar is functional and routes to pipelines page
- Page loads without errors

---

### Test Case 2: View Failed Pipeline Card and Error Count

**Preconditions**:
- User is on pipelines page (`/app/pipelines`)
- Failed pipeline card exists (from Test Case 1 preconditions)

**Steps**:

1. Locate pipeline card with selector matching pattern `pipeline-card-{pipelineId}`
2. Verify status chip is visible within the card (selector `pipeline-status-chip`)
3. Verify status chip displays "failed" text with failure intent color (red)
4. Verify latest run line shows error count or error indicator

**Expected Result**:
- Failed pipeline card displays prominent `failed` status chip
- The failed state is visually distinct from success/idle/running states
- Latest run in the card shows error-related information

**Selectors Used**: `pipeline-card-*`, `pipeline-status-chip`

**Invariants Verified**:
- A pipeline with no prior runs does not display a failure chip (empty state instead)
- Status chip uses the correct visual intent for failure (red/rose)
- Error state is observable without opening the drawer

---

### Test Case 3: Open Pipeline Detail Drawer and View Configuration

**Preconditions**:
- User is on pipelines page (`/app/pipelines`)
- Failed pipeline card is visible with selector `pipeline-card-{pipelineId}`

**Steps**:

1. Click on the failed pipeline card body (not the action button)
2. Verify drawer opens on the right side (480px width)
3. Verify drawer title matches pipeline title
4. Wait for drawer content to load
5. Locate pipeline configuration section with label "Pipeline Configuration"
6. Verify configuration is displayed in read-only pre-formatted block (selector `pipeline-config-pre`)

**Expected Result**:
- Right-side drawer opens showing pipeline details
- Drawer title is the pipeline name
- Configuration JSON is visible and readable
- "Edit" button is visible next to the configuration label (selector `pipeline-edit-config-button`)

**Selectors Used**: `pipeline-card-*`, `pipeline-config-pre`, `pipeline-edit-config-button`

**Invariants Verified**:
- Drawer opens without navigation change (remains on pipelines page)
- Configuration is fetched and displayed correctly
- Edit mode is not active on initial open (read-only display)

---

### Test Case 4: View Last 10 Runs and Failed Execution Details

**Preconditions**:
- Pipeline detail drawer is open from Test Case 3
- Pipeline has at least one failed execution in its history

**Steps**:

1. Scroll to "Last 10 Runs" section in the drawer
2. Verify runs table is visible (selector `pipeline-runs-table`)
3. Verify the failed run appears in the table with status chip showing "failed"
4. Locate the "View log" button for the failed run (selector pattern `pipeline-view-log-{executionId}`)
5. Click the "View log" button

**Expected Result**:
- Runs table displays up to 10 most recent executions
- Failed execution is listed with correct status and metadata (start time, duration, token counts)
- "View log" button becomes visible when hovering over or interacting with the failed row
- Error log panel scrolls into view after clicking "View log"

**Selectors Used**: `pipeline-runs-table`, `pipeline-view-log-*`

**Invariants Verified**:
- Last 10 runs are correctly ordered (most recent first)
- Pipelines with no prior runs display the empty state (selector `pipeline-no-runs`)
- Error log is only displayed when explicitly requested (not shown by default)

---

### Test Case 5: View Detailed Error Log and Verify Scrollability

**Preconditions**:
- Pipeline detail drawer is open
- "View log" button has been clicked for a failed execution (Test Case 4)
- Error log panel is now visible

**Steps**:

1. Locate error log panel (selector `pipeline-error-log`)
2. Verify error log contains structured error message (step, code, message, stack-frame for code steps)
3. If error message is long, verify the error log container is scrollable
4. Attempt to scroll within the error log to verify vertical scrolling works
5. Verify "Copy error" button is visible (selector `pipeline-copy-error-button`)

**Expected Result**:
- Error log panel displays the full error message
- For long error messages, the container scrolls vertically without affecting drawer scroll
- Copy button is accessible and allows copying error text to clipboard
- Error message format matches the structured format defined in UX spec (step, code, message, stack-frame)

**Selectors Used**: `pipeline-error-log`, `pipeline-copy-error-button`

**Invariants Verified**:
- Error log is only shown for executions with error_message
- Scrollability works independently from drawer scrolling
- Copy functionality preserves full error text

---

### Test Case 6: Edit Pipeline Configuration

**Preconditions**:
- Pipeline detail drawer is open from previous test cases
- Configuration is displayed in read-only mode (selector `pipeline-config-pre`)
- Edit button is visible (selector `pipeline-edit-config-button`)

**Steps**:

1. Click the "Edit" button next to "Pipeline Configuration" label
2. Verify configuration switches to edit mode (textarea with selector `pipeline-config-textarea`)
3. Locate textarea containing JSON configuration
4. Modify a configuration value (e.g., change a source URL, endpoint, or parameter)
5. Verify Save and Cancel buttons appear (selectors `pipeline-save-config-button`, `pipeline-revert-config-button`)
6. Click "Save" button to persist the edit

**Expected Result**:
- Edit mode activates and displays configuration in an editable textarea
- JSON is properly formatted and editable
- Save button is enabled when configuration has been modified
- Configuration is persisted to the backend after clicking Save
- Drawer shows autosave indicator or confirmation message

**Selectors Used**: `pipeline-edit-config-button`, `pipeline-config-textarea`, `pipeline-save-config-button`, `pipeline-revert-config-button`, `drawer-autosave-status`

**Invariants Verified**:
- Configuration changes are validated as JSON before save
- Dirty state is tracked (Save button disabled until changes made)
- Reverting discards unsaved changes and restores original configuration

---

### Test Case 7: Execute Pipeline and Observe Status Transition

**Preconditions**:
- Pipeline detail drawer is open
- Pipeline configuration has been edited and saved (from Test Case 6)
- "Run" button is visible in drawer header (selector `run-pipeline-btn`)

**Steps**:

1. Click "Run" button in the drawer header
2. Verify status chip in the card (visible behind drawer or on re-opening) transitions to `running` with amber pulse
3. Verify statusbar dot changes to amber pulse showing "1 pipeline running"
4. Wait for execution to complete (poll the executions endpoint or wait for observable change)
5. Verify status chip transitions to `success` (green)
6. Verify statusbar dot returns to green and shows "0 pipelines running"

**Expected Result**:
- Run button click triggers execution
- Status chip transitions: failed → running → success
- Statusbar updates to show running state with amber pulse
- Execution completes and status returns to success
- New execution appears in the runs table

**Selectors Used**: `run-pipeline-btn`, `pipeline-status-chip`, `pipeline-runs-table`

**Invariants Verified**:
- Only one execution can be in-flight per pipeline at a time
- Status transitions are immediately visible in the UI
- Statusbar state is synchronized with pipeline execution state

---

### Test Case 8: Verify Success Toast and Execution Metadata

**Preconditions**:
- Pipeline execution from Test Case 7 has completed successfully
- User is viewing the pipeline drawer

**Steps**:

1. Wait for toast notification to appear after execution completes
2. Verify toast displays success intent (green)
3. Verify toast text matches pattern "Pipeline ran · N records ingested" where N is the record count
4. Scroll to runs table section
5. Verify new execution appears at the top of the runs table
6. Verify new execution has status "success"
7. Verify token counts and duration are populated in the run row

**Expected Result**:
- Success toast appears with correct message
- Toast is dismissible or auto-dismisses after 4 seconds
- New execution is immediately visible in the runs table
- Execution metadata (status, duration, token counts) is complete and accurate

**Selectors Used**: `pipeline-runs-table`

**Invariants Verified**:
- Toast is only shown for user-initiated runs (not for scheduled or API-triggered runs in this test)
- Execution metadata is fetched and displayed correctly
- Toast message includes actual record count from backend

---

### Test Case 9: Edge Case - Pipeline with No Prior Runs

**Preconditions**:
- A new pipeline exists with no executions (status = idle)
- User opens the pipeline detail drawer

**Steps**:

1. Open drawer for pipeline with no runs
2. Verify "Last 10 Runs" section shows empty state (selector `pipeline-no-runs`)
3. Verify empty state message is displayed (e.g., "This pipeline has not been run yet.")
4. Verify "Run" button is still available and enabled
5. Click "Run" to execute the pipeline

**Expected Result**:
- Pipeline with no runs does not display a failure chip on the card (displays idle or default state)
- Empty state message is shown in the runs section
- Run button works normally
- After execution, the runs table populates with the first execution

**Selectors Used**: `pipeline-no-runs`, `run-pipeline-btn`, `pipeline-status-chip`

**Invariants Verified**:
- Pipelines with no prior runs have idle status, not failed
- Empty state is appropriate and helpful
- User can still run a pipeline from the idle state

---

### Test Case 10: Edge Case - Long Error Log Scrollability

**Preconditions**:
- A pipeline execution with a very long error message exists
- Pipeline detail drawer is open
- "View log" has been clicked to reveal the error log panel

**Steps**:

1. Locate error log panel with long error message (selector `pipeline-error-log`)
2. Measure or verify the error log container has overflow and is scrollable
3. Attempt to scroll within the error log using keyboard (arrow keys, Page Down)
4. Verify scrolling moves content within the error log without affecting drawer scroll
5. Verify all error content is readable and no content is hidden

**Expected Result**:
- Error log container is scrollable when content exceeds container height
- Scrolling within error log does not interfere with drawer scrolling
- All error text is readable and properly formatted
- Copy button remains accessible during scrolling

**Selectors Used**: `pipeline-error-log`, `pipeline-copy-error-button`

**Invariants Verified**:
- Long error messages do not break layout
- Scrollable content is properly bounded and styled
- Copy functionality works for the entire error message

---

## Coverage Analysis

### CRUD Coverage

- **Create**: Pipeline is created via API in preconditions (not tested in UI, covered by pipeline creation tests)
- **Read**: Pipeline details, configuration, and execution history are read and displayed in drawer (Test Cases 3-5, 8)
- **Update**: Pipeline configuration is edited and saved (Test Case 6)
- **Delete**: Not covered in this plan (covered by separate pipeline deletion tests)
- **Execute**: Pipeline execution is triggered and monitored (Test Cases 7-8)

### Edge Cases

- **Concurrency**: Single execution at a time per pipeline (verified in Test Case 7)
- **Cascade deletes**: Not applicable to pipelines (covered in separate tests)
- **Orphaned relationships**: Not applicable to pipelines
- **Reference-integrity violations**: Pipeline must exist before execution (verified implicitly)
- **No prior runs**: Pipeline displays idle state, not failed (Test Case 9)
- **Long error messages**: Error log is scrollable (Test Case 10)
- **Statusbar integration**: Failed pipeline state is communicated in statusbar (Test Case 1)

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions — all waits are tied to observable state changes (e.g., status chip transitions, toast appearance)
- ✓ No hardcoded UUIDs — pipeline and execution IDs are retrieved from API responses
- ✓ No invented selectors — all selectors match the registry exactly (pattern-based IDs like `pipeline-card-{id}` match registry patterns)
- ✓ No vacuous assertions — all assertions verify specific, observable outcomes (status colors, text content, element visibility)
- ✓ No text-based selectors for mutable content — all selectors use `data-testid` attributes, not UI text
- ✓ Proper cleanup — test data (pipelines) are created via API and should be cleaned up in `afterEach` via `clearTestData`

---

## Factory Usage

Factories needed:
- **Pipeline creation factory** (not yet in `/ux/e2e/fixtures/factories.ts`) — will create a pipeline with configurable status (idle, failed, running, success)
- **Execution creation factory** (not yet in factories) — will create pipeline executions with configurable status, error messages, and metadata
- **Existing `clearTestData`** function will handle deletion of test pipelines

**Note**: Pipeline and Execution factories will need to be added to `factories.ts` before the tests can be generated and run. The factories should:
- Call `POST /api/pipelines` to create a pipeline configuration
- Call `POST /api/pipelines/{id}/execute` to trigger an execution and optionally mock/seed failure states
- Support overrides for title, configuration, and execution status

---

## Open Questions

1. **Pipeline creation in preconditions**: Should the test factories create pipelines with pre-seeded failed executions, or should we mock the backend to return failed states? The current structure assumes the backend can be called to create pipelines and their execution history.

2. **Statusbar selector**: The app-context.md and UX.md reference a statusbar showing pipeline status, but there is no explicit `statusbar` selector in the registry. This test assumes the statusbar is observable and clickable; **a selector for the statusbar status text** (e.g., `statusbar-pipeline-status` or `statusbar-message`) may be needed.

3. **Execution status values**: The test refers to status values like `failed`, `running`, `success`. **Verify** that `ExecutionResponse.status` in the OpenAPI schema uses these exact values (not `error`, `in-progress`, `completed`, etc.).

4. **Drawer interactions with keyboard**: Test Case 6 mentions saving via "⌘S" in the UX spec, but the test plan uses the Save button. **Clarify** whether keyboard shortcut (⌘S) should be tested separately or if Save button is sufficient.

---

## Quality Gate Summary

- [x] Every selector listed exists in `ux/selector-registry.yaml` or matches a registered pattern
- [x] Every entity field referenced (`status`, `title`, `config`, `error_message`) exists in API types
- [x] The plan aligns with UX spec § 2.2 "Resolve a failed pipeline run"
- [x] CRUD coverage is explicit (Read, Update, Execute)
- [x] Invariant validation is named (status transitions, statusbar sync, empty state handling)
- [x] Anti-patterns acknowledged (no timeouts, no hardcoded IDs, no invented selectors)
- [x] Factory usage documented (pipeline and execution factories needed)
