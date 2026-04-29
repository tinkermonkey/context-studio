import { test, expect } from "@playwright/test";
import {
  createTestHierarchy,
  createClass,
  clearTestData,
  apiRequest,
} from "../../fixtures/test-helpers";

/**
 * Ontology Class CRUD E2E Tests
 *
 * Tests the complete CRUD lifecycle for ontology classes:
 * - Create a class within a concept scheme
 * - List classes
 * - View class details
 * - Update class properties
 * - Delete class
 *
 * Each test uses beforeEach factory to create preconditions and verifies both
 * UI state and API responses via apiRequest read-back.
 */

test.describe("Ontology Class CRUD Operations", () => {
  let schemeId: string;

  test.beforeEach(async ({ page }) => {
    // Create test hierarchy (taxonomy, scheme, and property for relationships)
    const hierarchy = await createTestHierarchy(page, 1);
    schemeId = hierarchy.scheme.id;
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a class via UI", async ({ page }) => {
    // Navigate to classes page
    await page.goto("/app/classes");
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
      .locator('[data-testid="class-title-input"]')
      .first();
    const definitionInput = page
      .locator('[data-testid="class-definition-input"]')
      .first();

    await titleInput.fill("test-class-e2e-create");
    await definitionInput.fill("A test class created via E2E tests");

    // Submit form
    const submitButton = modal.getByRole("button", {
      name: /create|save|submit/i,
    });
    await submitButton.click();

    // Wait for modal to close
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // Verify class appears in table
    await expect(page.getByText("test-class-e2e-create")).toBeVisible();
  });

  test("should create a class within a concept scheme", async ({ page }) => {
    // Create class within specific scheme
    const ontologyClass = await createClass(page, schemeId, {
      title: "Scheme Specific Class",
      definition: "Class created under specific scheme",
    });

    // Navigate to classes page
    await page.goto("/app/classes");
    await page.waitForLoadState("networkidle");

    // Verify class appears in list
    await expect(page.getByText("Scheme Specific Class")).toBeVisible();

    // Verify class is linked to correct scheme
    const apiResponse = await apiRequest<any>(
      page,
      `/api/classes/${ontologyClass.id}`,
    );
    expect(apiResponse.scheme_id).toBe(schemeId);
  });

  test("should list all classes", async ({ page }) => {
    // Create test classes
    const class1 = await createClass(page, schemeId, {
      title: "List Test Class 1",
    });
    const class2 = await createClass(page, schemeId, {
      title: "List Test Class 2",
    });

    // Navigate to classes page
    await page.goto("/app/classes");
    await page.waitForLoadState("networkidle");

    // Verify both classes appear in the list
    await expect(page.getByText("List Test Class 1")).toBeVisible();
    await expect(page.getByText("List Test Class 2")).toBeVisible();

    // Verify API response includes both
    const response = await apiRequest<any>(page, "/api/classes");
    const titles =
      response.items?.map((c: any) => c.title) ||
      response.map((c: any) => c.title) ||
      [];
    expect(titles).toContain(class1.title);
    expect(titles).toContain(class2.title);
  });

  test("should view class details", async ({ page }) => {
    // Create test class
    const ontologyClass = await createClass(page, schemeId, {
      title: "Detail Test Class",
      definition: "Test definition for class details",
    });

    // Navigate to classes page
    await page.goto("/app/classes");
    await page.waitForLoadState("networkidle");

    // Click on class row to view details
    const classLink = page.getByText("Detail Test Class");
    await classLink.click();

    // Wait for detail page to load
    await page.waitForLoadState("networkidle");

    // Verify detail page contains class information
    await expect(page.getByText("Detail Test Class")).toBeVisible();
    await expect(
      page.getByText("Test definition for class details"),
    ).toBeVisible();

    // Verify API read-back returns same data
    const apiResponse = await apiRequest<any>(
      page,
      `/api/classes/${ontologyClass.id}`,
    );
    expect(apiResponse.title).toBe(ontologyClass.title);
    expect(apiResponse.definition).toBe(ontologyClass.definition);
  });

  test("should update a class", async ({ page }) => {
    // Create test class
    const ontologyClass = await createClass(page, schemeId, {
      title: "Update Test Class",
      definition: "Original definition",
    });

    // Navigate to classes page
    await page.goto("/app/classes");
    await page.waitForLoadState("networkidle");

    // Find and double-click row to open edit form
    const classRow = page.getByText("Update Test Class");
    await classRow.dblclick();

    // Wait for edit form
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Update fields
    const titleInput = page
      .locator('[data-testid="class-title-input"]')
      .first();
    const definitionInput = page
      .locator('[data-testid="class-definition-input"]')
      .first();

    await titleInput.fill("test-class-e2e-update");
    await definitionInput.fill("Updated class definition");

    // Submit form
    const submitButton = modal.getByRole("button", { name: /save|update/i });
    await submitButton.click();

    // Wait for changes to apply
    await page.waitForLoadState("networkidle");

    // Verify updates in UI
    await expect(page.getByText("test-class-e2e-update")).toBeVisible();

    // Verify updates via API
    const apiResponse = await apiRequest<any>(
      page,
      `/api/classes/${ontologyClass.id}`,
    );
    expect(apiResponse.title).toBe("test-class-e2e-update");
    expect(apiResponse.definition).toBe("Updated class definition");
  });

  test("should delete a class", async ({ page }) => {
    // Create test class
    const ontologyClass = await createClass(page, schemeId, {
      title: "Delete Test Class",
    });

    // Navigate to classes page
    await page.goto("/app/classes");
    await page.waitForLoadState("networkidle");

    // Verify class is visible
    await expect(page.getByText("Delete Test Class")).toBeVisible();

    // Find the row and select it via checkbox
    const classRow = page.getByText("Delete Test Class");
    const rowContainer = classRow.locator("..").locator("..");
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

    // Verify class is removed from UI
    await expect(page.getByText("Delete Test Class")).not.toBeVisible({
      timeout: 5000,
    });

    // Verify via API that it's deleted
    try {
      await apiRequest<any>(page, `/api/classes/${ontologyClass.id}`);
      throw new Error("Class was not deleted from API");
    } catch (error: any) {
      if (!error.message.includes("404")) {
        throw error;
      }
    }
  });

  test("should verify class fields are persisted correctly", async ({
    page,
  }) => {
    // Create class with all fields populated
    const testTitle = `Field Test ${Date.now()}`;
    const testDefinition = "Testing all field persistence";

    const ontologyClass = await createClass(page, schemeId, {
      title: testTitle,
      definition: testDefinition,
    });

    // Navigate to classes page
    await page.goto("/app/classes");
    await page.waitForLoadState("networkidle");

    // Verify all fields visible in list
    await expect(page.getByText(testTitle)).toBeVisible();
    await expect(page.getByText(testDefinition)).toBeVisible();

    // Verify API response has all fields
    const apiResponse = await apiRequest<any>(
      page,
      `/api/classes/${ontologyClass.id}`,
    );
    expect(apiResponse.title).toBe(testTitle);
    expect(apiResponse.definition).toBe(testDefinition);
    expect(apiResponse.id).toBeDefined();
    expect(apiResponse.scheme_id).toBe(schemeId);
    expect(apiResponse.created_at).toBeDefined();
  });
});
