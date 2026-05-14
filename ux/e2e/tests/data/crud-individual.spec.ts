import { test, expect } from "@playwright/test";
import {
  createConceptScheme,
  createClass,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Individual CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Create Individual via Modal Form", async ({ page }) => {
    // Setup: Create a test class for the individual to reference
    const scheme = await createConceptScheme(page);
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class for Individual",
      description: "A class for testing Individual CRUD",
    });

    // Navigate to individuals page
    await page.goto("/app/data/individuals");
    await page.waitForLoadState("networkidle");

    // Click "Add Individual" button
    await page.getByTestId("individual-add-button").click();

    // Verify modal opens
    const modal = page.getByTestId("individual-create-modal");
    await expect(modal).toBeVisible();

    // Verify form is present
    const form = modal.locator('[data-testid="individual-form"]');
    await expect(form).toBeVisible();

    // Fill in title field
    await modal.getByTestId("individual-title-input").fill("Test Individual");

    // Click class select and choose the test class
    await modal.getByTestId("individual-class-select").click();
    await modal.getByTestId(`individual-class-option-${testClass.id}`).click();

    // Verify class chip appears
    const classChip = modal.locator('[data-testid^="individual-class-"]').first();
    await expect(classChip).toBeVisible();

    // Fill in description
    await modal.getByTestId("individual-description-input").fill("A test individual instance");

    // Submit form
    await modal.getByTestId("individual-submit-button").click();

    // Modal should close
    await expect(modal).not.toBeVisible();

    // Verify individual appears in the table
    await page.waitForLoadState("networkidle");
    const tableRow = page.locator('[data-testid^="individual-name-"]');
    await expect(tableRow.first()).toContainText("Test Individual");
  });

  test("Verify Individual in Table and Open Drawer", async ({ page }) => {
    // Setup: Create test class and individual
    const scheme = await createConceptScheme(page);
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class for Individual",
    });

    // Navigate to individuals page
    await page.goto("/app/data/individuals");
    await page.waitForLoadState("networkidle");

    // Create individual via modal
    await page.getByTestId("individual-add-button").click();
    const modal = page.getByTestId("individual-create-modal");
    await expect(modal).toBeVisible();

    await modal.getByTestId("individual-title-input").fill("Test Individual");
    await modal.getByTestId("individual-class-select").click();
    await modal.getByTestId(`individual-class-option-${testClass.id}`).click();
    await modal.getByTestId("individual-description-input").fill("A test individual instance");
    await modal.getByTestId("individual-submit-button").click();
    await expect(modal).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify individual row is visible
    const individualRow = page.locator('[data-testid^="individual-name-"]').first();
    await expect(individualRow).toContainText("Test Individual");

    // Verify class chip appears in the row
    const classChips = page.locator('[data-testid^="individual-class-chip-"]');
    await expect(classChips.first()).toBeVisible();

    // Click on individual row to open drawer
    await individualRow.click();

    // Verify drawer opens
    const drawer = page.getByTestId("individual-detail-page");
    await expect(drawer).toBeVisible();

    // Verify schema-page-layout parent container is present
    const layout = page.getByTestId("schema-page-layout");
    await expect(layout).toBeVisible();

    // Verify drawer displays ID field
    const idField = drawer.getByTestId("individual-drawer-id");
    await expect(idField).toBeVisible();

    // Verify drawer displays title
    const titleInput = drawer.getByTestId("individual-drawer-name-input");
    await expect(titleInput).toHaveValue("Test Individual");
  });

  test("Edit Individual Field in Drawer with Autosave", async ({ page }) => {
    // Setup: Create test class and individual
    const scheme = await createConceptScheme(page);
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class for Individual",
    });

    // Navigate to individuals page and create individual
    await page.goto("/app/data/individuals");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("individual-add-button").click();
    const modal = page.getByTestId("individual-create-modal");
    await expect(modal).toBeVisible();

    await modal.getByTestId("individual-title-input").fill("Original Title");
    await modal.getByTestId("individual-class-select").click();
    await modal.getByTestId(`individual-class-option-${testClass.id}`).click();
    await modal.getByTestId("individual-description-input").fill("Original description");
    await modal.getByTestId("individual-submit-button").click();
    await expect(modal).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Open drawer
    await page.locator('[data-testid^="individual-name-"]').first().click();
    const drawer = page.getByTestId("individual-detail-page");
    await expect(drawer).toBeVisible();

    // Edit title field
    const titleInput = drawer.getByTestId("individual-drawer-name-input");
    await titleInput.clear();
    await titleInput.fill("Updated Test Individual");

    // Verify autosave status shows "saving" then "saved"
    const autosaveStatus = page.getByTestId("drawer-autosave-status");
    await expect(autosaveStatus).toBeVisible();

    // Wait for autosave to complete (should show "saved" state)
    await expect(autosaveStatus).toContainText("saved", { timeout: 5000 });

    // Verify title persists in drawer
    await expect(titleInput).toHaveValue("Updated Test Individual");

    // Close and reopen drawer to verify persistence
    await page.getByTestId("individual-drawer-close-button").click();
    await page.locator('[data-testid^="individual-name-"]').first().click();
    await expect(drawer).toBeVisible();
    await expect(titleInput).toHaveValue("Updated Test Individual");
  });

  test("Delete Individual via Row Action and Confirm", async ({ page }) => {
    // Setup: Create test class and individual
    const scheme = await createConceptScheme(page);
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class for Individual",
    });

    // Navigate to individuals page and create individual
    await page.goto("/app/data/individuals");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("individual-add-button").click();
    const modal = page.getByTestId("individual-create-modal");
    await expect(modal).toBeVisible();

    await modal.getByTestId("individual-title-input").fill("To Delete");
    await modal.getByTestId("individual-class-select").click();
    await modal.getByTestId(`individual-class-option-${testClass.id}`).click();
    await modal.getByTestId("individual-description-input").fill("Will be deleted");
    await modal.getByTestId("individual-submit-button").click();
    await expect(modal).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Get the individual ID from the row (extract from testid pattern individual-name-{id})
    const individualRow = page.locator('[data-testid^="individual-name-"]').first();
    const rowTestId = await individualRow.getAttribute("data-testid");
    const individualId = rowTestId!.replace("individual-name-", "");

    // Click delete button for the individual
    const deleteButton = page.getByTestId(`individual-row-delete-${individualId}`);
    await expect(deleteButton).toBeVisible();
    await deleteButton.click();

    // Verify confirmation dialog appears
    const confirmDialog = page.getByTestId("confirm-dialog");
    await expect(confirmDialog).toBeVisible();

    // Verify dialog text mentions the individual
    await expect(confirmDialog).toContainText("To Delete");

    // Click confirm button
    await page.getByTestId("confirm-dialog-confirm").click();
    await expect(confirmDialog).not.toBeVisible();

    // Wait for table update
    await page.waitForLoadState("networkidle");

    // Verify individual no longer appears in table
    await expect(page.locator(`[data-testid="individual-name-${individualId}"]`)).not.toBeVisible();

    // Verify toast with undo action appears
    const toast = page.locator('[data-testid^="toast-action-"]').first();
    await expect(toast).toBeVisible();
    await expect(toast).toContainText(/undo|restore/i);
  });

  test("Restore Deleted Individual via Undo Toast", async ({ page }) => {
    // Setup: Create test class and individual
    const scheme = await createConceptScheme(page);
    const testClass = await createClass(page, scheme.id, {
      title: "Test Class for Individual",
    });

    // Navigate to individuals page and create individual
    await page.goto("/app/data/individuals");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("individual-add-button").click();
    const modal = page.getByTestId("individual-create-modal");
    await expect(modal).toBeVisible();

    await modal.getByTestId("individual-title-input").fill("To Restore");
    await modal.getByTestId("individual-class-select").click();
    await modal.getByTestId(`individual-class-option-${testClass.id}`).click();
    await modal.getByTestId("individual-description-input").fill("Will be restored");
    await modal.getByTestId("individual-submit-button").click();
    await expect(modal).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Get the individual ID from the row
    const individualRow = page.locator('[data-testid^="individual-name-"]').first();
    const rowTestId = await individualRow.getAttribute("data-testid");
    const individualId = rowTestId!.replace("individual-name-", "");

    // Delete the individual
    const deleteButton = page.getByTestId(`individual-row-delete-${individualId}`);
    await deleteButton.click();

    const confirmDialog = page.getByTestId("confirm-dialog");
    await expect(confirmDialog).toBeVisible();
    await page.getByTestId("confirm-dialog-confirm").click();
    await expect(confirmDialog).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify individual is gone from table
    await expect(page.locator(`[data-testid="individual-name-${individualId}"]`)).not.toBeVisible();

    // Verify undo toast appears and click it
    const toast = page.locator('[data-testid^="toast-action-"]').first();
    await expect(toast).toBeVisible();

    // Click the undo action button
    const undoButton = toast.getByRole("button");
    await expect(undoButton).toBeVisible();
    await undoButton.click();

    // Toast should close and table should update
    await expect(toast).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify individual reappears in table
    const restoredRow = page.locator(`[data-testid="individual-name-${individualId}"]`);
    await expect(restoredRow).toBeVisible();
    await expect(restoredRow).toContainText("To Restore");
  });
});
