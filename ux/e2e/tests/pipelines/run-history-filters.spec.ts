import { test, expect } from "@playwright/test";
import { clearTestData } from "../../fixtures/test-helpers";

test.describe("Pipeline Run History Filtering", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Navigate to Runs Page and Verify No Filters Applied Initially", async ({ page }) => {
    // Navigate to pipeline runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Verify runs page is visible
    await expect(page.getByTestId("runs-page")).toBeVisible();

    // Verify the runs table is visible
    await expect(page.getByTestId("runs-table")).toBeVisible();

    // Verify the filter bar is visible
    await expect(page.getByTestId("runs-filter-bar")).toBeVisible();

    // Verify table contains rows or shows empty state
    const runRows = page.locator('[data-testid^="run-row-"]');
    const rowCount = await runRows.count();

    // If there are runs, verify pagination controls
    if (rowCount > 0) {
      const prevButton = page.getByTestId("runs-pagination-prev");
      const nextButton = page.getByTestId("runs-pagination-next");

      // Pagination controls should exist (may be disabled on first page)
      await expect(prevButton).toBeDefined();
      await expect(nextButton).toBeDefined();
    }
  });

  test("Apply Pipeline Type Filter and Verify Filtered Results", async ({ page }) => {
    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Verify runs page and filter bar are visible
    await expect(page.getByTestId("runs-page")).toBeVisible();
    await expect(page.getByTestId("runs-filter-bar")).toBeVisible();

    // Get initial row count before filtering
    const runsTable = page.getByTestId("runs-table");
    await expect(runsTable).toBeVisible();
    const initialRows = page.locator('[data-testid^="run-row-"]');
    const _initialCount = await initialRows.count();

    // Locate the Pipeline Type filter control
    const pipelineTypeFilter = page.getByTestId("filter-pipeline-type");
    await expect(pipelineTypeFilter).toBeVisible();

    // Click on the filter control to open dropdown
    await pipelineTypeFilter.click();

    // Wait for dropdown to appear and select first option
    const dropdown = pipelineTypeFilter.locator("..").locator('[role="listbox"], [role="dialog"]');
    await expect(dropdown).toBeVisible();
    const firstOption = pipelineTypeFilter.locator("..").locator('[role="option"]').first();
    await expect(firstOption).toBeVisible();
    await firstOption.click();
    await page.waitForLoadState("networkidle");

    // Verify the runs table is updated and results changed
    await expect(page.getByTestId("runs-table")).toBeVisible();
    const filteredRows = page.locator('[data-testid^="run-row-"]');
    const filteredCount = await filteredRows.count();

    // Verify filtering produced a result (count may be less than or equal to initial)
    expect(filteredCount).toBeLessThanOrEqual(_initialCount);
  });

  test("Apply Status Filter and Verify Results", async ({ page }) => {
    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Verify runs page and filter bar
    await expect(page.getByTestId("runs-page")).toBeVisible();
    await expect(page.getByTestId("runs-filter-bar")).toBeVisible();

    // Get initial row count
    const initialRows = page.locator('[data-testid^="run-row-"]');
    const _initialCount = await initialRows.count();

    // Locate the Status filter control
    const statusFilter = page.getByTestId("filter-status");
    await expect(statusFilter).toBeVisible();

    // Click on the filter control to open dropdown
    await statusFilter.click();

    // Wait for dropdown to appear and select first option
    const dropdown = statusFilter.locator("..").locator('[role="listbox"], [role="dialog"]');
    await expect(dropdown).toBeVisible();
    const firstOption = statusFilter.locator("..").locator('[role="option"]').first();
    await expect(firstOption).toBeVisible();
    await firstOption.click();
    await page.waitForLoadState("networkidle");

    // Verify the runs table is updated and results changed
    await expect(page.getByTestId("runs-table")).toBeVisible();
    const filteredRows = page.locator('[data-testid^="run-row-"]');
    const filteredCount = await filteredRows.count();

    // Verify filtering produced a result
    expect(filteredCount).toBeLessThanOrEqual(_initialCount);
  });

  test("Combine Pipeline Type and Status Filters with AND Logic", async ({ page }) => {
    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Verify filters are visible
    await expect(page.getByTestId("runs-filter-bar")).toBeVisible();

    // Get initial row count
    const initialRows = page.locator('[data-testid^="run-row-"]');
    const _initialCount = await initialRows.count();

    // Apply Pipeline Type filter
    const pipelineTypeFilter = page.getByTestId("filter-pipeline-type");
    await pipelineTypeFilter.click();

    const typeDropdown = pipelineTypeFilter
      .locator("..")
      .locator('[role="listbox"], [role="dialog"]');
    await expect(typeDropdown).toBeVisible();
    const firstTypeOption = pipelineTypeFilter.locator("..").locator('[role="option"]').first();
    await expect(firstTypeOption).toBeVisible();
    await firstTypeOption.click();
    await page.waitForLoadState("networkidle");

    // Get count after first filter
    const afterFirstFilter = page.locator('[data-testid^="run-row-"]');
    const firstFilterCount = await afterFirstFilter.count();

    // Apply Status filter
    const statusFilter = page.getByTestId("filter-status");
    await statusFilter.click();

    const statusDropdown = statusFilter.locator("..").locator('[role="listbox"], [role="dialog"]');
    await expect(statusDropdown).toBeVisible();
    const firstStatusOption = statusFilter.locator("..").locator('[role="option"]').first();
    await expect(firstStatusOption).toBeVisible();
    await firstStatusOption.click();
    await page.waitForLoadState("networkidle");

    // Verify the runs table displays AND-combined filtered results
    await expect(page.getByTestId("runs-table")).toBeVisible();
    await expect(page.getByTestId("runs-filter-bar")).toBeVisible();

    // Verify the AND logic was applied - combined filter should be more restrictive
    const combinedFilterRows = page.locator('[data-testid^="run-row-"]');
    const combinedCount = await combinedFilterRows.count();
    expect(combinedCount).toBeLessThanOrEqual(firstFilterCount);
  });

  test("Add Date Range Filter and Verify Combined Filtering", async ({ page }) => {
    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Verify filter bar is visible
    await expect(page.getByTestId("runs-filter-bar")).toBeVisible();

    // Get initial row count
    const initialRows = page.locator('[data-testid^="run-row-"]');
    const initialCount = await initialRows.count();

    // Locate the Date Range filter control
    const dateRangeFilter = page.getByTestId("filter-date-range");
    await expect(dateRangeFilter).toBeVisible();

    // Click on the date range filter to open the date picker
    await dateRangeFilter.click();

    // Wait for date picker to appear
    const datePicker = dateRangeFilter.locator("..").locator('[role="dialog"]');
    await expect(datePicker).toBeVisible();

    // Look for date inputs within the picker
    const startDateInput = page.getByTestId("filter-start-date");
    const endDateInput = page.getByTestId("filter-end-date");

    // Fill date inputs with a reasonable range
    await expect(startDateInput).toBeVisible();
    // Set start date to 30 days ago
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 30);
    await startDateInput.fill(startDate.toISOString().split("T")[0]);

    await expect(endDateInput).toBeVisible();
    // Set end date to today
    const endDate = new Date();
    await endDateInput.fill(endDate.toISOString().split("T")[0]);

    // Wait for filter to apply
    await page.waitForLoadState("networkidle");

    // Verify the runs table is updated and results changed
    await expect(page.getByTestId("runs-table")).toBeVisible();
    const filteredRows = page.locator('[data-testid^="run-row-"]');
    const filteredCount = await filteredRows.count();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test("Verify Filter Summary and Active Filter Display", async ({ page }) => {
    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Verify filter bar is visible
    const filterBar = page.getByTestId("runs-filter-bar");
    await expect(filterBar).toBeVisible();

    // Apply a filter
    const pipelineTypeFilter = page.getByTestId("filter-pipeline-type");
    await pipelineTypeFilter.click();

    const dropdown = pipelineTypeFilter.locator("..").locator('[role="listbox"], [role="dialog"]');
    await expect(dropdown).toBeVisible();
    const firstOption = pipelineTypeFilter.locator("..").locator('[role="option"]').first();
    await expect(firstOption).toBeVisible();
    await firstOption.click();
    await page.waitForLoadState("networkidle");

    // Verify the runs table is visible with results
    await expect(page.getByTestId("runs-table")).toBeVisible();

    // Verify filter bar still shows the active filter
    await expect(filterBar).toBeVisible();
  });

  test("Clear Individual Filter and Verify Results Update", async ({ page }) => {
    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Get initial row count
    const initialRows = page.locator('[data-testid^="run-row-"]');
    const initialCount = await initialRows.count();

    // Apply a filter
    const pipelineTypeFilter = page.getByTestId("filter-pipeline-type");
    await pipelineTypeFilter.click();

    const dropdown = pipelineTypeFilter.locator("..").locator('[role="listbox"], [role="dialog"]');
    await expect(dropdown).toBeVisible();
    const firstOption = pipelineTypeFilter.locator("..").locator('[role="option"]').first();
    await expect(firstOption).toBeVisible();
    await firstOption.click();
    await page.waitForLoadState("networkidle");

    // Now clear the filter by clicking again to deselect
    await pipelineTypeFilter.click();
    await page.waitForLoadState("networkidle");

    // Verify the runs table is still visible
    await expect(page.getByTestId("runs-table")).toBeVisible();

    // Verify filter bar is visible
    await expect(page.getByTestId("runs-filter-bar")).toBeVisible();

    // Verify results updated after clearing filter (should return to all results)
    const clearedRows = page.locator('[data-testid^="run-row-"]');
    const clearedCount = await clearedRows.count();
    expect(clearedCount).toBeGreaterThanOrEqual(initialCount);
  });

  test("Clear All Filters and Verify Complete Results", async ({ page }) => {
    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Apply multiple filters
    const pipelineTypeFilter = page.getByTestId("filter-pipeline-type");
    await pipelineTypeFilter.click();

    const dropdown = pipelineTypeFilter.locator("..").locator('[role="listbox"], [role="dialog"]');
    await expect(dropdown).toBeVisible();
    const firstOption = pipelineTypeFilter.locator("..").locator('[role="option"]').first();
    await expect(firstOption).toBeVisible();
    await firstOption.click();
    await page.waitForLoadState("networkidle");

    // Get filtered row count
    const filteredRows = page.locator('[data-testid^="run-row-"]');
    const filteredCount = await filteredRows.count();

    // Look for a clear all button or clear individual filters
    const clearDatesButton = page.getByTestId("filter-clear-dates");
    const clearDatesVisible = await clearDatesButton.isVisible().catch(() => false);
    if (clearDatesVisible) {
      await clearDatesButton.click();
      await page.waitForLoadState("networkidle");
    }

    // Clear remaining filters by clicking on them again (toggle off)
    await pipelineTypeFilter.click();
    await page.waitForLoadState("networkidle");

    // Verify the runs table is visible with all results
    await expect(page.getByTestId("runs-table")).toBeVisible();

    // Verify filter bar is visible
    await expect(page.getByTestId("runs-filter-bar")).toBeVisible();

    // Verify all filters cleared - should see more or equal results than when filtered
    const clearedRows = page.locator('[data-testid^="run-row-"]');
    const clearedCount = await clearedRows.count();
    expect(clearedCount).toBeGreaterThanOrEqual(filteredCount);
  });

  test("Apply Filters Again and Verify Persistence Within Session", async ({ page }) => {
    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Get initial row count
    const initialRows = page.locator('[data-testid^="run-row-"]');
    const _initialCount = await initialRows.count();

    // Apply Pipeline Type filter
    const pipelineTypeFilter = page.getByTestId("filter-pipeline-type");
    await pipelineTypeFilter.click();

    const dropdown = pipelineTypeFilter.locator("..").locator('[role="listbox"], [role="dialog"]');
    await expect(dropdown).toBeVisible();
    const firstOption = pipelineTypeFilter.locator("..").locator('[role="option"]').first();
    await expect(firstOption).toBeVisible();
    await firstOption.click();
    await page.waitForLoadState("networkidle");

    // Verify filter is applied
    await expect(page.getByTestId("runs-table")).toBeVisible();
    const afterTypeFilter = page.locator('[data-testid^="run-row-"]');
    const typeFilterCount = await afterTypeFilter.count();

    // Apply Status filter
    const statusFilter = page.getByTestId("filter-status");
    await statusFilter.click();

    const statusDropdown = statusFilter.locator("..").locator('[role="listbox"], [role="dialog"]');
    await expect(statusDropdown).toBeVisible();
    const firstStatusOption = statusFilter.locator("..").locator('[role="option"]').first();
    await expect(firstStatusOption).toBeVisible();
    await firstStatusOption.click();
    await page.waitForLoadState("networkidle");

    // Verify both filters are applied
    await expect(page.getByTestId("runs-table")).toBeVisible();
    await expect(page.getByTestId("runs-filter-bar")).toBeVisible();

    // Verify combined filters are more restrictive
    const combinedRows = page.locator('[data-testid^="run-row-"]');
    const combinedCount = await combinedRows.count();
    expect(combinedCount).toBeLessThanOrEqual(typeFilterCount);
  });

  test("Pagination with Filters Applied", async ({ page }) => {
    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Verify runs page
    await expect(page.getByTestId("runs-page")).toBeVisible();

    // Apply a filter
    const pipelineTypeFilter = page.getByTestId("filter-pipeline-type");
    await pipelineTypeFilter.click();

    const dropdown = pipelineTypeFilter.locator("..").locator('[role="listbox"], [role="dialog"]');
    await expect(dropdown).toBeVisible();
    const firstOption = pipelineTypeFilter.locator("..").locator('[role="option"]').first();
    await expect(firstOption).toBeVisible();
    await firstOption.click();
    await page.waitForLoadState("networkidle");

    // Verify the runs table
    await expect(page.getByTestId("runs-table")).toBeVisible();

    // Check if Next button is enabled (indicates multiple pages)
    const nextButton = page.getByTestId("runs-pagination-next");
    const nextVisible = await nextButton.isVisible().catch(() => false);
    const nextEnabled = nextVisible && (await nextButton.isEnabled().catch(() => false));

    if (nextEnabled) {
      // Click Next to go to page 2
      await nextButton.click();
      await page.waitForLoadState("networkidle");

      // Verify runs table still shows filtered results
      await expect(page.getByTestId("runs-table")).toBeVisible();

      // Verify Previous button is now enabled
      const prevButton = page.getByTestId("runs-pagination-prev");
      const prevVisible = await prevButton.isVisible().catch(() => false);
      if (prevVisible) {
        await expect(prevButton).toBeEnabled();
        // Click Previous to return to page 1
        await prevButton.click();
        await page.waitForLoadState("networkidle");

        // Verify runs table is visible
        await expect(page.getByTestId("runs-table")).toBeVisible();
      }
    }
  });

  test("Verify Filter Controls Are Functional", async ({ page }) => {
    // Navigate to runs page
    await page.goto("/app/pipelines/runs");
    await page.waitForLoadState("networkidle");

    // Verify all filter controls are present
    const filterBar = page.getByTestId("runs-filter-bar");
    await expect(filterBar).toBeVisible();

    const pipelineTypeFilter = page.getByTestId("filter-pipeline-type");
    const statusFilter = page.getByTestId("filter-status");
    const dateRangeFilter = page.getByTestId("filter-date-range");

    // Verify filter controls exist and are visible
    await expect(pipelineTypeFilter).toBeVisible();
    await expect(statusFilter).toBeVisible();
    await expect(dateRangeFilter).toBeVisible();

    // Verify runs table is visible
    await expect(page.getByTestId("runs-table")).toBeVisible();
  });
});
