import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  clearTestData,
  apiRequest,
  waitForAppReady,
  APIError,
} from "../../fixtures/test-helpers";

/**
 * Taxonomy CRUD E2E Tests
 *
 * Each test verifies a full round-trip: UI action → API read-back confirms persistence.
 *
 * Delete flow: select row checkbox → Actions dropdown → Delete Selected → confirm modal.
 * Edit flow: double-click row → edit modal opens (taxonomy-edit-modal testid).
 */

test.describe("Taxonomy CRUD Operations", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a taxonomy via UI form", async ({ page }) => {
    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    await page.getByTestId("taxonomy-add-button").click();

    const form = page.getByTestId("taxonomy-form");
    await expect(form).toBeVisible();

    await page.getByTestId("taxonomy-title-input").fill("Test Taxonomy");
    await page
      .getByTestId("taxonomy-description-input")
      .fill("A test taxonomy for validation");
    await page.getByTestId("taxonomy-submit-button").click();

    await expect(form).not.toBeVisible();
    await waitForAppReady(page);

    await expect(page.getByTestId("taxonomy-table").getByText("Test Taxonomy", { exact: true })).toBeVisible();

    // Verify persistence via API
    const list = await apiRequest<{ items: Array<{ title: string }> }>(
      page,
      "/api/taxonomies"
    );
    expect(list.items.some((t) => t.title === "Test Taxonomy")).toBe(true);
  });

  test("should display created taxonomies in the list", async ({ page }) => {
    const taxonomy1 = await createTaxonomy(page, { title: "List Taxonomy Alpha" });
    const taxonomy2 = await createTaxonomy(page, { title: "List Taxonomy Beta" });

    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    await expect(page.getByText("List Taxonomy Alpha")).toBeVisible();
    await expect(page.getByText("List Taxonomy Beta")).toBeVisible();

    // Confirm both rows are present by testid
    await expect(page.getByTestId(`taxonomy-row-${taxonomy1.id}`)).toBeVisible();
    await expect(page.getByTestId(`taxonomy-row-${taxonomy2.id}`)).toBeVisible();
  });

  test("should navigate to taxonomy detail page on row click", async ({
    page,
  }) => {
    const taxonomy = await createTaxonomy(page, {
      title: "Detail Test Taxonomy",
      description: "Test description for details",
    });

    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    await page.getByTestId(`taxonomy-row-${taxonomy.id}`).click();
    await waitForAppReady(page);

    await expect(page.getByText("Detail Test Taxonomy")).toBeVisible();
    await expect(page.getByText("Test description for details")).toBeVisible();
  });

  test("should update a taxonomy via double-click edit", async ({ page }) => {
    const taxonomy = await createTaxonomy(page, {
      title: "Original Title",
      description: "Original description",
    });

    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    // Double-click the row to open the edit modal
    await page.getByTestId(`taxonomy-row-${taxonomy.id}`).dblclick();

    const editModal = page.getByTestId("taxonomy-edit-modal").first();
    await expect(editModal).toBeVisible({ timeout: 5000 });

    await page.getByTestId("taxonomy-title-input").fill("Updated Title");
    await page.getByTestId("taxonomy-description-input").fill("Updated description");
    await page.getByTestId("taxonomy-submit-button").click();

    await expect(editModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    // Row should reflect the new title
    await expect(
      page.getByTestId(`taxonomy-row-${taxonomy.id}`)
    ).toContainText("Updated Title");

    // Confirm persistence via API
    const updated = await apiRequest<{ title: string; description: string }>(
      page,
      `/api/taxonomies/${taxonomy.id}`
    );
    expect(updated.title).toBe("Updated Title");
    expect(updated.description).toBe("Updated description");
  });

  test("should delete a taxonomy via Actions dropdown", async ({ page }) => {
    const taxonomy = await createTaxonomy(page, { title: "Taxonomy to Delete" });

    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    await expect(page.getByText("Taxonomy to Delete")).toBeVisible();

    // Select the row via its checkbox
    const row = page.getByTestId(`taxonomy-row-${taxonomy.id}`);
    await row.getByRole("checkbox").click();

    // Open the Actions dropdown and choose Delete Selected
    await page.getByTestId("taxonomy-actions-dropdown").click();
    await page.getByTestId("taxonomy-delete-selected-action").click();

    // Confirm in the modal
    const deleteModal = page.getByTestId("taxonomy-delete-modal").first();
    await expect(deleteModal).toBeVisible();
    await page.getByTestId("taxonomy-delete-confirm-button").click();
    await expect(deleteModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(page.getByText("Taxonomy to Delete")).not.toBeVisible();

    // Confirm deletion via API
    try {
      await apiRequest(page, `/api/taxonomies/${taxonomy.id}`);
      throw new Error("Taxonomy was not deleted");
    } catch (err) {
      if (!(err instanceof APIError && err.statusCode === 404)) throw err;
    }
  });

  test("should validate that title is required", async ({ page }) => {
    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    await page.getByTestId("taxonomy-add-button").click();

    const form = page.getByTestId("taxonomy-form");
    await expect(form).toBeVisible();

    // Submit without filling title
    await page.getByTestId("taxonomy-submit-button").click();

    // Form must remain open — required field validation prevents submission
    await expect(form).toBeVisible();
  });

  test("should preserve special characters in taxonomy title", async ({
    page,
  }) => {
    const specialTitle = "Test™ Taxón°mý";

    await page.goto("/app/taxonomies");
    await waitForAppReady(page);

    await page.getByTestId("taxonomy-add-button").click();

    const form = page.getByTestId("taxonomy-form");
    await expect(form).toBeVisible();

    await page.getByTestId("taxonomy-title-input").fill(specialTitle);
    await page.getByTestId("taxonomy-description-input").fill("Special chars test");
    await page.getByTestId("taxonomy-submit-button").click();

    await expect(form).not.toBeVisible();
    await waitForAppReady(page);

    await expect(page.getByTestId("taxonomy-table")).toContainText(specialTitle);
  });
});
