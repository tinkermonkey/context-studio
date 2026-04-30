import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  clearTestData,
  apiRequest,
  waitForAppReady,
} from "../../fixtures/test-helpers";

/**
 * Taxonomy CRUD E2E Tests
 *
 * Tests the complete CRUD lifecycle for taxonomies:
 * - Create a new taxonomy
 * - List taxonomies and verify presence
 * - View taxonomy details
 * - Update taxonomy properties
 * - Delete taxonomy
 * - Validate form behavior
 * - Verify special character handling
 *
 * Each test uses beforeEach to create preconditions and verifies both
 * UI state and API responses via apiRequest read-back.
 */

test.describe("Taxonomy CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a taxonomy via UI form", async ({ page }) => {
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

  test("should list all taxonomies", async ({ page }) => {
    // Create test data
    const taxonomy1 = await createTaxonomy(page, {
      title: "List Test Taxonomy 1",
    });
    const taxonomy2 = await createTaxonomy(page, {
      title: "List Test Taxonomy 2",
    });

    // Navigate to taxonomies page
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // Verify both taxonomies appear in the list
    await expect(page.getByText("List Test Taxonomy 1")).toBeVisible();
    await expect(page.getByText("List Test Taxonomy 2")).toBeVisible();

    // Verify API response includes both
    const response = await apiRequest<any>(page, "/api/taxonomies");
    const titles =
      response.items?.map((t: any) => t.title) ||
      response.map((t: any) => t.title) ||
      [];
    expect(titles).toContain(taxonomy1.title);
    expect(titles).toContain(taxonomy2.title);
  });

  test("should view taxonomy details", async ({ page }) => {
    // Create test taxonomy
    const taxonomy = await createTaxonomy(page, {
      title: "Detail Test Taxonomy",
      description: "Test description for details",
    });

    // Navigate to taxonomies page
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // Click on taxonomy row to view details
    const taxonomyLink = page.getByText("Detail Test Taxonomy");
    await taxonomyLink.click();

    // Wait for detail page to load
    await page.waitForLoadState("networkidle");

    // Verify detail page contains taxonomy information
    await expect(page.getByText("Detail Test Taxonomy")).toBeVisible();
    await expect(page.getByText("Test description for details")).toBeVisible();

    // Verify API read-back returns same data
    const apiResponse = await apiRequest<any>(
      page,
      `/api/taxonomies/${taxonomy.id}`,
    );
    expect(apiResponse.title).toBe(taxonomy.title);
    expect(apiResponse.description).toBe(taxonomy.description);
  });

  test("should update a taxonomy", async ({ page }) => {
    // Create test taxonomy
    const taxonomy = await createTaxonomy(page, {
      title: "Update Test Taxonomy",
      description: "Original description",
    });

    // Navigate to taxonomies page
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // Find and double-click row to open edit form
    const taxonomyRow = page.getByText("Update Test Taxonomy");
    await taxonomyRow.dblclick();

    // Wait for edit form
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Update fields
    const titleInput = page
      .locator('[data-testid="taxonomy-title-input"]')
      .first();
    const descriptionInput = page
      .locator('[data-testid="taxonomy-description-input"]')
      .first();

    await titleInput.fill("test-taxonomy-e2e-update");
    await descriptionInput.fill("Updated description");

    // Submit form
    const submitButton = modal.getByRole("button", { name: /save|update/i });
    await submitButton.click();

    // Wait for changes to apply
    await page.waitForLoadState("networkidle");

    // Verify updates in UI
    await expect(page.getByText("test-taxonomy-e2e-update")).toBeVisible();

    // Verify updates via API
    const apiResponse = await apiRequest<any>(
      page,
      `/api/taxonomies/${taxonomy.id}`,
    );
    expect(apiResponse.title).toBe("test-taxonomy-e2e-update");
    expect(apiResponse.description).toBe("Updated description");
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

    // Verify via API that it's deleted
    try {
      await apiRequest<any>(page, `/api/taxonomies/${taxonomy.id}`);
      // If we get here, the taxonomy still exists, which is a failure
      throw new Error("Taxonomy was not deleted from API");
    } catch (error: any) {
      // 404 is expected
      if (!error.message.includes("404")) {
        throw error;
      }
    }
  });

  test("should verify taxonomy fields are persisted correctly", async ({
    page,
  }) => {
    // Create taxonomy with all fields populated
    const testTitle = `Field Test ${Date.now()}`;
    const testDescription = "Testing all field persistence";

    const taxonomy = await createTaxonomy(page, {
      title: testTitle,
      description: testDescription,
    });

    // Navigate to taxonomies page
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // Verify all fields visible in list
    await expect(page.getByText(testTitle)).toBeVisible();
    await expect(page.getByText(testDescription)).toBeVisible();

    // Verify API response has all fields
    const apiResponse = await apiRequest<any>(
      page,
      `/api/taxonomies/${taxonomy.id}`,
    );
    expect(apiResponse.title).toBe(testTitle);
    expect(apiResponse.description).toBe(testDescription);
    expect(apiResponse.id).toBeDefined();
    expect(apiResponse.version).toBeDefined();
    expect(apiResponse.created_at).toBeDefined();
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
