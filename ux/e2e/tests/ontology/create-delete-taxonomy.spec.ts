import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  waitForAppReady,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Taxonomy CRUD: Create and Delete", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });
  test("should create a taxonomy via the UI form", async ({ page }) => {
    // Navigate to taxonomies page
    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    // Click "Add" button to open the form
    await page.getByTestId("taxonomy-add-button").click();

    // Wait for form to be visible
    const form = page.getByTestId("taxonomy-form");
    await expect(form).toBeVisible();

    // Fill in the taxonomy title
    await page.getByTestId("taxonomy-title-input").fill("Test Taxonomy");

    // Fill in the description
    await page.getByTestId("taxonomy-description-input").fill(
      "A test taxonomy for validation",
    );

    // Submit the form
    await page.getByTestId("taxonomy-submit-button").click();

    // Wait for the form to close and page to update
    await expect(form).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify the taxonomy appears in the list
    await expect(page.getByText("Test Taxonomy")).toBeVisible();
  });

  test("should delete a taxonomy via the UI", async ({ page }) => {
    // Create a taxonomy using the factory (faster setup)
    const taxonomy = await createTaxonomy(page, {
      title: "Taxonomy to Delete",
      description: "This will be deleted",
    });

    // Navigate to taxonomies page
    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    // Wait for the taxonomy to appear in the list
    await expect(page.getByText("Taxonomy to Delete")).toBeVisible();

    // Click the delete action (using pattern selector for the row)
    const rowSelector = `taxonomy-row-${taxonomy.id}`;
    const deleteButton = page
      .getByTestId(rowSelector)
      .getByRole("button", { name: /delete/i });
    await deleteButton.click();

    // Confirm the deletion in the modal
    const deleteModal = page.getByTestId("taxonomy-delete-modal");
    await expect(deleteModal).toBeVisible();

    // Click the confirm button in the modal
    await page.getByTestId("taxonomy-delete-confirm-button").click();

    // Wait for the modal to close
    await expect(deleteModal).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify the taxonomy is no longer visible in the list
    await expect(page.getByText("Taxonomy to Delete")).not.toBeVisible();
  });

  test("should validate required fields when creating a taxonomy", async ({
    page,
  }) => {
    // Navigate to taxonomies page
    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    // Click "Add" button
    await page.getByTestId("taxonomy-add-button").click();

    // Wait for form to be visible
    const form = page.getByTestId("taxonomy-form");
    await expect(form).toBeVisible();

    // Try to submit without filling in required title
    await page.getByTestId("taxonomy-submit-button").click();

    // Form should still be visible (not submitted due to validation)
    await expect(form).toBeVisible();

    // Expect validation error message
    await expect(page.getByRole("alert")).toContainText("required");
  });

  test("should preserve special characters in taxonomy title", async ({
    page,
  }) => {
    // Navigate to taxonomies page
    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    // Click "Add" button
    await page.getByTestId("taxonomy-add-button").click();

    // Wait for form
    const form = page.getByTestId("taxonomy-form");
    await expect(form).toBeVisible();

    // Fill in title with special characters
    const specialTitle = "Test™ Taxón°mý";
    await page.getByTestId("taxonomy-title-input").fill(specialTitle);

    // Fill in description
    await page.getByTestId("taxonomy-description-input").fill("Special chars");

    // Submit the form
    await page.getByTestId("taxonomy-submit-button").click();

    // Wait for form to close
    await expect(form).not.toBeVisible();
    await page.waitForLoadState("networkidle");

    // Verify the taxonomy with special characters appears
    await expect(page.getByText(specialTitle)).toBeVisible();
  });

});
