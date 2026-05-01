import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  clearTestData,
  apiRequest,
} from "../../fixtures/test-helpers";

/**
 * Concept Scheme CRUD E2E Tests
 *
 * Tests the complete CRUD lifecycle for concept schemes:
 * - Create a concept scheme within a taxonomy
 * - List concept schemes
 * - View concept scheme details
 * - Update concept scheme properties
 * - Delete concept scheme
 *
 * Each test uses beforeEach factory to create preconditions and verifies both
 * UI state and API responses via apiRequest read-back.
 */

test.describe("Concept Scheme CRUD Operations", () => {
  let taxonomyId: string;

  test.beforeEach(async ({ page }) => {
    // Create a parent taxonomy for schemes to belong to
    const taxonomy = await createTaxonomy(page, {
      title: "test-taxonomy-parent",
    });
    taxonomyId = taxonomy.id;
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a concept scheme via UI", async ({ page }) => {
    // Navigate to concept schemes page
    await page.goto("/app/concept-schemes");
    await page.waitForLoadState("networkidle");

    // Click add button
    const addButton = page.getByRole("button", { name: /add|create|new/i });
    await expect(addButton).toBeVisible();
    await addButton.click();

    // Wait for form modal
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Fill form fields
    const titleInput = page
      .locator('[data-testid="concept-scheme-title-input"]')
      .first();
    const descriptionInput = page
      .locator('[data-testid="concept-scheme-description-input"]')
      .first();

    await titleInput.fill("test-scheme-e2e-create");
    await descriptionInput.fill("A test scheme created via E2E tests");

    // Submit form
    const submitButton = modal.getByRole("button", {
      name: /create|save|submit/i,
    });
    await submitButton.click();

    // Wait for modal to close
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // Verify scheme appears in table
    await expect(page.getByText("test-scheme-e2e-create")).toBeVisible();
  });

  test("should create a concept scheme within a taxonomy", async ({ page }) => {
    // Use API to create scheme within specific taxonomy
    const scheme = await createConceptScheme(page, taxonomyId, {
      title: "Taxonomy Specific Scheme",
      description: "Scheme created under specific taxonomy",
    });

    // Navigate to concept schemes page
    await page.goto("/app/concept-schemes");
    await page.waitForLoadState("networkidle");

    // Verify scheme appears in list
    await expect(page.getByText("Taxonomy Specific Scheme")).toBeVisible();

    // Verify scheme is linked to correct taxonomy
    const apiResponse = await apiRequest<any>(
      page,
      `/api/schemes/${scheme.id}`,
    );
    expect(apiResponse.taxonomy_id).toBe(taxonomyId);
  });

  test("should list all concept schemes", async ({ page }) => {
    // Create test schemes
    const scheme1 = await createConceptScheme(page, taxonomyId, {
      title: "List Test Scheme 1",
    });
    const scheme2 = await createConceptScheme(page, taxonomyId, {
      title: "List Test Scheme 2",
    });

    // Navigate to concept schemes page
    await page.goto("/app/concept-schemes");
    await page.waitForLoadState("networkidle");

    // Verify both schemes appear in the list
    await expect(page.getByText("List Test Scheme 1")).toBeVisible();
    await expect(page.getByText("List Test Scheme 2")).toBeVisible();

    // Verify API response includes both
    const response = await apiRequest<any>(page, "/api/schemes");
    const titles =
      response.items?.map((s: any) => s.title) ||
      response.map((s: any) => s.title) ||
      [];
    expect(titles).toContain(scheme1.title);
    expect(titles).toContain(scheme2.title);
  });

  test("should view concept scheme details", async ({ page }) => {
    // Create test scheme
    const scheme = await createConceptScheme(page, taxonomyId, {
      title: "Detail Test Scheme",
      description: "Test description for scheme details",
    });

    // Navigate to concept schemes page
    await page.goto("/app/concept-schemes");
    await page.waitForLoadState("networkidle");

    // Click on scheme row to view details
    const schemeLink = page.getByText("Detail Test Scheme");
    await schemeLink.click();

    // Wait for detail page to load
    await page.waitForLoadState("networkidle");

    // Verify detail page contains scheme information
    await expect(page.getByText("Detail Test Scheme")).toBeVisible();
    await expect(
      page.getByText("Test description for scheme details"),
    ).toBeVisible();

    // Verify API read-back returns same data
    const apiResponse = await apiRequest<any>(
      page,
      `/api/schemes/${scheme.id}`,
    );
    expect(apiResponse.title).toBe(scheme.title);
    expect(apiResponse.description).toBe(scheme.description);
  });

  test("should update a concept scheme", async ({ page }) => {
    // Create test scheme
    const scheme = await createConceptScheme(page, taxonomyId, {
      title: "Update Test Scheme",
      description: "Original description",
    });

    // Navigate to concept schemes page
    await page.goto("/app/concept-schemes");
    await page.waitForLoadState("networkidle");

    // Find and double-click row to open edit form
    const schemeRow = page.getByText("Update Test Scheme");
    await schemeRow.dblclick();

    // Wait for edit form
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Update fields
    const titleInput = page
      .locator('[data-testid="concept-scheme-title-input"]')
      .first();
    const descriptionInput = page
      .locator('[data-testid="concept-scheme-description-input"]')
      .first();

    await titleInput.fill("test-scheme-e2e-update");
    await descriptionInput.fill("Updated scheme definition");

    // Submit form
    const submitButton = modal.getByRole("button", { name: /save|update/i });
    await submitButton.click();

    // Wait for changes to apply
    await page.waitForLoadState("networkidle");

    // Verify updates in UI
    await expect(page.getByText("test-scheme-e2e-update")).toBeVisible();

    // Verify updates via API
    const apiResponse = await apiRequest<any>(
      page,
      `/api/schemes/${scheme.id}`,
    );
    expect(apiResponse.title).toBe("test-scheme-e2e-update");
    expect(apiResponse.description).toBe("Updated scheme definition");
  });

  test("should delete a concept scheme", async ({ page }) => {
    // Create test scheme
    const scheme = await createConceptScheme(page, taxonomyId, {
      title: "Delete Test Scheme",
    });

    // Navigate to concept schemes page
    await page.goto("/app/concept-schemes");
    await page.waitForLoadState("networkidle");

    // Verify scheme is visible
    await expect(page.getByText("Delete Test Scheme")).toBeVisible();

    // Find the row and select it via checkbox
    const schemeRow = page.getByText("Delete Test Scheme");
    const rowContainer = schemeRow.locator("..").locator("..");
    const checkbox = rowContainer.locator("input[type='checkbox']").first();
    await checkbox.click();

    // Click Actions dropdown
    const actionsDropdown = page.getByRole("button", { name: /actions/i });
    await actionsDropdown.click();

    // Click Delete Selected
    const deleteAction = page.getByRole("menuitem", {
      name: /delete selected/i,
    });
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

    // Verify scheme is removed from UI
    await expect(page.getByText("Delete Test Scheme")).not.toBeVisible({
      timeout: 5000,
    });

    // Verify via API that it's deleted
    try {
      await apiRequest<any>(page, `/api/schemes/${scheme.id}`);
      throw new Error("Scheme was not deleted from API");
    } catch (error: any) {
      if (!error.message.includes("404")) {
        throw error;
      }
    }
  });

  test("should verify concept scheme fields are persisted correctly", async ({
    page,
  }) => {
    // Create scheme with all fields populated
    const testTitle = `Field Test ${Date.now()}`;
    const testDescription = "Testing all field persistence";

    const scheme = await createConceptScheme(page, taxonomyId, {
      title: testTitle,
      description: testDescription,
    });

    // Navigate to concept schemes page
    await page.goto("/app/concept-schemes");
    await page.waitForLoadState("networkidle");

    // Verify all fields visible in list
    await expect(page.getByText(testTitle)).toBeVisible();
    await expect(page.getByText(testDescription)).toBeVisible();

    // Verify API response has all fields
    const apiResponse = await apiRequest<any>(
      page,
      `/api/schemes/${scheme.id}`,
    );
    expect(apiResponse.title).toBe(testTitle);
    expect(apiResponse.description).toBe(testDescription);
    expect(apiResponse.id).toBeDefined();
    expect(apiResponse.taxonomy_id).toBe(taxonomyId);
    expect(apiResponse.created_at).toBeDefined();
  });
});
