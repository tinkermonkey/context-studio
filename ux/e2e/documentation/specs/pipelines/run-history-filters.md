# Test Plan: Pipeline Run History Filtering

## Overview

This test validates the filtering and search functionality on the pipeline runs history page. The user navigates to the runs page, applies various filters (pipeline type, status, date range), verifies that only matching runs are displayed, combines multiple filters, and clears filters to reset the view. This ensures the filtering UI works correctly and the backend correctly applies filter criteria to the run results.

## Scope

- **Entities involved**: PipelineRun, PipelineType
- **Pages involved**: `/app/pipelines/runs`
- **External dependencies**: Back-end API for fetching filtered run lists
- **API endpoints**:
  - `GET /api/pipeline-runs` (fetch runs with optional filter parameters)
  - `GET /api/pipeline-runs?pipeline_type={type}` (filter by pipeline type)
  - `GET /api/pipeline-runs?status={status}` (filter by run status)
  - `GET /api/pipeline-runs?start_date={date}&end_date={date}` (filter by date range)

## Test Cases

### Test Case 1: Navigate to Runs Page and Verify No Filters Applied Initially

**Preconditions**:

- User is authenticated and has a workspace open
- At least 3 pipeline runs exist in the system with varying pipeline types and statuses
- Runs span multiple dates

**Steps**:

1. Navigate to `/app/pipelines/runs`
2. Wait for the runs page to load (selector `runs-page`)
3. Verify the runs table is visible (selector `runs-table`)
4. Verify the filter bar is visible (selector `runs-filter-bar`)
5. Verify the filter controls are in their default state (no active filters)
6. Verify the table displays all available runs (count all visible rows using `run-row-*` pattern)
7. Scroll through the table and confirm multiple runs from different types and statuses are visible

**Expected Result**:

- Runs page loads successfully
- Filter bar is displayed with available filter options
- All runs are visible initially (no filters applied)
- Table pagination controls are present (selectors `runs-pagination-prev`, `runs-pagination-next`)
- Filter controls show no active selections

**Selectors Used**: `runs-page`, `runs-filter-bar`, `runs-table`, `run-row-*`, `runs-pagination-prev`, `runs-pagination-next`

**Invariants Verified**:

- Runs page displays all available runs when no filters are applied
- Filter bar is readily accessible and not hidden
- Pagination is available if run count exceeds page size
- No orphaned or invisible runs in the table

---

### Test Case 2: Apply Pipeline Type Filter and Verify Filtered Results

**Preconditions**:

- Runs page is loaded with all runs visible (from Test Case 1)
- Multiple pipeline types are represented in the run list

**Steps**:

1. Locate the Pipeline Type filter control (selector `filter-pipeline-type`)
2. Click on the filter control to open the dropdown/selector
3. Select a specific pipeline type from the list (e.g., "Schema Extraction" or "Individual Extraction")
4. Verify the filter selection is applied (dropdown shows selected type or chip appears)
5. Observe the table update to show only runs of the selected type
6. Count the visible runs and verify each row contains the selected pipeline type
7. Verify the runs count or pagination info updates to reflect the filtered set

**Expected Result**:

- Pipeline Type filter dropdown opens and displays available types
- Selecting a type immediately filters the table results
- Only runs matching the selected type are displayed
- Table updates without requiring a page reload or manual refresh
- Filter selection is visually indicated in the filter control

**Selectors Used**: `filter-pipeline-type`, `runs-table`, `run-row-*`

**Invariants Verified**:

- Filter control is responsive and updates table immediately
- All visible rows match the selected pipeline type
- Runs of other types are not displayed
- Pagination updates to reflect filtered count

---

### Test Case 3: Apply Status Filter and Verify Results

**Preconditions**:

- Runs page is loaded (from Test Case 1 or 2)
- Multiple run statuses exist (e.g., COMPLETED, FAILED, RUNNING, PENDING)

**Steps**:

