import { test, expect } from "@playwright/test";
import {
  createPropertyDefinition,
  createTaxonomy,
  createConceptScheme,
  createClass,
  createRelationship,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Property CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Test Case 1: Create a New Property via Modal", async ({ page }) => {
    // Navigate to properties page
    await page.goto("/app/schema/properties");
    await page.waitForLoadState("networkidle");

    // Click the "Add Property" button
    const addButton = page.getByTestId("property-add-button");
    await expect(addButton).toBeVisible();
    await addButton.click();

    // Verify modal opens
    const createModal = page.getByTestId("property-create-modal");
    await expect(createModal).toBeVisible();

    // Locate the form
    const form = page.getByTestId("property-create-form");
    await expect(form).toBeVisible();

    // Fill the identifier input
    const identifierInput = page.getByTestId("property-definition-identifier-input");
    await expect(identifierInput).toBeVisible();
    await identifierInput.fill("prop_test_crud_001");

    // Fill the title input
    const titleInput = page.getByTestId("property-definition-title-input");
    await expect(titleInput).toBeVisible();
    await titleInput.fill("Test Property CRUD");

    // Fill the description input
    const descriptionInput = page.getByTestId("property-definition-description-input");
    await expect(descriptionInput).toBeVisible();
    await descriptionInput.fill("Property for testing CRUD operations");

    // Click submit button
    const submitButton = page.getByTestId("property-definition-submit-button");
    await expect(submitButton).toBeVisible();
    await submitButton.click();

    // Verify modal closes
    await expect(createModal).not.toBeVisible();

    // Wait for table to load
    await page.waitForLoadState("networkidle");

    // Verify the newly created property appears in the table
    const table = page.getByTestId("schema-table");
    await expect(table).toContainText("prop_test_crud_001");
    await expect(table).toContainText("Test Property CRUD");
    await expect(table).toContainText("Property for testing CRUD operations");
  });

  test("Test Case 2: Open Property Drawer and Verify Field Values", async ({ page }) => {
    // Create a property first
    const property = await createPropertyDefinition(page, {
      identifier: "prop_test_crud_001",
      title: "Test Property CRUD",
      description: "Property for testing CRUD operations",
    });

    // Navigate to properties page
    await page.goto("/app/schema/properties");
    await page.waitForLoadState("networkidle");

    // Find the property row by ID
    const propertyRow = page.getByTestId(`schema-row-${property.id}`);
    await expect(propertyRow).toBeVisible();

    // Click the property row to select it
    await propertyRow.click();
    await page.waitForLoadState("networkidle");

    // Verify the drawer opens on the right side
    const drawer = page.getByTestId("properties-drawer");
    await expect(drawer).toBeVisible();

    // Verify the drawer displays the property details
    const propertyDrawer = page.getByTestId("property-drawer");
    await expect(propertyDrawer).toBeVisible();

    // Verify the identifier field is read-only and displays correct value
    const identifierField = page.getByTestId("property-drawer-identifier");
    await expect(identifierField).toBeVisible();
    await expect(identifierField).toContainText("prop_test_crud_001");

    // Verify the title field displays correct value
    const titleField = page.getByTestId("property-drawer-title-input");
    await expect(titleField).toBeVisible();
    await expect(titleField).toHaveValue("Test Property CRUD");

    // Verify the description field displays correct value
    const descriptionField = page.getByTestId("property-drawer-description-input");
    await expect(descriptionField).toBeVisible();
    await expect(descriptionField).toHaveValue("Property for testing CRUD operations");

    // Verify the split layout is present
    const pageLayout = page.getByTestId("schema-page-layout");
    await expect(pageLayout).toBeVisible();
  });

  test("Test Case 3: Edit a Field and Verify Autosave Indicator", async ({ page }) => {
    // Create a property first
    const property = await createPropertyDefinition(page, {
      identifier: "prop_test_crud_001",
      title: "Test Property CRUD",
      description: "Property for testing CRUD operations",
    });

    // Navigate to properties page
    await page.goto("/app/schema/properties");
    await page.waitForLoadState("networkidle");

    // Find and click the property row to open drawer
    const propertyRow = page.getByTestId(`schema-row-${property.id}`);
    await expect(propertyRow).toBeVisible();
    await propertyRow.click();
    await page.waitForLoadState("networkidle");

    // Verify drawer is open
    const drawer = page.getByTestId("properties-drawer");
    await expect(drawer).toBeVisible();

    // Locate the title input field in the drawer
    const titleInput = page.getByTestId("property-drawer-title-input");
    await expect(titleInput).toBeVisible();

    // Clear and update the title
    await titleInput.clear();
    await titleInput.fill("Test Property CRUD - Updated");

    // Verify the autosave status indicator becomes visible
    const autosaveStatus = page.getByTestId("drawer-autosave-status");
    await expect(autosaveStatus).toBeVisible({ timeout: 5000 });

    // Wait for autosave to complete (status indicator shows success or clears)
    await expect(autosaveStatus).not.toBeVisible({ timeout: 10000 });

    // Wait for network to be idle to ensure save completes
    await page.waitForLoadState("networkidle");

    // Verify no error messages appear
    const errorElements = page.locator('[role="alert"]');
    const errorCount = await errorElements.count();
    expect(errorCount).toBe(0);

    // Verify the title field still contains the updated value
    await expect(titleInput).toHaveValue("Test Property CRUD - Updated");
  });

  test("Test Case 4: Delete Property (Unused) and Verify Undo Toast", async ({ page }) => {
    // Create a property first
    const property = await createPropertyDefinition(page, {
      identifier: "prop_test_crud_001",
      title: "Test Property CRUD",
      description: "Property for testing CRUD operations",
    });

    // Navigate to properties page
    await page.goto("/app/schema/properties");
    await page.waitForLoadState("networkidle");

    // Find and click the property row to open drawer
    const propertyRow = page.getByTestId(`schema-row-${property.id}`);
    await expect(propertyRow).toBeVisible();
    await propertyRow.click();
    await page.waitForLoadState("networkidle");

    // Verify drawer is open
    const drawer = page.getByTestId("properties-drawer");
    await expect(drawer).toBeVisible();

    // Locate and click the delete button
    const deleteButton = page.getByTestId("drawer-delete-button");
    await expect(deleteButton).toBeVisible();
    await deleteButton.click();

    // Verify no confirmation dialog appears (property is unused)
    const confirmDialog = page.getByTestId("confirm-dialog");
    await expect(confirmDialog).not.toBeVisible();

    // Wait for network idle after deletion
    await page.waitForLoadState("networkidle");

    // Verify drawer closes automatically
    await expect(drawer).not.toBeVisible();

    // Verify property row disappears from the table
    const table = page.getByTestId("schema-table");
    await expect(table).not.toContainText("Test Property CRUD");

    // Verify an undo toast appears
    const toastAction = page.locator('[data-testid^="toast-action-"]').first();
    await expect(toastAction).toBeVisible({ timeout: 5000 });
  });

  test("Test Case 5: Click Undo and Restore the Deleted Property", async ({ page }) => {
    // Create a property first
    const property = await createPropertyDefinition(page, {
      identifier: "prop_test_crud_001",
      title: "Test Property CRUD",
      description: "Property for testing CRUD operations",
    });

    // Navigate to properties page
    await page.goto("/app/schema/properties");
    await page.waitForLoadState("networkidle");

    // Find and click the property row to open drawer
    const propertyRow = page.getByTestId(`schema-row-${property.id}`);
    await expect(propertyRow).toBeVisible();
    await propertyRow.click();
    await page.waitForLoadState("networkidle");

    // Verify drawer is open
    const drawer = page.getByTestId("properties-drawer");
    await expect(drawer).toBeVisible();

    // Click delete button
    const deleteButton = page.getByTestId("drawer-delete-button");
    await expect(deleteButton).toBeVisible();
    await deleteButton.click();

    // Wait for network idle
    await page.waitForLoadState("networkidle");

    // Verify undo toast appears
    const toastAction = page.locator('[data-testid^="toast-action-"]').first();
    await expect(toastAction).toBeVisible({ timeout: 5000 });

    // Click the undo action button
    await toastAction.click();

    // Wait for network idle after undo
    await page.waitForLoadState("networkidle");

    // Verify the toast dismisses
    await expect(toastAction).not.toBeVisible();

    // Verify the property reappears in the table
    const table = page.getByTestId("schema-table");
    await expect(table).toContainText("Test Property CRUD", { timeout: 5000 });

    // Verify the property row is visible
    const restoredRow = page.getByTestId(`schema-row-${property.id}`);
    await expect(restoredRow).toBeVisible();

    // Verify the property row is immediately usable
    await restoredRow.click();
    await page.waitForLoadState("networkidle");

    // Verify drawer opens with original data intact
    const propertyDrawer = page.getByTestId("property-drawer");
    await expect(propertyDrawer).toBeVisible();

    const titleField = page.getByTestId("property-drawer-title-input");
    await expect(titleField).toHaveValue("Test Property CRUD");
  });

  test("Test Case 6: Delete Property (In Use) with Confirmation Dialog", async ({ page }) => {
    // Create prerequisite entities
    const taxonomy = await createTaxonomy(page, {
      title: "Test Taxonomy for In-Use Property",
      description: "Taxonomy for testing in-use property deletion",
    });

    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Scheme",
      description: "Scheme for testing in-use property",
    });

    const class1 = await createClass(page, scheme.id, {
      title: "Source Class",
      description: "Source class for relationship",
    });

    const class2 = await createClass(page, scheme.id, {
      title: "Target Class",
      description: "Target class for relationship",
    });

    // Create a property to be used in a relationship
    const property = await createPropertyDefinition(page, {
      identifier: "prop_in_use",
      title: "In Use Property",
      description: "Property that will be linked to a relationship",
    });

    // Create a relationship that uses this property
    await createRelationship(page, class1.id, class2.id, property.id);

    // Navigate to properties page
    await page.goto("/app/schema/properties");
    await page.waitForLoadState("networkidle");

    // Find and click the property row
    const propertyRow = page.getByTestId(`schema-row-${property.id}`);
    await expect(propertyRow).toBeVisible();
    await propertyRow.click();
    await page.waitForLoadState("networkidle");

    // Verify drawer opens
    const drawer = page.getByTestId("properties-drawer");
    await expect(drawer).toBeVisible();

    // Click delete button
    const deleteButton = page.getByTestId("drawer-delete-button");
    await expect(deleteButton).toBeVisible();
    await deleteButton.click();

    // Verify confirmation dialog appears
    const confirmDialog = page.getByTestId("confirm-dialog");
    await expect(confirmDialog).toBeVisible({ timeout: 5000 });

    // Verify dialog message indicates property is in use
    await expect(confirmDialog).toContainText(/in use|linked|relationship/i);

    // Verify two buttons exist: Cancel and Delete
    const cancelButton = page.getByTestId("confirm-dialog-cancel");
    const confirmButton = page.getByTestId("confirm-dialog-confirm");
    await expect(cancelButton).toBeVisible();
    await expect(confirmButton).toBeVisible();

    // Click the confirm/delete button
    await confirmButton.click();

    // Wait for network idle
    await page.waitForLoadState("networkidle");

    // Verify the property is deleted
    const table = page.getByTestId("schema-table");
    await expect(table).not.toContainText("In Use Property", { timeout: 5000 });

    // Verify drawer closes
    await expect(drawer).not.toBeVisible();

    // Verify undo toast appears
    const toastAction = page.locator('[data-testid^="toast-action-"]').first();
    await expect(toastAction).toBeVisible({ timeout: 5000 });
  });
});
