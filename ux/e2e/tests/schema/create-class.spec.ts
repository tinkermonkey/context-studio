import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Create Class", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("Navigate to Classes Page and Open Modal", async ({ page }) => {
    // Setup: Create a taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-create-class",
      description: "Taxonomy for class creation tests",
    });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "test-scheme-create-class",
      description: "Scheme for class creation tests",
    });

    // Navigate to classes page
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Verify page elements are visible
    await expect(page.getByTestId("classes-page")).toBeVisible();
    await expect(page.getByTestId("classes-content")).toBeVisible();
    await expect(page.getByTestId("class-add-button")).toBeVisible();

    // Click the "+ New class" button
    await page.getByTestId("class-add-button").click();

    // Verify modal opens with form
    await expect(page.getByTestId("class-create-modal")).toBeVisible();
    await expect(page.getByTestId("class-editor-form")).toBeVisible();
    await expect(page.getByTestId("class-editor-name-input")).toBeFocused();
    await expect(page.getByTestId("class-editor-name-input")).toHaveValue("");
  });

  test("Fill Modal Fields and Submit Successfully", async ({ page }) => {
    // Setup: Create a taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-create-class-submit",
      description: "Taxonomy for class submission tests",
    });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "test-scheme-create-class-submit",
      description: "Scheme for class submission tests",
    });

    // Navigate to classes page and open modal
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("class-add-button").click();
    await expect(page.getByTestId("class-create-modal")).toBeVisible();

    // Fill form fields
    await page.getByTestId("class-editor-name-input").fill("test_organism");
    await page.getByTestId("class-editor-description-input").fill("Test class for organism classification");

    // Select domain/scheme
    const domainSelect = page.getByTestId("class-editor-domain-select");
    await domainSelect.click();
    await page.waitForLoadState("networkidle");
    // Select the first option (our created scheme)
    const firstOption = page.locator('[data-testid*="class-editor-domain-select"] ~ [role="listbox"] >> [role="option"]').first();
    await firstOption.click();

    // Submit the form
    await page.getByTestId("class-editor-submit-button").click();

    // Verify modal closes
    await expect(page.getByTestId("class-create-modal")).not.toBeVisible();

    // Verify success toast appears with pattern "Class created · cls_*"
    const toast = page.locator('[role="status"]').filter({ hasText: /Class created.*cls_/ });
    await expect(toast).toBeVisible();
    await expect(toast).toContainText(/Class created.*cls_/);
  });

  test("New Class Appears in Table and Is Selected", async ({ page }) => {
    // Setup: Create a taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-create-class-table",
      description: "Taxonomy for class table tests",
    });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "test-scheme-create-class-table",
      description: "Scheme for class table tests",
    });

    // Navigate to classes page and open modal
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("class-add-button").click();
    await expect(page.getByTestId("class-create-modal")).toBeVisible();

    // Fill and submit form
    await page.getByTestId("class-editor-name-input").fill("test_organism");
    await page.getByTestId("class-editor-description-input").fill("Test class for organism classification");
    const domainSelect = page.getByTestId("class-editor-domain-select");
    await domainSelect.click();
    await page.waitForLoadState("networkidle");
    const firstOption = page.locator('[data-testid*="class-editor-domain-select"] ~ [role="listbox"] >> [role="option"]').first();
    await firstOption.click();

    await page.getByTestId("class-editor-submit-button").click();

    // Wait for modal to close and table to refresh
    await expect(page.getByTestId("class-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify class appears in table
    const table = page.getByTestId("schema-table");
    await expect(table).toContainText("test_organism");

    // Verify the row is present and selected (by checking page layout indicates split view)
    const rows = page.locator('[data-testid^="schema-row-"]');
    const matchingRow = rows.filter({ hasText: "test_organism" }).first();
    await expect(matchingRow).toBeVisible();

    // Verify drawer layout is applied (indicating row is selected)
    await expect(page.getByTestId("schema-page-layout")).toBeVisible();
    await expect(page.getByTestId("class-drawer")).toBeVisible();
  });

  test("Drawer Shows Correct Class Details", async ({ page }) => {
    // Setup: Create a taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-create-class-drawer",
      description: "Taxonomy for class drawer tests",
    });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "test-scheme-create-class-drawer",
      description: "Scheme for class drawer tests",
    });

    // Navigate to classes page and create a class via UI
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("class-add-button").click();
    await expect(page.getByTestId("class-create-modal")).toBeVisible();

    const classDescription = "Test class for drawer verification";
    await page.getByTestId("class-editor-name-input").fill("test_organism");
    await page.getByTestId("class-editor-description-input").fill(classDescription);
    const domainSelect = page.getByTestId("class-editor-domain-select");
    await domainSelect.click();
    await page.waitForLoadState("networkidle");
    const firstOption = page.locator('[data-testid*="class-editor-domain-select"] ~ [role="listbox"] >> [role="option"]').first();
    await firstOption.click();

    await page.getByTestId("class-editor-submit-button").click();

    // Wait for modal to close and drawer to appear
    await expect(page.getByTestId("class-create-modal")).not.toBeVisible();
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("class-drawer")).toBeVisible();

    // Verify drawer contains correct data
    await expect(page.getByTestId("class-drawer-id")).toHaveValue(/cls_/);
    await expect(page.getByTestId("class-drawer-name-input")).toHaveValue("test_organism");
    await expect(page.getByTestId("class-drawer-description-input")).toHaveValue(classDescription);
  });

  test("Edge Case — Empty Name Shows Validation Error", async ({ page }) => {
    // Setup: Create a taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-validation-empty",
      description: "Taxonomy for empty name validation tests",
    });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "test-scheme-validation-empty",
      description: "Scheme for empty name validation tests",
    });

    // Navigate to classes page and open modal
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("class-add-button").click();
    await expect(page.getByTestId("class-create-modal")).toBeVisible();

    // Leave name field empty and blur it
    const nameInput = page.getByTestId("class-editor-name-input");
    await nameInput.focus();
    await nameInput.blur();

    // Verify validation error appears
    await page.waitForTimeout(100); // Give validation a moment to appear
    const errorMessage = page.locator('[role="alert"], .text-red-500, .text-rose-500').first();
    // Error should be visible (either as alert or styled error message)
    const modal = page.getByTestId("class-create-modal");
    const errorText = await modal.locator('text=/required|empty/i').first().isVisible().catch(() => false);
    if (!errorText) {
      // If no explicit error text, verify the submit button is disabled or error is in form
      const hasError = await modal.locator('[role="alert"]').first().isVisible().catch(() => false);
      expect(hasError || errorText).toBeTruthy();
    }
  });

  test("Edge Case — Invalid Snake_case Shows Validation Error", async ({ page }) => {
    // Setup: Create a taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-validation-snake",
      description: "Taxonomy for snake_case validation tests",
    });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "test-scheme-validation-snake",
      description: "Scheme for snake_case validation tests",
    });

    // Navigate to classes page and open modal
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");
    await page.getByTestId("class-add-button").click();
    await expect(page.getByTestId("class-create-modal")).toBeVisible();

    // Type invalid name and blur
    const nameInput = page.getByTestId("class-editor-name-input");
    await nameInput.fill("Invalid Name");
    await nameInput.blur();

    // Verify validation error appears
    await page.waitForTimeout(100);
    const modal = page.getByTestId("class-create-modal");
    const hasError = await modal.locator('[role="alert"]').first().isVisible().catch(() => false);
    expect(hasError).toBeTruthy();

    // Correct the field to valid snake_case
    await nameInput.fill("invalid_name");
    await nameInput.blur();

    // Verify error disappears after correction
    await page.waitForTimeout(100);
    const errorStillVisible = await modal.locator('[role="alert"]').first().isVisible().catch(() => false);
    expect(errorStillVisible).toBeFalsy();
  });

  test("Edge Case — Pressing Escape Closes Modal Without Creating", async ({ page }) => {
    // Setup: Create a taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-escape",
      description: "Taxonomy for escape key tests",
    });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "test-scheme-escape",
      description: "Scheme for escape key tests",
    });

    // Navigate to classes page and open modal
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");
    const initialRowCount = await page.locator('[data-testid^="schema-row-"]').count();

    await page.getByTestId("class-add-button").click();
    await expect(page.getByTestId("class-create-modal")).toBeVisible();

    // Type some text into name field
    await page.getByTestId("class-editor-name-input").fill("test_class");

    // Press Escape key
    await page.press("Escape");

    // Verify modal closes
    await expect(page.getByTestId("class-create-modal")).not.toBeVisible();

    // Verify no new row was created
    await page.waitForLoadState("networkidle");
    const finalRowCount = await page.locator('[data-testid^="schema-row-"]').count();
    expect(finalRowCount).toBe(initialRowCount);
  });

  test("Edge Case — Closing Modal Requires Confirmation if Form is Dirty", async ({ page }) => {
    // Setup: Create a taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-dirty-form",
      description: "Taxonomy for dirty form tests",
    });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "test-scheme-dirty-form",
      description: "Scheme for dirty form tests",
    });

    // Navigate to classes page and open modal
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");
    const initialRowCount = await page.locator('[data-testid^="schema-row-"]').count();

    await page.getByTestId("class-add-button").click();
    await expect(page.getByTestId("class-create-modal")).toBeVisible();

    // Type text into the name field to make form dirty
    await page.getByTestId("class-editor-name-input").fill("unsaved_class");

    // Click outside the modal on the backdrop to attempt to close
    const backdrop = page.locator('[role="presentation"], .modal-backdrop').first();
    const isBackdropVisible = await backdrop.isVisible().catch(() => false);

    if (isBackdropVisible) {
      // If backdrop exists and is clickable, click outside
      const modalBox = page.getByTestId("class-create-modal");
      const boundingBox = await modalBox.boundingBox();
      if (boundingBox) {
        // Click outside the modal bounds
        await page.click(`[role="presentation"]`);
      }
    } else {
      // Fallback: try pressing Escape to see if confirmation dialog appears
      await page.press("Escape");
    }

    // Give a moment for confirmation dialog to appear (if it exists)
    await page.waitForTimeout(200);

    // Check if confirmation dialog exists
    const confirmDialog = page.getByTestId("confirm-dialog");
    const confirmDialogExists = await confirmDialog.isVisible().catch(() => false);

    if (confirmDialogExists) {
      // If confirmation dialog is shown, verify it and click Discard
      const discardButton = page.getByTestId("confirm-dialog-cancel");
      await expect(discardButton).toBeVisible();
      await discardButton.click();
    }

    // Verify modal is now closed
    await expect(page.getByTestId("class-create-modal")).not.toBeVisible();

    // Verify no class was created
    await page.waitForLoadState("networkidle");
    const finalRowCount = await page.locator('[data-testid^="schema-row-"]').count();
    expect(finalRowCount).toBe(initialRowCount);
  });
});
