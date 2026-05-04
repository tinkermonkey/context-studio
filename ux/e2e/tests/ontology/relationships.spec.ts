import { test, expect } from "@playwright/test";
import {
  createTestHierarchy,
  createRelationship,
  clearTestData,
  apiRequest,
  APIError,
  waitForAppReady,
} from "../../fixtures/test-helpers";

/**
 * Relationship List and Delete E2E Tests
 *
 * Relationships have no create/edit UI yet ("coming soon"), so these tests
 * cover the list view and the delete flow.
 *
 * typeName="Relationship" → testIdPrefix="relationship"
 * Table testids: "relationship-row-${id}", "relationship-actions-dropdown",
 *   "relationship-delete-selected-action", "relationship-delete-modal",
 *   "relationship-delete-confirm-button".
 *
 * Delete flow: select row checkbox → relationship-actions-dropdown
 *   → relationship-delete-selected-action → relationship-delete-modal
 *   → relationship-delete-confirm-button.
 */

test.describe("Relationship List and Delete", () => {
  let classIds: string[];

  test.beforeEach(async ({ page }) => {
    const hierarchy = await createTestHierarchy(page, 3);
    classIds = hierarchy.classes.map((c) => c.id);
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should display relationships created via API", async ({ page }) => {
    const rel1 = await createRelationship(
      page,
      classIds[0],
      classIds[1],
      "related_to",
    );
    const rel2 = await createRelationship(
      page,
      classIds[1],
      classIds[2],
      "parent_of",
    );

    await page.goto("/app/relationships");
    await waitForAppReady(page);

    await expect(page.getByTestId(`relationship-row-${rel1.id}`)).toBeVisible();
    await expect(page.getByTestId(`relationship-row-${rel2.id}`)).toBeVisible();
  });

  test("should delete a relationship via Actions dropdown", async ({
    page,
  }) => {
    const rel = await createRelationship(
      page,
      classIds[0],
      classIds[1],
      "related_to",
    );

    await page.goto("/app/relationships");
    await waitForAppReady(page);

    const row = page.getByTestId(`relationship-row-${rel.id}`);
    await expect(row).toBeVisible();
    await row.getByRole("checkbox").click();

    await page.getByTestId("relationship-actions-dropdown").click();
    await page.getByTestId("relationship-delete-selected-action").click();

    const deleteModal = page.getByTestId("relationship-delete-modal").first();
    await expect(deleteModal).toBeVisible();
    await page.getByTestId("relationship-delete-confirm-button").click();
    await expect(deleteModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(
      page.getByTestId(`relationship-row-${rel.id}`),
    ).not.toBeVisible();

    try {
      await apiRequest(page, `/api/relationships/${rel.id}`);
      throw new Error("Relationship was not deleted");
    } catch (err) {
      if (!(err instanceof APIError && err.statusCode === 404)) throw err;
    }
  });

  test("should cancel relationship deletion", async ({ page }) => {
    const rel = await createRelationship(
      page,
      classIds[0],
      classIds[1],
      "related_to",
    );

    await page.goto("/app/relationships");
    await waitForAppReady(page);

    const row = page.getByTestId(`relationship-row-${rel.id}`);
    await row.getByRole("checkbox").click();

    await page.getByTestId("relationship-actions-dropdown").click();
    await page.getByTestId("relationship-delete-selected-action").click();

    const deleteModal = page.getByTestId("relationship-delete-modal").first();
    await expect(deleteModal).toBeVisible();
    await page.getByTestId("relationship-delete-cancel-button").click();
    await expect(deleteModal).not.toBeVisible({ timeout: 5000 });

    // Relationship must still exist
    await expect(page.getByTestId(`relationship-row-${rel.id}`)).toBeVisible();
    const existing = await apiRequest<{ id: string }>(
      page,
      `/api/relationships/${rel.id}`,
    );
    expect(existing.id).toBe(rel.id);
  });
});
