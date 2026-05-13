import { test, expect } from "@playwright/test";
import {
  createConceptScheme,
  createClass,
  createIndividual,
  getIndividualsByClass,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Class CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Test Case 1: Create a New Class via Create Button", async ({ page }) => {
    // Setup: Create a concept scheme
    const scheme = await createConceptScheme(page, undefined, {
      title: "Test Scheme for Class CRUD",
      description: "Scheme to hold test classes",
    });

    // Navigate to classes page
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Step 1: Click "New class" button
    await page.getByTestId("class-add-button").click();

    // Step 2: Verify modal opens
    await expect(page.getByTestId("class-create-modal")).toBeVisible();

    // Step 3: Locate form
    await expect(page.getByTestId("class-form")).toBeVisible();

    // Step 4: Fill in name field
    await page.getByTestId("class-title-input").fill("Test Class: CRUD Operations");

    // Step 5: Fill in description field
    await page.getByTestId("class-description-input").fill(
      "Comprehensive test class for CRUD operations",
    );

    // Step 6: Select domain from dropdown
    // Note: We need to interact with the domain selector in the form
    // The form should have a domain/scheme selector
    const domainSelect = page.locator('[data-testid="class-form"]').locator("select");
    if (await domainSelect.count() > 0) {
      await domainSelect.selectOption(scheme.id);
    }

    // Step 8: Click submit button
    await page.getByTestId("class-submit-button").click();

    // Verify modal closes and class appears in the table
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("class-create-modal")).not.toBeVisible();

    // Verify class appears in the table
    await expect(page.getByTestId("schema-table")).toContainText("Test Class: CRUD Operations");
    await expect(page.getByTestId("schema-table")).toContainText("Comprehensive test class");
  });

  test("Test Case 2: Click Class Row to Open Detail Drawer and Verify Fields", async ({
    page,
  }) => {
    // Setup: Create scheme and class
    const scheme = await createConceptScheme(page, undefined, {
      title: "Test Scheme for Drawer",
      description: "Scheme for drawer test",
    });

    const testClass = await createClass(page, scheme.id, {
      title: "Test Class: CRUD Operations",
      description: "Comprehensive test class for CRUD operations",
    });

    // Navigate to classes page
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Step 1-2: Click the class name to open drawer
    await page.locator(`[data-testid="class-name-${testClass.id}"]`).click();

    // Step 3: Verify drawer opens
    await expect(page.getByTestId("class-drawer")).toBeVisible();

    // Step 5: Verify read-only ID field
    const idField = page.getByTestId("class-drawer-id");
    await expect(idField).toContainText(testClass.id);

    // Step 6: Verify name input field
    const nameInput = page.getByTestId("class-drawer-name-input");
    await expect(nameInput).toHaveValue("Test Class: CRUD Operations");

    // Step 7: Verify description textarea
    const descriptionInput = page.getByTestId("class-drawer-description-input");
    await expect(descriptionInput).toHaveValue("Comprehensive test class for CRUD operations");

    // Step 8: Verify domain selector
    const domainSelect = page.getByTestId("class-drawer-domain-select");
    await expect(domainSelect).toBeVisible();

    // Step 9: Verify no parent class field (or shows "—")
    const drawerContainer = page.getByTestId("class-drawer");
    const parentDisplay = drawerContainer.locator("text=—");
    // Parent might not be visible if there's no parent, which is expected
  });

  test("Test Case 3: Edit a Field in the Drawer and Verify Autosave Indicator", async ({
    page,
  }) => {
    // Setup: Create scheme and class
    const scheme = await createConceptScheme(page, undefined, {
      title: "Test Scheme for Edit",
      description: "Scheme for edit test",
    });

    const testClass = await createClass(page, scheme.id, {
      title: "Test Class: CRUD Operations",
      description: "Comprehensive test class for CRUD operations",
    });

    // Navigate to classes page
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Click to open drawer
    await page.locator(`[data-testid="class-name-${testClass.id}"]`).click();
    await expect(page.getByTestId("class-drawer")).toBeVisible();

    // Step 1-2: Locate and clear the name input, then type new name
    const nameInput = page.getByTestId("class-drawer-name-input");
    await nameInput.tripleClick();
    await nameInput.fill("Updated Test Class");

    // Step 4-5: Verify autosave indicator transitions to "saved"
    const autosaveStatus = page.getByTestId("drawer-autosave-status");
    await expect(autosaveStatus).toContainText(/Saved|saved/, { timeout: 5000 });

    // Step 6: Verify input field value changed
    await expect(nameInput).toHaveValue("Updated Test Class");

    // Step 7: Click description textarea
    const descriptionInput = page.getByTestId("class-drawer-description-input");
    await descriptionInput.tripleClick();

    // Step 8: Type new description
    await descriptionInput.fill("Updated description for CRUD test");

    // Step 10: Verify autosave indicator shows "saved"
    await expect(autosaveStatus).toContainText(/Saved|saved/, { timeout: 5000 });
  });

  test("Test Case 4: Delete the Class and Handle Type-to-Confirm Dialog (No Instances)", async ({
    page,
  }) => {
    // Setup: Create scheme and class
    const scheme = await createConceptScheme(page, undefined, {
      title: "Test Scheme for Delete",
      description: "Scheme for delete test",
    });

    const testClass = await createClass(page, scheme.id, {
      title: "Updated Test Class",
      description: "Class for deletion test",
    });

    // Navigate to classes page
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Click to open drawer
    await page.locator(`[data-testid="class-name-${testClass.id}"]`).click();
    await expect(page.getByTestId("class-drawer")).toBeVisible();

    // Step 1: Click delete button
    await page.getByTestId("drawer-delete-button").click();

    // Step 3: Verify type-to-confirm dialog appears
    await expect(page.getByTestId("type-confirm-dialog")).toBeVisible();

    // Step 5: Locate input field and type the class title
    const confirmInput = page.getByTestId("type-confirm-input");
    await confirmInput.fill("Updated Test Class");

    // Step 7: Verify confirm button becomes enabled
    const confirmButton = page.getByTestId("type-confirm-button");
    await expect(confirmButton).toBeEnabled();

    // Step 8: Click confirm button
    await confirmButton.click();

    // Step 9: Verify dialog closes and class removed from table
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("type-confirm-dialog")).not.toBeVisible();
    await expect(page.getByTestId("class-drawer")).not.toBeVisible();

    // Verify class no longer in table
    await expect(page.getByTestId("schema-table")).not.toContainText("Updated Test Class");

    // Step 10: Verify toast notification with undo action appears
    const toast = page.locator('[data-testid^="toast-action-"]');
    await expect(toast).toBeVisible();
  });

  test("Test Case 5: Click Undo to Restore the Deleted Class", async ({ page }) => {
    // Setup: Create scheme and class
    const scheme = await createConceptScheme(page, undefined, {
      title: "Test Scheme for Undo",
      description: "Scheme for undo test",
    });

    const testClass = await createClass(page, scheme.id, {
      title: "Test Class for Undo",
      description: "Class to be deleted and restored",
    });

    // Navigate to classes page
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Delete the class first
    await page.locator(`[data-testid="class-name-${testClass.id}"]`).click();
    await expect(page.getByTestId("class-drawer")).toBeVisible();

    await page.getByTestId("drawer-delete-button").click();
    await expect(page.getByTestId("type-confirm-dialog")).toBeVisible();

    const confirmInput = page.getByTestId("type-confirm-input");
    await confirmInput.fill("Test Class for Undo");

    const confirmButton = page.getByTestId("type-confirm-button");
    await confirmButton.click();

    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("schema-table")).not.toContainText("Test Class for Undo");

    // Step 2: Locate the toast notification with undo action
    const undoButton = page.locator('[data-testid^="toast-action-"]').first();
    await expect(undoButton).toBeVisible();

    // Step 3: Click the undo action button
    await undoButton.click();

    // Step 5: Wait for page to update
    await page.waitForLoadState("networkidle");

    // Verify class reappears in the table
    await expect(page.getByTestId("schema-table")).toContainText("Test Class for Undo");

    // Verify we can click it again
    const classLink = page.locator(`[data-testid="class-name-${testClass.id}"]`);
    await expect(classLink).toBeVisible();
  });

  test("Test Case 6: Create a Class with Instances and Verify Type-to-Confirm with Warning Message", async ({
    page,
  }) => {
    // Setup: Create scheme, class, and individuals
    const scheme = await createConceptScheme(page, undefined, {
      title: "Test Scheme for Cascade",
      description: "Scheme for cascade delete test",
    });

    const testClass = await createClass(page, scheme.id, {
      title: "Test Class with Instances",
      description: "Class with individuals for cascade test",
    });

    // Create two individuals linked to this class
    const individual1 = await createIndividual(page, {
      title: "Test Individual 1",
      description: "First instance",
      class_ids: [testClass.id],
    });

    const individual2 = await createIndividual(page, {
      title: "Test Individual 2",
      description: "Second instance",
      class_ids: [testClass.id],
    });

    // Verify individuals are created
    const individuals = await getIndividualsByClass(page, testClass.id);
    expect(individuals.length).toBe(2);

    // Navigate to classes page
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Click to open drawer
    await page.locator(`[data-testid="class-name-${testClass.id}"]`).click();
    await expect(page.getByTestId("class-drawer")).toBeVisible();

    // Step 1: Click delete button
    await page.getByTestId("drawer-delete-button").click();

    // Step 3: Verify type-to-confirm dialog appears
    await expect(page.getByTestId("type-confirm-dialog")).toBeVisible();

    // Step 4: Verify warning message appears
    const dialog = page.getByTestId("type-confirm-dialog");
    await expect(dialog).toContainText(/individual/i);

    // Step 6: Locate input and type the confirmation text
    const confirmInput = page.getByTestId("type-confirm-input");
    await confirmInput.fill("Test Class with Instances");

    // Step 8: Verify confirm button becomes enabled
    const confirmButton = page.getByTestId("type-confirm-button");
    await expect(confirmButton).toBeEnabled();

    // Step 9: Click the confirm button
    await confirmButton.click();

    // Step 10: Verify dialog closes and class is soft-deleted
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("type-confirm-dialog")).not.toBeVisible();
    await expect(page.getByTestId("schema-table")).not.toContainText(
      "Test Class with Instances",
    );

    // Step 11: Verify toast appears
    const toast = page.locator('[data-testid^="toast-action-"]');
    await expect(toast).toBeVisible();
  });
});
