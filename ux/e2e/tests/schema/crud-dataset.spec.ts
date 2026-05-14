import { test, expect } from "@playwright/test";
import { clearTestData } from "../../fixtures/test-helpers";

test.describe("Dataset CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a dataset via modal and verify in list", async ({ page }) => {
    // Test Case 1: Create a Dataset via Modal
    await page.goto("/app/data/datasets");
    await page.waitForLoadState("networkidle");

    // Click "Add" button to open modal
    await page.getByTestId("dataset-add-button").click();
    await expect(page.getByTestId("dataset-create-modal")).toBeVisible();

    // Fill in form fields
    await page.getByTestId("dataset-title-input").fill("E2E Test Dataset Create");
    await page.getByTestId("dataset-filename-input").fill("test_dataset.db");
    await page
      .getByTestId("dataset-description-input")
      .fill("Test dataset created via E2E test suite");

    // Submit the form
    await page.getByTestId("dataset-submit-button").click();

    // Modal should close and dataset should appear in the list
    await expect(page.getByTestId("dataset-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify dataset appears in the table
    const table = page.getByTestId("schema-table");
    await expect(table).toContainText("E2E Test Dataset Create");
    await expect(table).toContainText("test_dataset.db");
    await expect(table).toContainText("Test dataset created via E2E test suite");
  });

  test("should delete dataset with confirmation", async ({ page }) => {
    // Setup: Create a dataset via UI
    await page.goto("/app/data/datasets");
    await page.waitForLoadState("networkidle");

    // Create dataset via modal
    await page.getByTestId("dataset-add-button").click();
    await expect(page.getByTestId("dataset-create-modal")).toBeVisible();

    await page.getByTestId("dataset-title-input").fill("E2E Test Dataset Delete");
    await page.getByTestId("dataset-filename-input").fill("test_delete.db");
    await page.getByTestId("dataset-description-input").fill("Dataset to be deleted");
    await page.getByTestId("dataset-submit-button").click();

    await expect(page.getByTestId("dataset-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify dataset appears in the table
    let table = page.getByTestId("schema-table");
    await expect(table).toContainText("E2E Test Dataset Delete");

    // Find and click delete button for the dataset
    const deleteButton = page.locator('[data-testid^="dataset-row-delete-"]').first();
    await expect(deleteButton).toBeVisible();

    // Setup listener for confirmation dialog
    page.on("dialog", (dialog) => {
      expect(dialog.type()).toBe("confirm");
      expect(dialog.message()).toContain("Are you sure");
      dialog.accept();
    });

    // Click delete button
    await deleteButton.click();

    // Wait for the deletion to process
    await page.waitForLoadState("networkidle");

    // Verify dataset no longer appears in the table
    table = page.getByTestId("schema-table");
    await expect(table).not.toContainText("E2E Test Dataset Delete");
  });

  test("should display all required columns in dataset table", async ({ page }) => {
    // Setup: Create a dataset
    await page.goto("/app/data/datasets");
    await page.waitForLoadState("networkidle");

    // Create dataset via modal
    await page.getByTestId("dataset-add-button").click();
    await expect(page.getByTestId("dataset-create-modal")).toBeVisible();

    await page.getByTestId("dataset-title-input").fill("E2E Test Dataset Columns");
    await page.getByTestId("dataset-filename-input").fill("test_columns.db");
    await page.getByTestId("dataset-description-input").fill("Testing table columns");
    await page.getByTestId("dataset-submit-button").click();

    await expect(page.getByTestId("dataset-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify all columns are present
    const table = page.getByTestId("schema-table");
    await expect(table).toBeVisible();

    // Check for table headers
    const headerCells = page.locator("th");
    const headerTexts = await headerCells.allTextContents();

    // Verify expected columns exist
    expect(headerTexts.length).toBeGreaterThan(0);
    const textContent = headerTexts.join(" ");
    expect(textContent).toContain("Name");
    expect(textContent).toContain("Filename");
    expect(textContent).toContain("Description");
    expect(textContent).toContain("Status");
  });

  test("should handle empty datasets list gracefully", async ({ page }) => {
    // Navigate to datasets page without creating any
    await page.goto("/app/data/datasets");
    await page.waitForLoadState("networkidle");

    // Should show empty state
    const emptyState = page.locator(".empty-state");
    await expect(emptyState).toBeVisible();

    const title = page.locator(".empty-state-title");
    await expect(title).toContainText("No datasets yet");

    // Create button should be visible in empty state
    const createButton = page.getByTestId("empty-state-new-dataset");
    await expect(createButton).toBeVisible();
  });

  test("should prevent deletion of active dataset", async ({ page, context }) => {
    // Setup: Create a dataset and activate it
    await page.goto("/app/data/datasets");
    await page.waitForLoadState("networkidle");

    // Create dataset
    await page.getByTestId("dataset-add-button").click();
    await expect(page.getByTestId("dataset-create-modal")).toBeVisible();
    await page.getByTestId("dataset-title-input").fill("E2E Test Dataset Active");
    await page.getByTestId("dataset-filename-input").fill("test_active.db");
    await page.getByTestId("dataset-submit-button").click();

    await expect(page.getByTestId("dataset-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Get the dataset ID from the table
    const table = page.getByTestId("schema-table");
    await expect(table).toContainText("E2E Test Dataset Active");

    // Extract dataset ID from the delete button's data-testid attribute
    const deleteButton = page.locator('[data-testid^="dataset-row-delete-"]').first();
    const dataTestId = await deleteButton.getAttribute("data-testid");
    const datasetId = dataTestId?.replace("dataset-row-delete-", "") || "";

    // Activate the dataset via API
    await context.request.post(`http://localhost:8000/api/v1/admin/datasets/${datasetId}/activate`);
    await page.waitForLoadState("networkidle");

    // Refresh the page to see the updated state
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Find the delete button again after refresh
    const refreshedDeleteButton = page.locator(`[data-testid="dataset-row-delete-${datasetId}"]`);

    // Delete button should be disabled for active dataset
    await expect(refreshedDeleteButton).toBeDisabled();
  });

  test("should support form validation and show error messages", async ({ page }) => {
    // Navigate to datasets page
    await page.goto("/app/data/datasets");
    await page.waitForLoadState("networkidle");

    // Open create modal
    await page.getByTestId("dataset-add-button").click();
    await expect(page.getByTestId("dataset-create-modal")).toBeVisible();

    // Try to submit without filling required fields
    await page.getByTestId("dataset-submit-button").click();

    // Verify validation error for missing title
    await expect(page.getByText("Title is required")).toBeVisible();

    // Fill in title and try again
    await page.getByTestId("dataset-title-input").fill("Partial Dataset");
    await page.getByTestId("dataset-submit-button").click();

    // Verify validation error for missing filename
    await expect(page.getByText("Filename is required")).toBeVisible();

    // Fill in filename
    await page.getByTestId("dataset-filename-input").fill("partial.db");
    await page.getByTestId("dataset-submit-button").click();

    // Modal should close on success
    await expect(page.getByTestId("dataset-create-modal")).not.toBeVisible();
  });

  test("should perform complete CRUD cycle for dataset", async ({ page }) => {
    // CREATE: Create a dataset
    await page.goto("/app/data/datasets");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("dataset-add-button").click();
    await expect(page.getByTestId("dataset-create-modal")).toBeVisible();

    const datasetTitle = "E2E Test Dataset Complete CRUD";
    const datasetFilename = "test_crud_complete.db";
    const datasetDescription = "Complete CRUD test dataset";

    await page.getByTestId("dataset-title-input").fill(datasetTitle);
    await page.getByTestId("dataset-filename-input").fill(datasetFilename);
    await page.getByTestId("dataset-description-input").fill(datasetDescription);

    await page.getByTestId("dataset-submit-button").click();
    await expect(page.getByTestId("dataset-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify CREATE was successful
    let table = page.getByTestId("schema-table");
    await expect(table).toContainText(datasetTitle);
    await expect(table).toContainText(datasetFilename);
    await expect(table).toContainText(datasetDescription);

    // DELETE: Delete the dataset
    const deleteButton = page.locator('[data-testid^="dataset-row-delete-"]').first();

    // Delete button should be enabled for inactive dataset
    await expect(deleteButton).not.toBeDisabled();

    // Setup confirmation dialog handler
    page.on("dialog", (dialog) => {
      dialog.accept();
    });

    // Click delete and verify it was successful
    await deleteButton.click();
    await page.waitForLoadState("networkidle");

    // Verify DELETE was successful
    table = page.getByTestId("schema-table");
    await expect(table).not.toContainText(datasetTitle);
  });
});
