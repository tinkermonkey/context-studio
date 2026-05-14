import { test, expect } from "@playwright/test";
import { createTaxonomy, createConceptScheme, clearTestData } from "../../fixtures/test-helpers";

test.describe("Concept Scheme CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Test Case 1: Create a Concept Scheme via Modal", async ({ page }) => {
    // Setup: Create parent taxonomy
    const _taxonomy = await createTaxonomy(page, {
      title: "Test Taxonomy for Scheme CRUD",
      description: "Parent taxonomy for concept scheme tests",
    });

    // Navigate to schemes page
    await page.goto("/app/schema/schemes/");
    await page.waitForLoadState("networkidle");

    // Step 1: Click "Add Scheme" button
    await page.getByTestId("scheme-add-button").click();

    // Step 2: Verify create modal opens
    await expect(page.getByTestId("scheme-create-modal")).toBeVisible();

    // Step 3: Locate form
    const form = page.getByTestId("scheme-form");
    await expect(form).toBeVisible();

    // Step 4: Fill title field
    await form.locator('[data-testid="scheme-title-input"]').fill("Test Concept Scheme");

    // Step 5: Fill description field
    await form
      .locator('[data-testid="scheme-description-input"]')
      .fill("A test scheme for CRUD operations");

    // Step 6: Click submit
    await form.locator('[data-testid="scheme-submit-button"]').click();

    // Step 7: Verify modal closes and scheme appears in list
    await expect(page.getByTestId("scheme-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify scheme appears in table
    const schemeTable = page.getByTestId("schema-table");
    await expect(schemeTable).toContainText("Test Concept Scheme");
  });

  test("Test Case 2: Click Row to Open Detail Drawer and Verify Field Values", async ({ page }) => {
    // Setup: Create parent taxonomy and scheme
    const taxonomy = await createTaxonomy(page, {
      title: "Test Taxonomy for Drawer",
      description: "Parent taxonomy for drawer tests",
    });

    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Concept Scheme",
      description: "A test scheme for CRUD operations",
    });

    // Navigate to schemes page
    await page.goto("/app/schema/schemes/");
    await page.waitForLoadState("networkidle");

    // Step 1: Locate and click the scheme row
    const schemeRow = page.locator(`[data-testid="schema-row-${scheme.id}"]`);
    await expect(schemeRow).toBeVisible();
    await schemeRow.click();

    // Step 2: Verify drawer opens
    const drawer = page.getByTestId("scheme-drawer");
    await expect(drawer).toBeVisible();

    // Step 3: Verify schema-page-layout is present
    await expect(page.getByTestId("schema-page-layout")).toBeVisible();

    // Step 4: Verify read-only ID field
    const idField = drawer.locator('[data-testid="scheme-drawer-id"]');
    await expect(idField).toBeVisible();
    await expect(idField).toHaveValue(scheme.id);

    // Step 5: Verify editable title field
    const titleField = drawer.locator('[data-testid="scheme-drawer-title-input"]');
    await expect(titleField).toBeVisible();
    await expect(titleField).toHaveValue("Test Concept Scheme");

    // Step 6: Verify editable description field
    const descriptionField = drawer.locator('[data-testid="scheme-drawer-description-input"]');
    await expect(descriptionField).toBeVisible();
    await expect(descriptionField).toHaveValue("A test scheme for CRUD operations");

    // Step 7: Verify read-only parent taxonomy field
    const taxonomyField = drawer.locator('[data-testid="scheme-drawer-parent-taxonomy"]');
    await expect(taxonomyField).toBeVisible();
    await expect(taxonomyField).toHaveValue(taxonomy.id);
  });

  test("Test Case 3: Edit a Field in the Drawer and Verify Autosave Indicator Appears", async ({
    page,
  }) => {
    // Setup: Create parent taxonomy and scheme
    const taxonomy = await createTaxonomy(page, {
      title: "Test Taxonomy for Autosave",
      description: "Parent taxonomy for autosave tests",
    });

    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Concept Scheme",
      description: "Original description",
    });

    // Navigate to schemes page
    await page.goto("/app/schema/schemes/");
    await page.waitForLoadState("networkidle");

    // Open the drawer by clicking the scheme row
    const schemeRow = page.locator(`[data-testid="schema-row-${scheme.id}"]`);
    await schemeRow.click();
    await page.waitForLoadState("networkidle");

    // Step 1: Locate title input
    const drawer = page.getByTestId("scheme-drawer");
    const titleField = drawer.locator('[data-testid="scheme-drawer-title-input"]');

    // Step 2: Clear and type new title
    await titleField.clear();
    await titleField.fill("Updated Test Scheme");

    // Step 3: Observe autosave indicator
    const autosaveStatus = drawer.locator('[data-testid="drawer-autosave-status"]');
    await expect(autosaveStatus).toBeVisible();

    // Step 4: Wait for autosave to complete - indicator should show "saved"
    await expect(autosaveStatus).toContainText("saved", { timeout: 10000 });

    // Step 5: Close and reopen drawer to verify persistence
    await page.keyboard.press("Escape");
    await page.waitForLoadState("networkidle");

    // Reopen by clicking the row again
    await schemeRow.click();
    await page.waitForLoadState("networkidle");

    // Verify title persisted
    const reopenedTitleField = drawer.locator('[data-testid="scheme-drawer-title-input"]');
    await expect(reopenedTitleField).toHaveValue("Updated Test Scheme");
  });

  test("Test Case 4: Delete the Scheme via Delete Button and Confirm Deletion", async ({
    page,
  }) => {
    // Setup: Create parent taxonomy and scheme
    const taxonomy = await createTaxonomy(page, {
      title: "Test Taxonomy for Delete",
      description: "Parent taxonomy for delete tests",
    });

    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Concept Scheme to Delete",
      description: "This scheme will be deleted",
    });

    // Navigate to schemes page
    await page.goto("/app/schema/schemes/");
    await page.waitForLoadState("networkidle");

    // Step 1: Click scheme row to open drawer
    const schemeRow = page.locator(`[data-testid="schema-row-${scheme.id}"]`);
    await schemeRow.click();
    await page.waitForLoadState("networkidle");

    // Step 2: Locate and click delete button
    const drawer = page.getByTestId("scheme-drawer");
    const deleteButton = drawer.locator('[data-testid="drawer-delete-button"]');
    await expect(deleteButton).toBeVisible();
    await deleteButton.click();

    // Step 3: Verify confirmation dialog appears
    const confirmDialog = page.getByTestId("scheme-delete-confirm");
    await expect(confirmDialog).toBeVisible();

    // Step 4: Click confirm button
    const confirmButton = page.getByTestId("confirm-dialog-confirm");
    await confirmButton.click();

    // Step 5: Verify drawer closes and scheme is removed from list
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("scheme-drawer")).not.toBeVisible();

    // Verify scheme is no longer in table
    const schemeTable = page.getByTestId("schema-table");
    await expect(schemeTable).not.toContainText("Test Concept Scheme to Delete");

    // Verify undo toast appears
    const undoToast = page.locator('[data-testid^="toast-action-"]');
    await expect(undoToast).toBeVisible();
  });

  test("Test Case 5: Click Undo to Restore the Deleted Scheme", async ({ page }) => {
    // Setup: Create parent taxonomy and scheme
    const taxonomy = await createTaxonomy(page, {
      title: "Test Taxonomy for Undo",
      description: "Parent taxonomy for undo tests",
    });

    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Concept Scheme for Undo",
      description: "This scheme will be deleted and restored",
    });

    // Navigate to schemes page
    await page.goto("/app/schema/schemes/");
    await page.waitForLoadState("networkidle");

    // Delete the scheme
    const schemeRow = page.locator(`[data-testid="schema-row-${scheme.id}"]`);
    await schemeRow.click();
    await page.waitForLoadState("networkidle");

    const drawer = page.getByTestId("scheme-drawer");
    const deleteButton = drawer.locator('[data-testid="drawer-delete-button"]');
    await deleteButton.click();

    const _confirmDialog = page.getByTestId("scheme-delete-confirm");
    const confirmButton = page.getByTestId("confirm-dialog-confirm");
    await confirmButton.click();

    await page.waitForLoadState("networkidle");

    // Step 1: Locate the undo toast
    const undoToast = page.locator('[data-testid^="toast-action-"]');
    await expect(undoToast).toBeVisible();

    // Step 2: Click the undo action button
    await undoToast.click();

    // Step 3: Wait for the page to update
    await page.waitForLoadState("networkidle");

    // Step 4: Verify toast closes
    await expect(undoToast).not.toBeVisible();

    // Step 5: Verify scheme reappears in table
    const schemeTable = page.getByTestId("schema-table");
    await expect(schemeTable).toContainText("Test Concept Scheme for Undo");
  });
});