1. Locate the Status filter control (selector `filter-status`)
2. Click on the filter control to open the dropdown/multi-select
3. Select a specific status from the list (e.g., "COMPLETED")
4. Verify the filter selection is applied (chip appears or dropdown shows selected status)
5. Observe the table update to show only runs with the selected status
6. Count the visible runs and verify each row has the selected status
7. Verify the runs count or summary updates to reflect the filtered set

**Expected Result**:

- Status filter control opens and displays available status options
- Selecting a status immediately filters the table results
- Only runs matching the selected status are displayed
- Table updates without page reload
- Filter selection is visually indicated in the filter control

**Selectors Used**: `filter-status`, `runs-table`, `run-row-*`

**Invariants Verified**:

- Filter control is responsive and updates table immediately
- All visible rows match the selected status
- Runs with other statuses are not displayed
- Pagination updates to reflect filtered count

---

### Test Case 4: Combine Filters and Verify AND Logic

**Preconditions**:

- Both Pipeline Type and Status filters are available (from Test Cases 2-3)
- Runs matching both type and status criteria exist

**Steps**:

1. Verify the Pipeline Type filter is still set from Test Case 2
2. Verify the Status filter is still set from Test Case 3
3. Observe the table showing only runs that match BOTH type AND status
4. Count the visible runs and verify each matches both filter criteria
5. Verify the filter bar displays both active filters (two chips or selections)
6. Verify a filter summary or count indicates "X results matching both filters" or similar

**Expected Result**:

- Table displays only runs matching both filters (AND logic, not OR)
- All visible rows satisfy both type and status criteria
- Filter bar clearly shows both active filters
- Pagination reflects the combined filter result count
- Table is empty or shows empty state if no runs match both criteria

**Selectors Used**: `filter-pipeline-type`, `filter-status`, `runs-filter-bar`, `runs-table`, `run-row-*`

**Invariants Verified**:

- Multiple filters work together with AND logic (not OR)
- Filter combination correctly reduces result set
- Filter UI clearly indicates which filters are active
- Empty state appears if no runs match combined filters

---

### Test Case 5: Add Date Range Filter

**Preconditions**:

- Both Pipeline Type and Status filters are active (from Test Case 4)
- Runs span multiple dates and some are within a specific date range

**Steps**:

1. Locate the Date Range filter control (selector `filter-date-range`)
2. Click on the filter control to open the date picker or date inputs
3. Select or enter a start date (selector `filter-start-date`)
4. Select or enter an end date (selector `filter-end-date`)
5. Verify the date filter is applied (dates appear in the filter control or as chips)
6. Observe the table update to show only runs within the selected date range AND matching type and status
7. Verify all visible runs have start timestamps within the date range
8. Verify the runs count updates to reflect the triple-filtered set

**Expected Result**:

- Date Range filter control opens and accepts date input
- Setting dates immediately filters the table
- Only runs within the date range are displayed
- Results also satisfy the previous type and status filters (triple filter)
- Filter control shows the selected date range

**Selectors Used**: `filter-date-range`, `filter-start-date`, `filter-end-date`, `runs-table`, `run-row-*`

**Invariants Verified**:

- Date filter works with existing filters using AND logic
- All visible runs fall within the specified date range
- Run timestamps are correctly parsed and compared
- Pagination reflects the triple-filtered result count

---

### Test Case 6: Verify Filter Summary Updates

**Preconditions**:

- All three filters are active: Pipeline Type, Status, and Date Range (from Test Case 5)
- Table displays a filtered subset of runs

**Steps**:

1. Observe the filter bar to see which filters are active
2. Verify each active filter is visually indicated (chip, badge, or highlighted control)
3. Verify the table header or a results summary shows the filtered count (e.g., "Showing 5 of 47 runs")
4. Scroll through the visible runs and spot-check that each matches all three filter criteria
5. Verify no runs from other types, statuses, or dates are visible

**Expected Result**:

- All three active filters are clearly displayed in the filter bar
- Visual indication (chips, colors, badges) shows which filters are active
- Results summary shows the count of matching runs vs. total available
- All visible runs satisfy all three filter criteria
- UI provides clear feedback on active filters

