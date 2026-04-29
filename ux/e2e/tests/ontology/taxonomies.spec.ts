import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  clearTestData,
  apiRequest,
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
 *
 * Each test uses beforeEach to create preconditions and verifies both
 * UI state and API responses via apiRequest read-back.
 */

test.describe("Taxonomy CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a taxonomy via UI", async ({ page }) => {
    // Navigate to taxonomies page
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // Click add button
    const addButton = page.getByRole("button", { name: /add|create|new/i });
    await expect(addButton).toBeVisible();
    await addButton.click();

    // Wait for form modal
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Fill form fields
    const titleInput = page.locator('[data-testid="taxonomy-title-input"]').first();
    const descriptionInput = page.locator('[data-testid="taxonomy-description-input"]').first();

    await titleInput.fill("test-taxonomy-e2e-create");
    await descriptionInput.fill("A test taxonomy created via E2E tests");

    // Submit form
    const submitButton = modal.getByRole("button", { name: /create|save|submit/i });
    await submitButton.click();

    // Wait for modal to close
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // Verify taxonomy appears in table
    await expect(page.getByText("test-taxonomy-e2e-create")).toBeVisible();
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
    const titles = response.items?.map((t: any) => t.title) ||
      response.map((t: any) => t.title) || [];
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
    const titleInput = page.locator('[data-testid="taxonomy-title-input"]').first();
    const descriptionInput = page.locator('[data-testid="taxonomy-description-input"]').first();

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

  test("should delete a taxonomy", async ({ page }) => {
    // Create test taxonomy
    const taxonomy = await createTaxonomy(page, {
      title: "Delete Test Taxonomy",
    });

    // Navigate to taxonomies page
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // Verify taxonomy is visible
    await expect(page.getByText("Delete Test Taxonomy")).toBeVisible();

    // Find the row and select it via checkbox
    const taxonomyRow = page.getByText("Delete Test Taxonomy");
    const rowContainer = taxonomyRow.locator("..").locator("..");
    const checkbox = rowContainer.locator("input[type='checkbox']").first();
    await checkbox.click();

    // Click Actions dropdown
    const actionsDropdown = page.getByRole("button", { name: /actions/i });
    await actionsDropdown.click();

    // Click Delete Selected
    const deleteAction = page.getByRole("menuitem", { name: /delete selected/i });
    await deleteAction.click();

    // Handle confirmation dialog if present
    const confirmButton = page.getByRole("button", {
      name: /confirm|delete|yes/i,
    });
    if (await confirmButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await confirmButton.click();
    }

    // Wait for deletion to complete
    await page.waitForLoadState("networkidle");

    // Verify taxonomy is removed from UI
    await expect(page.getByText("Delete Test Taxonomy")).not.toBeVisible({
      timeout: 5000,
    });

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
});
