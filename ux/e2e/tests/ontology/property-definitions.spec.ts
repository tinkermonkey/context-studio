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
    const titleInput = page
      .locator('[data-testid="property-definition-title-input"]')
      .first();
    const descriptionInput = page
      .locator('[data-testid="property-definition-description-input"]')
      .first();

    await titleInput.fill("test-property-e2e-create");
    await descriptionInput.fill("A test property created via E2E tests");

    // Submit form
    const submitButton = modal.getByRole("button", {
      name: /create|save|submit/i,
    });
    await submitButton.click();

    // Wait for modal to close
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // Verify property appears in table
    await expect(page.getByText("test-property-e2e-create")).toBeVisible();
  });

  test("should create a property definition via API", async ({ page }) => {
    // Create property using API
    const property = await createPropertyDefinition(page, {
      title: "API Created Property",
      description: "Property created via API",
      identifier: "api_created_property",
    });

    // Verify property was created successfully
    expect(property.id).toBeDefined();
    expect(property.title).toBe("API Created Property");
    expect(property.description).toBe("Property created via API");
    expect(property.identifier).toBe("api_created_property");

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
      identifier: "list_test_prop_1",
    });
    const prop2 = await createPropertyDefinition(page, {
      title: "List Test Property 2",
      identifier: "list_test_prop_2",
    });

    // Navigate to properties page
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");

    // Verify both properties appear in the list
    await expect(page.getByText("List Test Property 1")).toBeVisible();
    await expect(page.getByText("List Test Property 2")).toBeVisible();

    // Verify API response includes both
    const response = await apiRequest<any>(page, "/api/properties");
    const titles =
      response.items?.map((p: any) => p.title) ||
      response.map((p: any) => p.title) ||
      [];
    expect(titles).toContain(prop1.title);
    expect(titles).toContain(prop2.title);
  });

  test("should view property definition details", async ({ page }) => {
    // Create test property
    const property = await createPropertyDefinition(page, {
      title: "Detail Test Property",
      description: "Test description for property details",
      identifier: "detail_test_property",
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
    expect(apiResponse.identifier).toBe(property.identifier);
  });

  test("should update a property definition", async ({ page }) => {
    // Create test property
    const property = await createPropertyDefinition(page, {
      title: "Update Test Property",
      description: "Original description",
      identifier: "update_test_property",
    });

    // Navigate to properties page
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");

    // Find and double-click row to open edit form
    const propertyRow = page.getByText("Update Test Property");
    await propertyRow.dblclick();

    // Wait for edit form
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Update fields
    const titleInput = page
      .locator('[data-testid="property-definition-title-input"]')
      .first();
    const descriptionInput = page
      .locator('[data-testid="property-definition-description-input"]')
      .first();

    await titleInput.fill("test-property-e2e-update");
    await descriptionInput.fill("Updated property description");

    // Submit form
    const submitButton = modal.getByRole("button", { name: /save|update/i });
    await submitButton.click();

    // Wait for changes to apply
    await page.waitForLoadState("networkidle");

    // Verify updates in UI
    await expect(page.getByText("test-property-e2e-update")).toBeVisible();

    // Verify updates via API
    const apiResponse = await apiRequest<any>(
      page,
      `/api/properties/${property.id}`,
    );
    expect(apiResponse.title).toBe("test-property-e2e-update");
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

    // Find the row and select it via checkbox
    const propertyRow = page.getByText("Delete Test Property");
    const rowContainer = propertyRow.locator("..").locator("..");
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
    const testIdentifier = `field_test_${Date.now()}`;

    const property = await createPropertyDefinition(page, {
      title: testTitle,
      description: testDescription,
      identifier: testIdentifier,
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
    expect(apiResponse.identifier).toBe(testIdentifier);
    expect(apiResponse.id).toBeDefined();
    expect(apiResponse.created_at).toBeDefined();
  });

  test("should create multiple property definitions with different identifiers", async ({
    page,
  }) => {
    // Create properties with different identifiers
    const prop1 = await createPropertyDefinition(page, {
      title: "String Property",
      identifier: "string_property",
    });
    const prop2 = await createPropertyDefinition(page, {
      title: "Integer Property",
      identifier: "integer_property",
    });
    const prop3 = await createPropertyDefinition(page, {
      title: "Boolean Property",
      identifier: "boolean_property",
    });

    // Verify each property has correct identifier via API
    const response1 = await apiRequest<any>(
      page,
      `/api/properties/${prop1.id}`,
    );
    expect(response1.identifier).toBe("string_property");

    const response2 = await apiRequest<any>(
      page,
      `/api/properties/${prop2.id}`,
    );
    expect(response2.identifier).toBe("integer_property");

    const response3 = await apiRequest<any>(
      page,
      `/api/properties/${prop3.id}`,
    );
    expect(response3.identifier).toBe("boolean_property");
  });
});