**Selectors Used**: `runs-filter-bar`, `runs-table`, `run-row-*`

**Invariants Verified**:

- Filter UI clearly communicates active filters
- Results summary is accurate
- No spurious runs appear in filtered results

---

### Test Case 7: Clear Individual Filter and Verify Results Update

**Preconditions**:

- All three filters are active (from Test Case 5)
- Table shows filtered results

**Steps**:

1. Locate the Pipeline Type filter chip or control (selector `filter-pipeline-type`)
2. Click the "clear" or "X" button on the Pipeline Type filter chip to remove it
3. Verify the filter is removed from the filter bar
4. Observe the table update to now show runs of ANY type (but still matching Status and Date Range)
5. Verify the run count increases (more runs now visible)
6. Verify the results summary updates to reflect the new count
7. Scroll through the table to confirm runs from multiple pipeline types are now visible

**Expected Result**:

- Pipeline Type filter is removed from the filter bar
- Table expands to show runs of all types (but still filtered by Status and Date Range)
- Results count increases
- Other filters (Status, Date Range) remain active
- Results summary updates to reflect the change

**Selectors Used**: `filter-pipeline-type`, `runs-filter-bar`, `runs-table`, `run-row-*`

**Invariants Verified**:

- Individual filters can be removed without affecting others
- Results update immediately when a filter is cleared
- Remaining filters continue to apply

---

### Test Case 8: Clear All Filters and Verify Complete Results

**Preconditions**:

- At least one filter is active (from Test Case 7 or any previous test)
- Table shows filtered results

**Steps**:

1. Locate the "Clear All" button or clear the remaining filters (Status and Date Range)
2. Click the clear button on each remaining filter chip or use a global "Clear All" control if available (selector `filter-clear-dates`)
3. Verify all filter chips are removed from the filter bar
4. Observe the table update to show all available runs (unfiltered)
5. Verify the run count returns to the initial maximum
6. Verify the results summary shows the total run count with no filter indication
7. Scroll through to confirm runs of all types, statuses, and dates are visible

**Expected Result**:

- All active filters are removed from the filter bar
- Table displays all available runs (no filtering)
- Results count returns to the maximum
- Filter bar returns to default/empty state
- Results summary no longer shows filter indication

**Selectors Used**: `filter-clear-dates`, `runs-filter-bar`, `runs-table`, `run-row-*`

**Invariants Verified**:

- Filters can be completely cleared
- Table reverts to showing all runs
- Clear operation works for all filter types
- No orphaned filters remain in the UI

---

### Test Case 9: Apply Filters Again and Verify Persistence

**Preconditions**:

- All filters have been cleared (from Test Case 8)
- Table shows all runs

**Steps**:

1. Re-apply the Pipeline Type filter (selector `filter-pipeline-type`)
2. Re-apply the Status filter (selector `filter-status`)
3. Verify both filters are active and the table is filtered accordingly
4. Verify the results match the combined filter criteria
5. Do NOT navigate away from the page
6. Verify filter selections persist in the UI

**Expected Result**:

- Filters can be re-applied after clearing
- Table updates correctly with re-applied filters
- Results match the new filter criteria
- Filter state is consistent

**Selectors Used**: `filter-pipeline-type`, `filter-status`, `runs-filter-bar`, `runs-table`, `run-row-*`

**Invariants Verified**:

- Filters are not permanently locked to cleared state
- Re-applying filters works correctly
- Filter logic remains consistent

---

### Test Case 10: Pagination with Filters Applied

**Preconditions**:

- Filters are applied and result set is larger than one page (from Test Case 4 or 5)
- Pagination controls are visible

**Steps**:

1. Verify the filtered results exceed the page size (multiple pages available)
2. Verify the "Next" pagination button is enabled (selector `runs-pagination-next`)
3. Click the "Next" button to go to page 2
4. Verify the table updates to show the next set of filtered runs (all matching the active filters)
5. Verify the "Previous" pagination button is now enabled (selector `runs-pagination-prev`)
6. Click the "Previous" button to return to page 1
7. Verify the table updates back to the original filtered page 1 results

