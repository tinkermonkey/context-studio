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
    await createConceptScheme(page, taxonomy.id, {
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
    await createConceptScheme(page, taxonomy.id, {
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
    // Wait for listbox to appear, then select the first option
    const listbox = page.locator('[role="listbox"]');
    await expect(listbox).toBeVisible();
    const firstOption = listbox.locator('[role="option"]').first();
    await firstOption.click();

    // Submit the form
    const submitButton = page.getByTestId("class-editor-submit-button");
    await submitButton.click();

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
    await createConceptScheme(page, taxonomy.id, {
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
    // Wait for listbox to appear, then select the first option
    const listbox = page.locator('[role="listbox"]');
    await expect(listbox).toBeVisible();
    const firstOption = listbox.locator('[role="option"]').first();
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
    await createConceptScheme(page, taxonomy.id, {
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
    // Wait for listbox to appear, then select the first option
    const listbox = page.locator('[role="listbox"]');
    await expect(listbox).toBeVisible();
    const firstOption = listbox.locator('[role="option"]').first();
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
    await createConceptScheme(page, taxonomy.id, {
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

    // Verify validation error appears with proper assertion and auto-retry
    const modal = page.getByTestId("class-create-modal");
    const errorAlert = modal.locator('[role="alert"]');
    await expect(errorAlert).toBeVisible();
  });

  test("Edge Case — Invalid Snake_case Shows Validation Error", async ({ page }) => {
    // Setup: Create a taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-validation-snake",
      description: "Taxonomy for snake_case validation tests",
    });
    await createConceptScheme(page, taxonomy.id, {
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
    const modal = page.getByTestId("class-create-modal");
    const errorAlert = modal.locator('[role="alert"]');

    await nameInput.fill("Invalid Name");
    await nameInput.blur();

    // Verify validation error appears
    await expect(errorAlert).toBeVisible();

    // Correct the field to valid snake_case
    await nameInput.fill("invalid_name");
    await nameInput.blur();

    // Verify error disappears after correction (onChange handler should clear it)
    await expect(errorAlert).not.toBeVisible();
  });

  test("Edge Case — Pressing Escape Closes Modal Without Creating", async ({ page }) => {
    // Setup: Create a taxonomy and concept scheme
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-escape",
      description: "Taxonomy for escape key tests",
    });
    await createConceptScheme(page, taxonomy.id, {
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
    await page.keyboard.press("Escape");

    // Verify modal closes
    await expect(page.getByTestId("class-create-modal")).not.toBeVisible();

    // Verify no new row was created
    await page.waitForLoadState("networkidle");
    const finalRowCount = await page.locator('[data-testid^="schema-row-"]').count();
    expect(finalRowCount).toBe(initialRowCount);
  });

});
