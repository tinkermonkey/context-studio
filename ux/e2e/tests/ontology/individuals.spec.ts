import { test, expect } from "@playwright/test";
import {
  createTestHierarchy,
  clearTestData,
  apiRequest,
  APIError,
  waitForAppReady,
} from "../../fixtures/test-helpers";

/**
 * Ontology Individual CRUD and Class Membership E2E Tests
 *
 * Each test verifies a full round-trip: UI action → API read-back confirms persistence.
 *
 * typeName="Individual" → testids: individual-add-button, individual-row-${id},
 *   individual-create-modal, individual-edit-modal, individual-delete-modal, etc.
 *
 * Class selector note: #add-class-select has an onChange handler that adds the class
 * immediately on selection — no button click needed after selectOption().
 *
 * Delete flow: select individual-row-${id} checkbox → individual-actions-dropdown
 *   → individual-delete-selected-action → individual-delete-modal
 *   → individual-delete-confirm-button.
 * Edit flow: double-click individual-row-${id} → individual-edit-modal opens.
 */

test.describe("Ontology Individual CRUD and Class Membership Operations", () => {
  let classIds: string[] = [];

  test.beforeEach(async ({ page }) => {
    const hierarchy = await createTestHierarchy(page, 3, {
      classTitle: "individual-test-class",
    });
    classIds = hierarchy.classes.map((cls) => cls.id);
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create an individual via UI form with a parent class", async ({
    page,
  }) => {
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    await page.getByTestId("individual-add-button").click();

    const createModal = page.getByTestId("individual-create-modal");
    await expect(createModal).toBeVisible({ timeout: 5000 });

    await page.getByTestId("individual-title-input").fill("UI Created Individual");
    await page.getByTestId("individual-description-input").fill("Created via UI form");

    // Selecting the class via onChange fires immediately — no button click required.
    await page.locator("#add-class-select").selectOption(classIds[0]);

    await page.getByTestId("individual-form-submit").click();

    await expect(createModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(page.getByText("UI Created Individual")).toBeVisible();

    // Confirm persistence via API
    const list = await apiRequest<{ items: Array<{ id: string; title: string; class_ids: string[] }> }>(
      page,
      "/api/individuals"
    );
    const created = list.items.find((i) => i.title === "UI Created Individual");
    expect(created).toBeDefined();
    expect(created!.class_ids).toContain(classIds[0]);
  });

  test("should display individuals in the list", async ({ page }) => {
    const ind1 = await apiRequest<{ id: string }>(page, "/api/individuals", {
      method: "POST",
      body: { title: "List Individual Alpha", class_ids: [classIds[0]] },
    });
    const ind2 = await apiRequest<{ id: string }>(page, "/api/individuals", {
      method: "POST",
      body: { title: "List Individual Beta", class_ids: [classIds[1]] },
    });

    await page.goto("/app/individuals");
    await waitForAppReady(page);

    await expect(page.getByText("List Individual Alpha")).toBeVisible();
    await expect(page.getByText("List Individual Beta")).toBeVisible();

    await expect(page.getByTestId(`individual-row-${ind1.id}`)).toBeVisible();
    await expect(page.getByTestId(`individual-row-${ind2.id}`)).toBeVisible();
  });

  test("should update an individual via double-click edit", async ({ page }) => {
    const individual = await apiRequest<{ id: string }>(
      page,
      "/api/individuals",
      {
        method: "POST",
        body: {
          title: "Individual Before Update",
          description: "Original description",
          class_ids: [classIds[0]],
        },
      }
    );

    await page.goto("/app/individuals");
    await waitForAppReady(page);

    await page.getByTestId(`individual-row-${individual.id}`).dblclick();

    const editModal = page.getByTestId("individual-edit-modal");
    await expect(editModal).toBeVisible({ timeout: 5000 });

    await page.getByTestId("individual-title-input").fill("Individual After Update");
    await page.getByTestId("individual-description-input").fill("Updated description");
    await page.getByTestId("individual-form-submit").click();

    await expect(editModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(
      page.getByTestId(`individual-row-${individual.id}`)
    ).toContainText("Individual After Update");

    const updated = await apiRequest<{ title: string; description: string }>(
      page,
      `/api/individuals/${individual.id}`
    );
    expect(updated.title).toBe("Individual After Update");
    expect(updated.description).toBe("Updated description");
  });

  test("should delete an individual via Actions dropdown", async ({ page }) => {
    const individual = await apiRequest<{ id: string }>(
      page,
      "/api/individuals",
      {
        method: "POST",
        body: {
          title: "Individual to Delete",
          class_ids: [classIds[0]],
        },
      }
    );

    await page.goto("/app/individuals");
    await waitForAppReady(page);

    await expect(page.getByText("Individual to Delete")).toBeVisible();

    const row = page.getByTestId(`individual-row-${individual.id}`);
    await row.getByRole("checkbox").click();

    await page.getByTestId("individual-actions-dropdown").click();
    await page.getByTestId("individual-delete-selected-action").click();

    const deleteModal = page.getByTestId("individual-delete-modal");
    await expect(deleteModal).toBeVisible();
    await page.getByTestId("individual-delete-confirm-button").click();
    await expect(deleteModal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    await expect(page.getByText("Individual to Delete")).not.toBeVisible();

    try {
      await apiRequest(page, `/api/individuals/${individual.id}`);
      throw new Error("Individual was not deleted");
    } catch (err) {
      if (!(err instanceof APIError && err.statusCode === 404)) throw err;
    }
  });

  test("should add a parent class via edit form", async ({ page }) => {
    const individual = await apiRequest<{ id: string; class_ids: string[] }>(
      page,
      "/api/individuals",
      {
        method: "POST",
        body: {
          title: "Individual for Class Addition",
          class_ids: [classIds[0]],
        },
      }
    );

    await page.goto("/app/individuals");
    await waitForAppReady(page);

    await page.getByTestId(`individual-row-${individual.id}`).dblclick();

    const editModal = page.getByTestId("individual-edit-modal");
    await expect(editModal).toBeVisible({ timeout: 5000 });

    // Add a second class — onChange fires immediately on selection
    await page.locator("#add-class-select").selectOption(classIds[1]);

    await page.getByTestId("individual-form-submit").click();
    await expect(editModal).not.toBeVisible({ timeout: 5000 });

    const updated = await apiRequest<{ class_ids: string[] }>(
      page,
      `/api/individuals/${individual.id}`
    );
    expect(updated.class_ids).toContain(classIds[0]);
    expect(updated.class_ids).toContain(classIds[1]);
  });

  test("should remove a parent class via edit form", async ({ page }) => {
    const individual = await apiRequest<{ id: string }>(
      page,
      "/api/individuals",
      {
        method: "POST",
        body: {
          title: "Individual for Class Removal",
          class_ids: [classIds[0], classIds[1]],
        },
      }
    );

    await page.goto("/app/individuals");
    await waitForAppReady(page);

    await page.getByTestId(`individual-row-${individual.id}`).dblclick();

    const editModal = page.getByTestId("individual-edit-modal");
    await expect(editModal).toBeVisible({ timeout: 5000 });

    // Remove the second class
    await page
      .getByTestId(`individual-classes-remove-button-${classIds[1]}`)
      .click();

    await page.getByTestId("individual-form-submit").click();
    await expect(editModal).not.toBeVisible({ timeout: 5000 });

    const updated = await apiRequest<{ class_ids: string[] }>(
      page,
      `/api/individuals/${individual.id}`
    );
    expect(updated.class_ids).toEqual([classIds[0]]);
  });

  test("should show validation error when no parent class is selected", async ({
    page,
  }) => {
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    await page.getByTestId("individual-add-button").click();

    const createModal = page.getByTestId("individual-create-modal");
    await expect(createModal).toBeVisible({ timeout: 5000 });

    await page.getByTestId("individual-title-input").fill("No Class Individual");
    // Intentionally skip class selection

    await page.getByTestId("individual-form-submit").click();

    // Form must remain open — submitting without a class is invalid
    await expect(createModal).toBeVisible();
  });

  test("should fetch inherited-properties with ListResponse envelope", async ({
    page,
  }) => {
    const individual = await apiRequest<{ id: string }>(
      page,
      "/api/individuals",
      {
        method: "POST",
        body: {
          title: "Inherited Props Individual",
          class_ids: [classIds[0]],
        },
      }
    );

    await page.goto("/app/individuals");
    await waitForAppReady(page);

    await expect(page.getByTestId(`individual-row-${individual.id}`)).toBeVisible();

    const response = await apiRequest<{
      items: unknown[];
      total: number;
      limit: number;
      offset: number;
    }>(page, `/api/individuals/${individual.id}/inherited-properties`);

    expect(Array.isArray(response.items)).toBe(true);
    expect(typeof response.total).toBe("number");
    expect(typeof response.limit).toBe("number");
    expect(typeof response.offset).toBe("number");
  });
});