**Expected Result**:

- Pagination works correctly with filters applied
- Next/Previous buttons navigate through pages while maintaining active filters
- Each page shows only runs matching the active filters
- Results on each page are consistent with the filter criteria
- Pagination state reflects current page

**Selectors Used**: `runs-pagination-next`, `runs-pagination-prev`, `runs-table`, `run-row-*`, `filter-pipeline-type`, `filter-status`

**Invariants Verified**:

- Pagination respects active filters
- All pages show filtered results only
- Navigation between pages works correctly
- Filter state is maintained during pagination

---

## Coverage Analysis

### Filter Coverage

- **Pipeline Type Filter**: Tests filtering runs by pipeline type identifier (Test Cases 2, 4, 9)
- **Status Filter**: Tests filtering runs by execution status (COMPLETED, FAILED, etc.) (Test Cases 3, 4, 9)
- **Date Range Filter**: Tests filtering runs by start date within a range (Test Cases 5, 8)
- **Combined Filters**: Tests AND logic when multiple filters are active (Test Cases 4, 5, 6)
- **Clear Individual Filters**: Tests removing one filter while others remain (Test Case 7)
- **Clear All Filters**: Tests resetting all filters to show complete results (Test Case 8)

### CRUD Coverage

- **Read**: Runs are read from the backend with various filter parameters (all test cases)
- **Filtering/Query**: Backend receives and applies filter parameters correctly

### Edge Cases

- **No results**: Combined filters result in zero matching runs (empty state)
- **All results**: When all filters cleared, complete run list is displayed
- **Partial filter**: Only some filters are applied (Test Cases 2-3, 7)
- **Date boundary**: Runs created on exact start/end date are included
- **Multiple pages**: Filters work correctly across paginated results (Test Case 10)
- **Filter persistence**: Filters remain active during pagination (Test Case 10)

### Anti-Pattern Validations

- ✓ No fixed timeouts without conditions — all table updates observed via selector polling
- ✓ No hardcoded UUIDs — run IDs are derived from table rows, not hardcoded
- ✓ No invented selectors — all selectors exist in registry or match registered patterns
- ✓ No vacuous assertions — all assertions verify specific outcomes (filter application, result visibility, pagination behavior)
- ✓ No text-based selectors for mutable content — uses `data-testid` attributes for filter controls and table rows
- ✓ Proper cleanup — no test data created; filtering tests use existing runs

---

## Factory Usage

Factories needed for preconditions:

- **Pre-existing runs**: Test assumes at least 3-5 pipeline runs already exist with varying types, statuses, and dates
- **No cleanup required**: Filtering tests do not modify data, only read and filter existing runs

If sufficient runs do not exist, use existing pipeline execution factories (`executePipeline` or run-creation APIs) to seed test data before running this test suite.

---

## Open Questions

1. **Filter combination logic**: Do all filters combine with AND logic, or is status a multi-select (OR within status, AND with type)?

2. **Date range inclusivity**: Are runs created on the exact start and end date included in the results, or only those between (exclusive)?

3. **Filter reset scope**: When "Clear All" is clicked, does it reset to page 1 or maintain the current page position?

4. **Filter persistence on reload**: If the user applies filters and reloads the page, do the filters persist or reset to default?

5. **Empty results behavior**: When filters result in zero matches, is an empty state message shown, or does the table show zero rows with no message?

6. **Filter control UI**: Are filters displayed as chips that can be individually cleared, or as dropdown selections that must be changed?

---

## Quality Gate Summary

- [x] Every selector listed exists in `ux/selector-registry.yaml` or matches a registered pattern
- [x] Filter controls and table selectors all registered
- [x] Plan covers all major filter types and combinations
- [x] Edge cases documented (no results, all results, multiple pages)
- [x] Anti-patterns acknowledged (no timeouts, no hardcoded IDs, no invented selectors)
- [x] Factory usage appropriate for filtering tests (no data creation needed)
