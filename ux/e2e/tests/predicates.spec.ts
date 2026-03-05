import { test, expect } from "@playwright/test";
import { apiRequest } from "../fixtures/test-helpers";

/**
 * Predicate Management E2E Tests
 *
 * These tests validate the complete CRUD workflow for predicates:
 * - Creating predicates through the table view
 * - Editing predicates through modals
 * - Deleting predicates with confirmation
 * - Searching predicates
 * - Validating predicate form fields
 */

test.describe("Predicate Management", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to predicates page
    await page.goto("/app/predicates");
    await page.waitForLoadState("networkidle");
  });

  test("should display the predicates table", async ({ page }) => {
    // Verify table is visible
    await expect(page.locator('[data-testid="predicate-table"]')).toBeVisible();

    // Verify toolbar is visible with add button
    await expect(
      page.locator('[data-testid="predicate-table-toolbar"]'),
    ).toBeVisible();
    await expect(
      page.locator('[data-testid="predicate-add-button"]'),
    ).toBeVisible();
  });

  test("should create a new predicate", async ({ page }) => {
    const predicateTitle = `E2E Test Predicate ${Date.now()}`;
    const predicateDefinition = "A test predicate created by E2E tests";

    // Click "Add Predicate" button
    await page.click('[data-testid="predicate-add-button"]');

    // Wait for create modal to appear
    await expect(
      page.getByRole("dialog", { name: "Create New Predicate" }),
    ).toBeVisible();

    // Fill in the form
    await page.fill('[data-testid="predicate-title-input"]', predicateTitle);
    await page.fill(
      '[data-testid="predicate-definition-input"]',
      predicateDefinition,
    );

    // The identifier should be auto-generated, but we can verify it's there
    const identifierValue = await page
      .locator('[data-testid="predicate-identifier-input"]')
      .inputValue();
    expect(identifierValue).toBeTruthy();

    // Submit the form
    await page.click('[data-testid="predicate-submit-button"]');

    // Wait for modal to close
    await expect(
      page.getByRole("dialog", { name: "Create New Predicate" }),
    ).not.toBeVisible();

    // Verify predicate appears in the table
    await expect(page.locator('[data-testid="predicate-table"]')).toContainText(
      predicateTitle,
    );

    // Verify predicate exists in backend
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response = await apiRequest<{ data: any[] }>(page, "/api/predicates");
    const createdPredicate = response.data.find(
       
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (p: any) => p.title === predicateTitle,

    expect(createdPredicate).toBeDefined();
    expect(createdPredicate?.definition).toBe(predicateDefinition);
  });

  test("should create a predicate with custom identifier", async ({ page }) => {
    const predicateTitle = `E2E Custom ID ${Date.now()}`;
    const customIdentifier = `custom_id_${Date.now()}`;

    // Click "Add Predicate" button
    await page.click('[data-testid="predicate-add-button"]');

    // Wait for create modal
    await expect(
      page.getByRole("dialog", { name: "Create New Predicate" }),
    ).toBeVisible();

    // Fill in the form with custom identifier
    await page.fill('[data-testid="predicate-title-input"]', predicateTitle);
    await page.fill(
      '[data-testid="predicate-identifier-input"]',
      customIdentifier,
    );

    // Submit the form
    await page.click('[data-testid="predicate-submit-button"]');

    // Wait for modal to close
    await expect(
      page.getByRole("dialog", { name: "Create New Predicate" }),
    ).not.toBeVisible();

    // Verify predicate exists in backend with custom identifier
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response = await apiRequest<{ data: any[] }>(page, "/api/predicates");
    const createdPredicate = response.data.find(
       
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (p: any) => p.title === predicateTitle,

    expect(createdPredicate).toBeDefined();
    expect(createdPredicate?.identifier).toBe(customIdentifier);
  });

  test("should edit a predicate through the table", async ({ page }) => {
    // First, create a predicate to edit
    const originalTitle = `E2E Edit Test ${Date.now()}`;
    const updatedTitle = `${originalTitle} (Updated)`;
    const updatedDefinition = "Updated definition via E2E test";

    // Create predicate via API for speed
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const createResponse = await apiRequest<any>(page, "/api/predicates", {
      method: "POST",
      body: {
        title: originalTitle,
        definition: "Original definition",
      },
    });
    const predicateId = createResponse.id;

    // Refresh the page to see the new predicate
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Double-click the predicate row to edit
    await page
      .locator(`[data-testid="predicate-row-${predicateId}"]`)
      .dblclick();

    // Wait for edit modal
    await expect(
      page.getByRole("dialog", { name: "Edit Predicate" }),
    ).toBeVisible();

    // Clear and update the title
    await page.fill('[data-testid="predicate-title-input"]', updatedTitle);
    await page.fill(
      '[data-testid="predicate-definition-input"]',
      updatedDefinition,
    );

    // Submit
    await page.click('[data-testid="predicate-submit-button"]');

    // Wait for modal to close
    await expect(
      page.getByRole("dialog", { name: "Edit Predicate" }),
    ).not.toBeVisible();

    // Verify updated values appear in table
    await expect(page.locator('[data-testid="predicate-table"]')).toContainText(
      updatedTitle,
    );

    // Verify backend was updated
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response = await apiRequest<any>(
      page,
      `/api/predicates/${predicateId}`,
    );
    expect(response.title).toBe(updatedTitle);
    expect(response.definition).toBe(updatedDefinition);
  });

  test("should delete a predicate", async ({ page }) => {
    // Create a predicate to delete
    const predicateTitle = `E2E Delete Test ${Date.now()}`;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const createResponse = await apiRequest<any>(page, "/api/predicates", {
      method: "POST",
      body: {
        title: predicateTitle,
        definition: "Predicate to be deleted",
      },
    });
    const predicateId = createResponse.id;

    // Refresh to see the predicate
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Select the predicate row by clicking its checkbox
    const row = page.locator(`[data-testid="predicate-row-${predicateId}"]`);
    await row.locator('input[type="checkbox"]').check();

    // Click Actions dropdown and select Delete
    await page.click('[data-testid="predicate-actions-dropdown"]');
    await page.click('[data-testid="predicate-delete-selected-action"]');

    // Wait for delete confirmation modal
    await expect(
      page.getByRole("dialog", { name: /Confirm Delete/i }),
    ).toBeVisible();

    // Confirm deletion
    await page.click('[data-testid="predicate-delete-confirm-button"]');

    // Wait for modal to close
    await expect(
      page.getByRole("dialog", { name: /Confirm Delete/i }),
    ).not.toBeVisible();

    // Verify predicate is removed from table
    await expect(
      page.locator('[data-testid="predicate-table"]'),
    ).not.toContainText(predicateTitle);

    // Verify predicate is deleted from backend
    try {
      await apiRequest(page, `/api/predicates/${predicateId}`);
      // If we get here, the predicate wasn't deleted
      expect(false).toBe(true); // Force fail
    } catch (error) {
      // Expected - predicate should be deleted
      expect(error).toBeDefined();
    }
  });

  test("should search for predicates", async ({ page }) => {
    // Create multiple predicates with distinct names
    const timestamp = Date.now();
    const predicate1Title = `Alpha Predicate ${timestamp}`;
    const predicate2Title = `Beta Predicate ${timestamp}`;
    const predicate3Title = `Gamma Predicate ${timestamp}`;

    // Create predicates via API
    await Promise.all([
      apiRequest(page, "/api/predicates", {
        method: "POST",
        body: { title: predicate1Title },
      }),
      apiRequest(page, "/api/predicates", {
        method: "POST",
        body: { title: predicate2Title },
      }),
      apiRequest(page, "/api/predicates", {
        method: "POST",
        body: { title: predicate3Title },
      }),
    ]);

    // Refresh page
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Verify all predicates are visible initially
    await expect(page.locator('[data-testid="predicate-table"]')).toContainText(
      predicate1Title,
    );
    await expect(page.locator('[data-testid="predicate-table"]')).toContainText(
      predicate2Title,
    );
    await expect(page.locator('[data-testid="predicate-table"]')).toContainText(
      predicate3Title,
    );

    // Search for "Beta"
    await page.fill('[data-testid="predicate-search-input"]', "Beta");

    // Wait a bit for search to filter (debounced)
    await page.waitForTimeout(500);

    // Verify only Beta predicate is visible
    await expect(page.locator('[data-testid="predicate-table"]')).toContainText(
      predicate2Title,
    );
    await expect(
      page.locator('[data-testid="predicate-table"]'),
    ).not.toContainText(predicate1Title);
    await expect(
      page.locator('[data-testid="predicate-table"]'),
    ).not.toContainText(predicate3Title);

    // Clear search
    await page.fill('[data-testid="predicate-search-input"]', "");
    await page.waitForTimeout(500);

    // Verify all predicates are visible again
    await expect(page.locator('[data-testid="predicate-table"]')).toContainText(
      predicate1Title,
    );
    await expect(page.locator('[data-testid="predicate-table"]')).toContainText(
      predicate2Title,
    );
    await expect(page.locator('[data-testid="predicate-table"]')).toContainText(
      predicate3Title,
    );
  });

  test("should validate required fields", async ({ page }) => {
    // Click "Add Predicate" button
    await page.click('[data-testid="predicate-add-button"]');

    // Wait for create modal
    await expect(
      page.getByRole("dialog", { name: "Create New Predicate" }),
    ).toBeVisible();

    // Try to submit without filling in title (required field) - HTML5 validation will prevent submission
    await page.click('[data-testid="predicate-submit-button"]');

    // Modal should still be visible (HTML5 validation prevented submission)
    await expect(
      page.getByRole("dialog", { name: "Create New Predicate" }),
    ).toBeVisible();

    // Verify the title input field is marked as invalid (HTML5 validation)
    const titleInput = page.locator('[data-testid="predicate-title-input"]');
    await expect(titleInput).toHaveAttribute("required");
  });

  test("should handle multiple predicate selections and bulk delete", async ({
    page,
  }) => {
    // Create multiple predicates
    const timestamp = Date.now();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const predicate1 = await apiRequest<any>(page, "/api/predicates", {
      method: "POST",
      body: { title: `Bulk Delete 1 ${timestamp}` },
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const predicate2 = await apiRequest<any>(page, "/api/predicates", {
      method: "POST",
      body: { title: `Bulk Delete 2 ${timestamp}` },
    });

    // Refresh
    await page.reload();
    await page.waitForLoadState("networkidle");

    // Select both predicates
    await page
      .locator(`[data-testid="predicate-row-${predicate1.id}"]`)
      .locator('input[type="checkbox"]')
      .check();
    await page
      .locator(`[data-testid="predicate-row-${predicate2.id}"]`)
      .locator('input[type="checkbox"]')
      .check();

    // Delete selected
    await page.click('[data-testid="predicate-actions-dropdown"]');
    await page.click('[data-testid="predicate-delete-selected-action"]');

    // Confirm
    const deleteModal = page.getByRole("dialog", { name: /Confirm Delete/i });
    await expect(deleteModal).toBeVisible();
    await expect(deleteModal).toContainText("2 selected");
    await page.click('[data-testid="predicate-delete-confirm-button"]');

    // Wait for modal to close
    await expect(deleteModal).not.toBeVisible();

    // Verify both predicates are gone
    await expect(
      page.locator('[data-testid="predicate-table"]'),
    ).not.toContainText(`Bulk Delete 1 ${timestamp}`);
    await expect(
      page.locator('[data-testid="predicate-table"]'),
    ).not.toContainText(`Bulk Delete 2 ${timestamp}`);
  });

  test("should cancel predicate creation", async ({ page }) => {
    // Get current predicate count
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const beforeResponse = await apiRequest<{ data: any[]; total: number }>(
      page,
      "/api/predicates",
    );
    const beforeCount = beforeResponse.total;

    // Click "Add Predicate" button
    await page.click('[data-testid="predicate-add-button"]');

    // Wait for create modal
    const createModal = page.getByRole("dialog", {
      name: "Create New Predicate",
    });
    await expect(createModal).toBeVisible();

    // Fill in some data but don't submit
    await page.fill(
      '[data-testid="predicate-title-input"]',
      "Test Predicate Not Submitted",
    );

    // Navigate away to close the modal
    await page.goto("/app/predicates");
    await page.waitForLoadState("networkidle");

    // Verify no new predicate was created
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const afterResponse = await apiRequest<{ data: any[]; total: number }>(
      page,
      "/api/predicates",
    );
    const afterCount = afterResponse.total;

    expect(afterCount).toBe(beforeCount);

    // Verify the specific test predicate was not created
    const testPredicate = afterResponse.data.find(
       
      (p: any) => );  // eslint-disable-line @typescript-eslint/no-explicit-any p.title === "Test Predicate Not Submitted",
    expect(testPredicate).toBeUndefined();
  });

  test("should validate identifier format", async ({ page }) => {
    // Click "Add Predicate" button
    await page.click('[data-testid="predicate-add-button"]');

    // Wait for create modal
    await expect(
      page.getByRole("dialog", { name: "Create New Predicate" }),
    ).toBeVisible();

    // Fill in title
    await page.fill('[data-testid="predicate-title-input"]', "Test Predicate");

    // Try to enter an invalid identifier (with special characters not allowed)
    await page.fill(
      '[data-testid="predicate-identifier-input"]',
      "invalid-identifier!@#",
    );

    // Blur the identifier field to trigger validation
    await page.locator('[data-testid="predicate-title-input"]').click();

    // Check if there's an error message displayed
    // The form should show validation error for invalid identifier format
    const modalBody = page.getByRole("dialog", {
      name: "Create New Predicate",
    });
    await expect(modalBody).toContainText(/can only contain/i);
  });
});
