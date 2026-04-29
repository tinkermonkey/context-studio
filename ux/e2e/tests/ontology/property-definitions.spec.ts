import { test, expect } from "@playwright/test";
import {
  createPropertyDefinition,
  clearTestData,
  apiRequest,
} from "../../fixtures/test-helpers";

/**
 * Property Definition CRUD E2E Tests
 *
 * Tests the complete CRUD lifecycle for property definitions:
 * - Create a new property definition
 * - List property definitions
 * - View property definition details
 * - Update property definition properties
 * - Delete property definition
 *
 * Each test uses beforeEach factory to create preconditions and verifies both
 * UI state and API responses via apiRequest read-back.
 */

test.describe("Property Definition CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a property definition via UI", async ({ page }) => {
    // Navigate to properties page
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");

    // Click add button
    const addButton = page.getByRole("button", { name: /add|create|new/i });
    await expect(addButton).toBeVisible();
    await addButton.click();

    // Wait for form modal
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Fill form fields
    const titleInput = page.locator("input[name='title']").first();
    const descriptionInput = page.locator("textarea[name='description']").first();

    await titleInput.fill("E2E Test Property");
    await descriptionInput.fill("A test property created via E2E tests");

    // Submit form
    const submitButton = modal.getByRole("button", {
      name: /create|save|submit/i,
    });
    await submitButton.click();

    // Wait for modal to close
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // Verify property appears in table
    await expect(page.getByText("E2E Test Property")).toBeVisible();
  });

  test("should create a property definition via API", async ({ page }) => {
    // Create property using API
    const property = await createPropertyDefinition(page, {
      title: "API Created Property",
      description: "Property created via API",
      range: "string",
    });

    // Verify property was created successfully
    expect(property.id).toBeDefined();
    expect(property.title).toBe("API Created Property");
    expect(property.description).toBe("Property created via API");
    expect(property.range).toBe("string");

    // Navigate to properties page to verify it appears in UI
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");

    // Verify property appears in list
    await expect(page.getByText("API Created Property")).toBeVisible();
  });

  test("should list all property definitions", async ({ page }) => {
    // Create test properties
    const prop1 = await createPropertyDefinition(page, {
      title: "List Test Property 1",
      range: "string",
    });
    const prop2 = await createPropertyDefinition(page, {
      title: "List Test Property 2",
      range: "integer",
    });

    // Navigate to properties page
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");

    // Verify both properties appear in the list
    await expect(page.getByText("List Test Property 1")).toBeVisible();
    await expect(page.getByText("List Test Property 2")).toBeVisible();

    // Verify API response includes both
    const response = await apiRequest<any>(page, "/api/properties");
    const titles = response.items?.map((p: any) => p.title) ||
      response.map((p: any) => p.title) || [];
    expect(titles).toContain(prop1.title);
    expect(titles).toContain(prop2.title);
  });

  test("should view property definition details", async ({ page }) => {
    // Create test property
    const property = await createPropertyDefinition(page, {
      title: "Detail Test Property",
      description: "Test description for property details",
      range: "string",
    });

    // Navigate to properties page
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");

    // Click on property row to view details
    const propertyLink = page.getByText("Detail Test Property");
    await propertyLink.click();

    // Wait for detail page to load
    await page.waitForLoadState("networkidle");

    // Verify detail page contains property information
    await expect(page.getByText("Detail Test Property")).toBeVisible();
    await expect(
      page.getByText("Test description for property details"),
    ).toBeVisible();

    // Verify API read-back returns same data
    const apiResponse = await apiRequest<any>(
      page,
      `/api/properties/${property.id}`,
    );
    expect(apiResponse.title).toBe(property.title);
    expect(apiResponse.description).toBe(property.description);
    expect(apiResponse.range).toBe(property.range);
  });

  test("should update a property definition", async ({ page }) => {
    // Create test property
    const property = await createPropertyDefinition(page, {
      title: "Update Test Property",
      description: "Original description",
      range: "string",
    });

    // Navigate to properties page
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");

    // Find and click edit button for property
    const propertyRow = page.getByText("Update Test Property");
    const rowContainer = propertyRow.locator("..");
    const editButton = rowContainer.getByRole("button", {
      name: /edit|update/i,
    });

    // Click edit button or double-click row
    if (await editButton.isVisible()) {
      await editButton.click();
    } else {
      await propertyRow.dblclick();
    }

    // Wait for edit form
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Update fields
    const titleInput = page.locator("input[name='title']").first();
    const descriptionInput = page.locator("textarea[name='description']").first();

    await titleInput.fill("Updated Property Title");
    await descriptionInput.fill("Updated property description");

    // Submit form
    const submitButton = modal.getByRole("button", { name: /save|update/i });
    await submitButton.click();

    // Wait for changes to apply
    await page.waitForLoadState("networkidle");

    // Verify updates in UI
    await expect(page.getByText("Updated Property Title")).toBeVisible();

    // Verify updates via API
    const apiResponse = await apiRequest<any>(
      page,
      `/api/properties/${property.id}`,
    );
    expect(apiResponse.title).toBe("Updated Property Title");
    expect(apiResponse.description).toBe("Updated property description");
  });

  test("should delete a property definition", async ({ page }) => {
    // Create test property
    const property = await createPropertyDefinition(page, {
      title: "Delete Test Property",
    });

    // Navigate to properties page
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");

    // Verify property is visible
    await expect(page.getByText("Delete Test Property")).toBeVisible();

    // Find and click delete button
    const propertyRow = page.getByText("Delete Test Property");
    const rowContainer = propertyRow.locator("..");
    const deleteButton = rowContainer.getByRole("button", {
      name: /delete|remove/i,
    });

    if (await deleteButton.isVisible()) {
      await deleteButton.click();

      // Handle confirmation dialog if present
      const confirmButton = page.getByRole("button", {
        name: /confirm|delete|yes/i,
      });
      if (await confirmButton.isVisible({ timeout: 2000 }).catch(() => false)) {
        await confirmButton.click();
      }
    }

    // Wait for deletion to complete
    await page.waitForLoadState("networkidle");

    // Verify property is removed from UI
    await expect(page.getByText("Delete Test Property")).not.toBeVisible({
      timeout: 5000,
    });

    // Verify via API that it's deleted
    try {
      await apiRequest<any>(page, `/api/properties/${property.id}`);
      throw new Error("Property was not deleted from API");
    } catch (error: any) {
      if (!error.message.includes("404")) {
        throw error;
      }
    }
  });

  test("should verify property definition fields are persisted correctly", async ({
    page,
  }) => {
    // Create property with all fields populated
    const testTitle = `Field Test ${Date.now()}`;
    const testDescription = "Testing all field persistence";
    const testRange = "string";

    const property = await createPropertyDefinition(page, {
      title: testTitle,
      description: testDescription,
      range: testRange,
    });

    // Navigate to properties page
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");

    // Verify all fields visible in list
    await expect(page.getByText(testTitle)).toBeVisible();
    await expect(page.getByText(testDescription)).toBeVisible();

    // Verify API response has all fields
    const apiResponse = await apiRequest<any>(
      page,
      `/api/properties/${property.id}`,
    );
    expect(apiResponse.title).toBe(testTitle);
    expect(apiResponse.description).toBe(testDescription);
    expect(apiResponse.range).toBe(testRange);
    expect(apiResponse.id).toBeDefined();
    expect(apiResponse.created_at).toBeDefined();
  });

  test("should support different property ranges", async ({ page }) => {
    // Create properties with different ranges
    const stringProp = await createPropertyDefinition(page, {
      title: "String Property",
      range: "string",
    });
    const intProp = await createPropertyDefinition(page, {
      title: "Integer Property",
      range: "integer",
    });
    const boolProp = await createPropertyDefinition(page, {
      title: "Boolean Property",
      range: "boolean",
    });

    // Verify each property has correct range via API
    const stringResponse = await apiRequest<any>(
      page,
      `/api/properties/${stringProp.id}`,
    );
    expect(stringResponse.range).toBe("string");

    const intResponse = await apiRequest<any>(
      page,
      `/api/properties/${intProp.id}`,
    );
    expect(intResponse.range).toBe("integer");

    const boolResponse = await apiRequest<any>(
      page,
      `/api/properties/${boolProp.id}`,
    );
    expect(boolResponse.range).toBe("boolean");
  });
});
