import { test, expect } from "@playwright/test";
import {
  createTestHierarchy,
  createClass,
  clearTestData,
  apiRequest,
  APIError,
  waitForAppReady,
} from "../../fixtures/test-helpers";

/**
 * Ontology Class CRUD E2E Tests
 *
 * Each test verifies a full round-trip: UI action → API read-back confirms persistence.
 *
 * typeName="Class" in classes_table.tsx → testids are class-add-button,
 * class-row-${id}, class-create-modal, class-edit-modal, class-delete-modal, etc.
 *
 * Delete flow: select row checkbox → class-actions-dropdown → class-delete-selected-action
 *   → class-delete-modal → class-delete-confirm-button.
 * Edit flow: double-click class-row-${id} → class-edit-modal opens.
 */

test.describe("Ontology Class CRUD Operations", () => {
  let schemeId: string;

  test.beforeEach(async ({ page }) => {
    const hierarchy = await createTestHierarchy(page, 1);
    schemeId = hierarchy.scheme.id;
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a class via UI form", async ({ page }) => {
    await page.goto("/app/classes");
    await waitForAppReady(page);

    await page.getByTestId("class-add-button").click();

    const createModal = page.getByTestId("class-create-modal").first();
    await expect(createModal).toBeVisible({ timeout: 5000 });

    await page.getByTestId("class-title-input").fill("E2E Created Class");
    await page.getByTestId("class-description-input").fill("Created via E2E test");
    await page.getByTestId("class-submit-button").click();

    await expect(createModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(page.getByText("E2E Created Class")).toBeVisible();

    // Confirm persistence via API
    const list = await apiRequest<{ items: Array<{ title: string }> }>(
      page,
      "/api/classes"
    );
    expect(list.items.some((c) => c.title === "E2E Created Class")).toBe(true);
  });

  test("should display classes in the list", async ({ page }) => {
    const class1 = await createClass(page, schemeId, { title: "Alpha Class" });
    const class2 = await createClass(page, schemeId, { title: "Beta Class" });

    await page.goto("/app/classes");
    await waitForAppReady(page);

    await expect(page.getByText("Alpha Class")).toBeVisible();
    await expect(page.getByText("Beta Class")).toBeVisible();

    await expect(page.getByTestId(`class-row-${class1.id}`)).toBeVisible();
    await expect(page.getByTestId(`class-row-${class2.id}`)).toBeVisible();
  });

  test("should update a class via double-click edit", async ({ page }) => {
    const ontologyClass = await createClass(page, schemeId, {
      title: "Class Before Update",
      description: "Original definition",
    });

    await page.goto("/app/classes");
    await waitForAppReady(page);

    await page.getByTestId(`class-row-${ontologyClass.id}`).dblclick();

    const editModal = page.getByTestId("class-edit-modal").first();
    await expect(editModal).toBeVisible({ timeout: 5000 });

    await page.getByTestId("class-title-input").fill("Class After Update");
    await page.getByTestId("class-description-input").fill("Updated definition");
    await page.getByTestId("class-submit-button").click();

    await expect(editModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(
      page.getByTestId(`class-row-${ontologyClass.id}`)
    ).toContainText("Class After Update");

    const updated = await apiRequest<{ title: string; description: string }>(
      page,
      `/api/classes/${ontologyClass.id}`
    );
    expect(updated.title).toBe("Class After Update");
    expect(updated.description).toBe("Updated definition");
  });

  test("should delete a class via Actions dropdown", async ({ page }) => {
    const ontologyClass = await createClass(page, schemeId, {
      title: "Class to Delete",
    });

    await page.goto("/app/classes");
    await waitForAppReady(page);

    await expect(page.getByText("Class to Delete")).toBeVisible();

    const row = page.getByTestId(`class-row-${ontologyClass.id}`);
    await row.getByRole("checkbox").click();

    await page.getByTestId("class-actions-dropdown").click();
    await page.getByTestId("class-delete-selected-action").click();

    const deleteModal = page.getByTestId("class-delete-modal").first();
    await expect(deleteModal).toBeVisible();
    await page.getByTestId("class-delete-confirm-button").click();
    await expect(deleteModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(page.getByText("Class to Delete")).not.toBeVisible();

    try {
      await apiRequest(page, `/api/classes/${ontologyClass.id}`);
      throw new Error("Class was not deleted");
    } catch (err) {
      if (!(err instanceof APIError && err.statusCode === 404)) throw err;
    }
  });

  test("should verify class is linked to its concept scheme", async ({
    page,
  }) => {
    const ontologyClass = await createClass(page, schemeId, {
      title: "Scheme-Linked Class",
      description: "Linked to a specific scheme",
    });

    await page.goto("/app/classes");
    await waitForAppReady(page);

    await expect(page.getByTestId(`class-row-${ontologyClass.id}`)).toBeVisible();

    const apiResponse = await apiRequest<{
      concept_scheme_id: string;
      title: string;
    }>(page, `/api/classes/${ontologyClass.id}`);
    expect(apiResponse.concept_scheme_id).toBe(schemeId);
    expect(apiResponse.title).toBe("Scheme-Linked Class");
  });
});
