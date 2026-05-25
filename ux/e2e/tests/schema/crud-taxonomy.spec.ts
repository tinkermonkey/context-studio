import { test, expect } from "@playwright/test";
import { clearTestData } from "../../fixtures/test-helpers";

test.describe("Taxonomy CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a taxonomy via modal and verify in list", async ({ page }) => {
    // Test Case 1: Create a Taxonomy via Modal
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");

    // Click "Add" button to open modal
    await page.getByTestId("taxonomy-add-button").click();
    await expect(page.getByTestId("taxonomy-create-modal")).toBeVisible();

    // Fill in form fields
    await page.getByTestId("taxonomy-title-input").fill("E2E Test Taxonomy Create");
    await page
      .getByTestId("taxonomy-description-input")
      .fill("Test taxonomy created via E2E test suite");

    // Submit the form
    await page.getByTestId("taxonomy-submit-button").click();

    // Modal should close and taxonomy should appear in the list
    await expect(page.getByTestId("taxonomy-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify taxonomy appears in the table
    const table = page.getByTestId("schema-table");
    await expect(table).toContainText("E2E Test Taxonomy Create");
    await expect(table).toContainText("Test taxonomy created via E2E test suite");
  });

  test("should open detail drawer and verify field values match created taxonomy", async ({
    page,
  }) => {
    // Setup: Create a taxonomy via UI (from previous test steps)
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");

    // Create taxonomy via modal
    await page.getByTestId("taxonomy-add-button").click();
    await expect(page.getByTestId("taxonomy-create-modal")).toBeVisible();

    await page.getByTestId("taxonomy-title-input").fill("E2E Test Taxonomy Create");
    await page
      .getByTestId("taxonomy-description-input")
      .fill("Test taxonomy created via E2E test suite");
    await page.getByTestId("taxonomy-submit-button").click();

    await expect(page.getByTestId("taxonomy-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Test Case 2: Open Detail Drawer and Verify Field Values
    // Find the row with the created taxonomy
    const tableRow = page
      .locator('[data-testid^="schema-row-"]')
      .filter({ hasText: "E2E Test Taxonomy Create" })
      .first();
    await expect(tableRow).toBeVisible();

    // Click the row to open the drawer
    await tableRow.click();

    // Verify drawer opens
    await expect(page.getByTestId("taxonomy-inspector")).toBeVisible();

    // Verify read-only ID field is visible
    await expect(page.getByTestId("taxonomy-drawer-id")).toBeVisible();

    // Verify title field contains the correct value
    const titleInput = page.getByTestId("taxonomy-drawer-title-input");
    await expect(titleInput).toHaveValue("E2E Test Taxonomy Create");

    // Verify description field contains the correct value
    const descriptionInput = page.getByTestId("taxonomy-drawer-description-input");
    await expect(descriptionInput).toHaveValue("Test taxonomy created via E2E test suite");

    // Verify drawer is visible (split layout with table on left, drawer on right)
    await expect(page.getByTestId("schema-page-layout")).toBeVisible();
  });

  test("should edit taxonomy title and verify autosave indicator", async ({ page }) => {
    // Setup: Create and open taxonomy drawer
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");

    // Create taxonomy via modal
    await page.getByTestId("taxonomy-add-button").click();
    await expect(page.getByTestId("taxonomy-create-modal")).toBeVisible();

    await page.getByTestId("taxonomy-title-input").fill("E2E Test Taxonomy Create");
    await page
      .getByTestId("taxonomy-description-input")
      .fill("Test taxonomy created via E2E test suite");
    await page.getByTestId("taxonomy-submit-button").click();

    await expect(page.getByTestId("taxonomy-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Open drawer
    const tableRow = page
      .locator('[data-testid^="schema-row-"]')
      .filter({ hasText: "E2E Test Taxonomy Create" })
      .first();
    await tableRow.click();
    await expect(page.getByTestId("taxonomy-inspector")).toBeVisible();

    // Test Case 3: Edit the title field and verify autosave
    const titleInput = page.getByTestId("taxonomy-drawer-title-input");

    // Clear and type new value
    await titleInput.click({ clickCount: 3 });
    await titleInput.fill("E2E Test Taxonomy Updated");

    // Wait for autosave indicator to appear
    const autosaveStatus = page.getByTestId("inspector-autosave-status");
    await expect(autosaveStatus).toBeVisible({ timeout: 5000 });

    // Wait for autosave to complete (indicator shows saved state or disappears)
    await expect(autosaveStatus).not.toBeVisible({ timeout: 5000 });

    // Verify the new title is still in the field
    await expect(titleInput).toHaveValue("E2E Test Taxonomy Updated");
  });

  test("should delete taxonomy via drawer delete button with confirmation and show undo toast", async ({
    page,
  }) => {
    // Setup: Create and open taxonomy drawer
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");

    // Create taxonomy via modal
    await page.getByTestId("taxonomy-add-button").click();
    await expect(page.getByTestId("taxonomy-create-modal")).toBeVisible();

    await page.getByTestId("taxonomy-title-input").fill("E2E Test Taxonomy Create");
    await page
      .getByTestId("taxonomy-description-input")
      .fill("Test taxonomy created via E2E test suite");
    await page.getByTestId("taxonomy-submit-button").click();

    await expect(page.getByTestId("taxonomy-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Open drawer
    const tableRow = page
      .locator('[data-testid^="schema-row-"]')
      .filter({ hasText: "E2E Test Taxonomy Create" })
      .first();
    await tableRow.click();
    await expect(page.getByTestId("taxonomy-inspector")).toBeVisible();

    // Test Case 4: Delete via drawer delete button
    const deleteButton = page.getByTestId("inspector-delete-button");
    await deleteButton.click();

    // Verify confirmation dialog appears
    const confirmDialog = page.getByTestId("confirm-dialog");
    await expect(confirmDialog).toBeVisible();

    // Click confirm button
    const confirmButton = page.getByTestId("confirm-dialog-confirm");
    await confirmButton.click();

    // Verify dialog closes
    await expect(confirmDialog).not.toBeVisible();

    // Wait for drawer to close
    await expect(page.getByTestId("taxonomy-inspector")).not.toBeVisible({ timeout: 5000 });

    // Verify taxonomy no longer appears in the table
    const table = page.getByTestId("schema-table");
    await expect(table).not.toContainText("E2E Test Taxonomy Create");

    // Test Case 5: Verify undo toast appears and click undo
    const toastAction = page.locator('[data-testid^="toast-action-"]').first();
    await expect(toastAction).toBeVisible({ timeout: 5000 });

    // Click undo action
    await toastAction.click();

    // Wait for toast to disappear
    await expect(toastAction).not.toBeVisible({ timeout: 5000 });

    // Wait for table to update
    await page.waitForLoadState("networkidle");

    // Verify restored taxonomy appears in the table
    await expect(table).toContainText("E2E Test Taxonomy Create", { timeout: 5000 });

    // Verify the description is preserved
    await expect(table).toContainText("Test taxonomy created via E2E test suite");
  });
});
