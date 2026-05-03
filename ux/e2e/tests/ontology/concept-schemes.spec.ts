import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  clearTestData,
  apiRequest,
  APIError,
  waitForAppReady,
} from "../../fixtures/test-helpers";

/**
 * Concept Scheme CRUD E2E Tests
 *
 * Each test verifies a full round-trip: UI action → API read-back confirms persistence.
 *
 * typeName="Concept Scheme" → testIdPrefix="concept-scheme"
 * Table testids: "concept-scheme-add-button", "concept-scheme-row-${id}", etc.
 * Form testids: "concept-scheme-title-input", "concept-scheme-description-input", etc.
 *
 * Delete flow: select row checkbox → concept-scheme-actions-dropdown
 *   → concept-scheme-delete-selected-action → concept-scheme-delete-modal
 *   → concept-scheme-delete-confirm-button.
 * Edit flow: double-click concept-scheme-row-${id} → concept-scheme-edit-modal opens.
 */

test.describe("Concept Scheme CRUD Operations", () => {
  let taxonomyId: string;

  test.beforeEach(async ({ page }) => {
    const taxonomy = await createTaxonomy(page, { title: "Parent Taxonomy" });
    taxonomyId = taxonomy.id;
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a concept scheme via UI form", async ({ page }) => {
    await page.goto("/app/concept-schemes");
    await waitForAppReady(page);

    // typeName="Concept Scheme" → "concept-scheme-add-button" (normalized from typeName "Concept Scheme")
    await page.getByTestId("concept-scheme-add-button").click();

    const createModal = page.getByTestId("concept-scheme-create-modal").first();
    await expect(createModal).toBeVisible({ timeout: 5000 });

    await page.getByTestId("concept-scheme-title-input").fill("E2E Created Scheme");
    await page.getByTestId("concept-scheme-description-input").fill("Created via E2E");

    // Select the parent taxonomy (required to submit)
    await page.getByTestId("concept-scheme-taxonomy-selector").getByRole("button").click();
    await page.locator(`#option-${taxonomyId}`).click();

    await page.getByTestId("concept-scheme-submit-button").click();

    await expect(createModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(page.getByText("E2E Created Scheme")).toBeVisible();

    const list = await apiRequest<{ items: Array<{ title: string }> }>(
      page,
      "/api/schemes"
    );
    expect(list.items.some((s) => s.title === "E2E Created Scheme")).toBe(true);
  });

  test("should display concept schemes in the list", async ({ page }) => {
    const scheme1 = await createConceptScheme(page, taxonomyId, {
      title: "Scheme Alpha",
    });
    const scheme2 = await createConceptScheme(page, taxonomyId, {
      title: "Scheme Beta",
    });

    await page.goto("/app/concept-schemes");
    await waitForAppReady(page);

    await expect(page.getByText("Scheme Alpha")).toBeVisible();
    await expect(page.getByText("Scheme Beta")).toBeVisible();

    await expect(
      page.getByTestId(`concept-scheme-row-${scheme1.id}`)
    ).toBeVisible();
    await expect(
      page.getByTestId(`concept-scheme-row-${scheme2.id}`)
    ).toBeVisible();
  });

  test("should update a concept scheme via double-click edit", async ({
    page,
  }) => {
    const scheme = await createConceptScheme(page, taxonomyId, {
      title: "Scheme Before Update",
      description: "Original description",
    });

    await page.goto("/app/concept-schemes");
    await waitForAppReady(page);

    await page.getByTestId(`concept-scheme-row-${scheme.id}`).dblclick();

    const editModal = page.getByTestId("concept-scheme-edit-modal").first();
    await expect(editModal).toBeVisible({ timeout: 5000 });

    await page.getByTestId("concept-scheme-title-input").fill("Scheme After Update");
    await page.getByTestId("concept-scheme-description-input").fill("Updated description");
    await page.getByTestId("concept-scheme-submit-button").click();

    await expect(editModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(
      page.getByTestId(`concept-scheme-row-${scheme.id}`)
    ).toContainText("Scheme After Update");

    const updated = await apiRequest<{ title: string; description: string }>(
      page,
      `/api/schemes/${scheme.id}`
    );
    expect(updated.title).toBe("Scheme After Update");
    expect(updated.description).toBe("Updated description");
  });

  test("should delete a concept scheme via Actions dropdown", async ({
    page,
  }) => {
    const scheme = await createConceptScheme(page, taxonomyId, {
      title: "Scheme to Delete",
    });

    await page.goto("/app/concept-schemes");
    await waitForAppReady(page);

    await expect(page.getByText("Scheme to Delete")).toBeVisible();

    const row = page.getByTestId(`concept-scheme-row-${scheme.id}`);
    await row.getByRole("checkbox").click();

    await page.getByTestId("concept-scheme-actions-dropdown").click();
    await page.getByTestId("concept-scheme-delete-selected-action").click();

    const deleteModal = page.getByTestId("concept-scheme-delete-modal").first();
    await expect(deleteModal).toBeVisible();
    await page.getByTestId("concept-scheme-delete-confirm-button").click();
    await expect(deleteModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(page.getByText("Scheme to Delete")).not.toBeVisible();

    try {
      await apiRequest(page, `/api/schemes/${scheme.id}`);
      throw new Error("Scheme was not deleted");
    } catch (err) {
      if (!(err instanceof APIError && err.statusCode === 404)) throw err;
    }
  });

  test("should verify concept scheme is linked to its taxonomy", async ({
    page,
  }) => {
    const scheme = await createConceptScheme(page, taxonomyId, {
      title: "Taxonomy-Linked Scheme",
    });

    await page.goto("/app/concept-schemes");
    await waitForAppReady(page);

    await expect(
      page.getByTestId(`concept-scheme-row-${scheme.id}`)
    ).toBeVisible();

    const apiResponse = await apiRequest<{ taxonomy_id: string }>(
      page,
      `/api/schemes/${scheme.id}`
    );
    expect(apiResponse.taxonomy_id).toBe(taxonomyId);
  });
});
