import { test, expect } from "@playwright/test";
import {
  createPropertyDefinition,
  clearTestData,
  apiRequest,
  APIError,
  waitForAppReady,
} from "../../fixtures/test-helpers";

/**
 * Property Definition CRUD E2E Tests
 *
 * Each test verifies a full round-trip: UI action → API read-back confirms persistence.
 *
 * typeName="Property Definition" → testIdPrefix="property-definition"
 * Table testids: "property-definition-add-button", "property-definition-row-${id}", etc.
 * Form testids: "property-definition-identifier-input", "property-definition-title-input", etc.
 *
 * Delete flow: select row checkbox → property-definition-actions-dropdown
 *   → property-definition-delete-selected-action → property-definition-delete-modal
 *   → property-definition-delete-confirm-button.
 * Edit flow: double-click property-definition-row-${id} → property-definition-edit-modal.
 */

test.describe("Property Definition CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a property definition via UI form", async ({ page }) => {
    await page.goto("/app/properties");
    await waitForAppReady(page);

    // typeName="Property Definition" → "property-definition-add-button" (normalized from typeName "Property Definition")
    await page.getByTestId("property-definition-add-button").click();

    const createModal = page.getByTestId("property-definition-create-modal").first();
    await expect(createModal).toBeVisible({ timeout: 5000 });

    await page.getByTestId("property-definition-identifier-input").fill("e2e_test_property");
    await page.getByTestId("property-definition-title-input").fill("E2E Test Property");
    await page.getByTestId("property-definition-description-input").fill("Created via E2E");
    await page.getByTestId("property-definition-submit-button").click();

    await expect(createModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(page.getByText("E2E Test Property")).toBeVisible();

    const list = await apiRequest<{ items: Array<{ title: string }> }>(
      page,
      "/api/properties"
    );
    expect(list.items.some((p) => p.title === "E2E Test Property")).toBe(true);
  });

  test("should display property definitions in the list", async ({ page }) => {
    const prop1 = await createPropertyDefinition(page, {
      title: "Property Alpha",
      identifier: "property_alpha",
    });
    const prop2 = await createPropertyDefinition(page, {
      title: "Property Beta",
      identifier: "property_beta",
    });

    await page.goto("/app/properties");
    await waitForAppReady(page);

    await expect(page.getByText("Property Alpha")).toBeVisible();
    await expect(page.getByText("Property Beta")).toBeVisible();

    await expect(
      page.getByTestId(`property-definition-row-${prop1.id}`)
    ).toBeVisible();
    await expect(
      page.getByTestId(`property-definition-row-${prop2.id}`)
    ).toBeVisible();
  });

  test("should update a property definition via double-click edit", async ({
    page,
  }) => {
    const prop = await createPropertyDefinition(page, {
      title: "Property Before Update",
      identifier: "before_update",
      description: "Original description",
    });

    await page.goto("/app/properties");
    await waitForAppReady(page);

    await page.getByTestId(`property-definition-row-${prop.id}`).dblclick();

    const editModal = page.getByTestId("property-definition-edit-modal").first();
    await expect(editModal).toBeVisible({ timeout: 5000 });

    await page.getByTestId("property-definition-title-input").fill("Property After Update");
    await page.getByTestId("property-definition-description-input").fill("Updated description");
    await page.getByTestId("property-definition-submit-button").click();

    await expect(editModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(
      page.getByTestId(`property-definition-row-${prop.id}`)
    ).toContainText("Property After Update");

    const updated = await apiRequest<{ title: string; description: string }>(
      page,
      `/api/properties/${prop.id}`
    );
    expect(updated.title).toBe("Property After Update");
    expect(updated.description).toBe("Updated description");
  });

  test("should delete a property definition via Actions dropdown", async ({
    page,
  }) => {
    const prop = await createPropertyDefinition(page, {
      title: "Property to Delete",
      identifier: "to_delete",
    });

    await page.goto("/app/properties");
    await waitForAppReady(page);

    await expect(page.getByText("Property to Delete")).toBeVisible();

    const row = page.getByTestId(`property-definition-row-${prop.id}`);
    await row.getByRole("checkbox").click();

    await page.getByTestId("property-definition-actions-dropdown").click();
    await page.getByTestId("property-definition-delete-selected-action").click();

    const deleteModal = page.getByTestId("property-definition-delete-modal").first();
    await expect(deleteModal).toBeVisible();
    await page.getByTestId("property-definition-delete-confirm-button").click();
    await expect(deleteModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(page.getByText("Property to Delete")).not.toBeVisible();

    try {
      await apiRequest(page, `/api/properties/${prop.id}`);
      throw new Error("Property was not deleted");
    } catch (err) {
      if (!(err instanceof APIError && err.statusCode === 404)) throw err;
    }
  });

  test("should persist identifier, title, and description fields", async ({
    page,
  }) => {
    const prop = await createPropertyDefinition(page, {
      title: "Persistence Test Property",
      identifier: "persistence_test",
      description: "Testing field persistence",
    });

    await page.goto("/app/properties");
    await waitForAppReady(page);

    const row = page.getByTestId(`property-definition-row-${prop.id}`);
    await expect(row).toBeVisible();
    await expect(row).toContainText("Persistence Test Property");

    const apiResponse = await apiRequest<{
      title: string;
      identifier: string;
      description: string;
    }>(page, `/api/properties/${prop.id}`);
    expect(apiResponse.title).toBe("Persistence Test Property");
    expect(apiResponse.identifier).toBe("persistence_test");
    expect(apiResponse.description).toBe("Testing field persistence");
  });
});
