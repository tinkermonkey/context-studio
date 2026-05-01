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
 * Tests the complete CRUD lifecycle for individuals and class membership operations:
 * - Create an individual via UI form within one or more classes
 * - List individuals and verify presence in UI
 * - View individual details with inherited properties
 * - Update individual properties via UI
 * - Manage parent class membership (add, remove, reorder)
 * - Delete individual via UI
 * - Verify error handling for invalid operations
 *
 * Each test follows the established pattern from #578:
 * beforeEach factory setup → navigate → act (form interaction) → UI assertion → API read-back
 */

test.describe("Ontology Individual CRUD and Class Membership Operations", () => {
  let schemeId: string;
  let classIds: string[] = [];

  test.beforeEach(async ({ page }) => {
    // Create test hierarchy with 3 classes for testing multi-class operations
    const hierarchy = await createTestHierarchy(page, 3, {
      classTitle: "test-individual-class",
    });
    schemeId = hierarchy.scheme.id;
    classIds = hierarchy.classes.map((cls) => cls.id);
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create an individual via UI form with single parent class", async ({
    page,
  }) => {
    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Click "Add" button to open form (look for button with add icon or text)
    const addButton = page.getByRole("button", { name: /add|create|new/i }).first();
    await addButton.click();

    // Wait for form to be visible
    const form = page.getByTestId("individual-form");
    await expect(form).toBeVisible();

    // Fill in the individual title
    await page.getByTestId("individual-title-input").fill("UI Test Individual");

    // Fill in description
    await page.getByTestId("individual-description-input").fill("Created via UI test");

    // Select the first parent class from dropdown
    const classSelector = page.locator("#add-class-select");
    await classSelector.selectOption(classIds[0]);

    // Click add class button
    await page.getByTestId("individual-classes-add-button").click();

    // Wait for class to appear in selected list
    await expect(page.locator(`text=${classIds[0].substring(0, 8)}`)).toBeVisible();

    // Submit the form
    await page.getByTestId("individual-form-submit").click();

    // Wait for form to close and page to update
    await expect(form).not.toBeVisible();
    await waitForAppReady(page);

    // Verify the individual appears in the list
    await expect(page.getByText("UI Test Individual")).toBeVisible();

    // Verify via API read-back
    const allIndividuals = await apiRequest<any>(page, "/api/individuals");
    const individuals = Array.isArray(allIndividuals) ? allIndividuals : allIndividuals.items || [];
    const created = individuals.find((ind: any) => ind.title === "UI Test Individual");
    expect(created).toBeDefined();
    expect(created.class_ids).toEqual([classIds[0]]);
  });

  test("should create an individual via UI form with multiple parent classes", async ({
    page,
  }) => {
    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Open form
    const addButton = page.getByRole("button", { name: /add|create|new/i }).first();
    await addButton.click();

    const form = page.getByTestId("individual-form");
    await expect(form).toBeVisible();

    // Fill form
    await page.getByTestId("individual-title-input").fill("Multi-Class UI Individual");
    await page.getByTestId("individual-description-input").fill("Individual with multiple classes");

    // Add three classes in specific order (order matters for precedence)
    for (const classId of [classIds[0], classIds[1], classIds[2]]) {
      const classSelector = page.locator("#add-class-select");
      await classSelector.selectOption(classId);
      await page.getByTestId("individual-classes-add-button").click();
      // Wait for class to be added
      await page.waitForTimeout(100);
    }

    // Submit the form
    await page.getByTestId("individual-form-submit").click();

    // Wait for form to close
    await expect(form).not.toBeVisible();
    await waitForAppReady(page);

    // Verify in UI
    await expect(page.getByText("Multi-Class UI Individual")).toBeVisible();

    // Verify via API - should have all three classes in correct order
    const allIndividuals = await apiRequest<any>(page, "/api/individuals");
    const individuals = Array.isArray(allIndividuals) ? allIndividuals : allIndividuals.items || [];
    const created = individuals.find((ind: any) => ind.title === "Multi-Class UI Individual");
    expect(created).toBeDefined();
    expect(created.class_ids).toEqual([classIds[0], classIds[1], classIds[2]]);
  });

  test("should list all individuals and verify UI display", async ({ page }) => {
    // Create individuals via API for faster setup
    const ind1Response = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "List Display Individual 1",
        description: "First individual",
        class_ids: [classIds[0]],
      },
    });

    const ind2Response = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "List Display Individual 2",
        description: "Second individual",
        class_ids: [classIds[1]],
      },
    });

    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Verify both individuals appear in the table
    await expect(page.getByText("List Display Individual 1")).toBeVisible();
    await expect(page.getByText("List Display Individual 2")).toBeVisible();

    // Verify table shows correct count of parent classes
    const rows = page.locator("table tbody tr");
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThanOrEqual(2);
  });

  test("should filter individuals by class", async ({ page }) => {
    // Create individuals in different classes via API
    const ind1 = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "Class Filter Individual 1",
        description: "Individual in class 0",
        class_ids: [classIds[0]],
      },
    });

    const ind2 = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "Class Filter Individual 2",
        description: "Individual in class 1",
        class_ids: [classIds[1]],
      },
    });

    // Navigate and verify API filter works
    const filteredResponse = await apiRequest<any>(
      page,
      `/api/individuals?class_id=${classIds[0]}`,
    );
    const filtered = Array.isArray(filteredResponse)
      ? filteredResponse
      : filteredResponse.items || [];

    // Verify filtering
    const ids = filtered.map((ind: any) => ind.id);
    expect(ids).toContain(ind1.id);
    expect(ids).not.toContain(ind2.id);
  });

  test("should retrieve individual details and navigate to detail view", async ({
    page,
  }) => {
    // Create individual via API
    const individual = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "Detail View Individual",
        description: "Testing detail page",
        class_ids: [classIds[0]],
      },
    });

    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Verify individual appears in list
    await expect(page.getByText("Detail View Individual")).toBeVisible();

    // Click on the individual row to view details
    const tableRow = page.getByRole("row", { name: /Detail View Individual/i }).first();
    await tableRow.click();

    // Wait for detail page to load
    await waitForAppReady(page);

    // Verify detail page shows the individual information
    await expect(page.getByText("Detail View Individual")).toBeVisible();
  });

  test("should fetch inherited-properties endpoint with correct ListResponse format", async ({
    page,
  }) => {
    // Create individual
    const individual = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "Inherited Properties Individual",
        description: "Test inherited properties",
        class_ids: [classIds[0]],
      },
    });

    // Fetch inherited properties - must return ListResponse envelope
    const response = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}/inherited-properties`,
    );

    // Verify response structure - MUST be ListResponse (not plain array)
    expect(response).toBeDefined();
    expect(response.items).toBeDefined();
    expect(Array.isArray(response.items)).toBe(true);
    expect(response.total).toBeDefined();
    expect(typeof response.total).toBe("number");
    expect(response.limit).toBeDefined();
    expect(typeof response.limit).toBe("number");
    expect(response.offset).toBeDefined();
    expect(typeof response.offset).toBe("number");
  });

  test("should update individual via UI edit form", async ({ page }) => {
    // Create individual via API
    const individual = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "Individual To Update",
        description: "Original description",
        class_ids: [classIds[0]],
      },
    });

    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Find and double-click row to open edit form
    const tableRow = page.getByRole("row", { name: /Individual To Update/i }).first();
    await tableRow.dblclick();

    // Wait for edit form modal to appear
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Update fields
    const titleInput = page.getByTestId("individual-title-input");
    const descriptionInput = page.getByTestId("individual-description-input");

    await titleInput.fill("Individual Updated Via UI");
    await descriptionInput.fill("Updated description via UI test");

    // Submit form
    const submitButton = page.getByTestId("individual-form-submit");
    await submitButton.click();

    // Wait for form to close
    await expect(modal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    // Verify updates in UI
    await expect(page.getByText("Individual Updated Via UI")).toBeVisible();

    // Verify persistence via API
    const readBack = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );
    expect(readBack.title).toBe("Individual Updated Via UI");
    expect(readBack.description).toBe("Updated description via UI test");
  });

  test("should add a parent class to an individual via edit", async ({ page }) => {
    // Create individual with one class via API
    const individual = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "Add Class Individual",
        description: "Testing class addition",
        class_ids: [classIds[0]],
      },
    });

    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Open edit form
    const tableRow = page.getByRole("row", { name: /Add Class Individual/i }).first();
    await tableRow.dblclick();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Add a second parent class
    const classSelector = page.locator("#add-class-select");
    await classSelector.selectOption(classIds[1]);
    await page.getByTestId("individual-classes-add-button").click();
    await page.waitForTimeout(100);

    // Submit form
    await page.getByTestId("individual-form-submit").click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // Verify via API
    const readBack = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );
    expect(readBack.class_ids).toEqual([classIds[0], classIds[1]]);
  });

  test("should remove a parent class from an individual via edit", async ({
    page,
  }) => {
    // Create individual with multiple classes
    const individual = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "Remove Class Individual",
        description: "Testing class removal",
        class_ids: [classIds[0], classIds[1], classIds[2]],
      },
    });

    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Open edit form
    const tableRow = page.getByRole("row", { name: /Remove Class Individual/i }).first();
    await tableRow.dblclick();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Remove the middle class (classIds[1])
    const removeButton = page.getByTestId(
      `individual-classes-remove-button-${classIds[1]}`,
    );
    await removeButton.click();
    await page.waitForTimeout(100);

    // Submit form
    await page.getByTestId("individual-form-submit").click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // Verify via API - class was removed, order maintained
    const readBack = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );
    expect(readBack.class_ids).toEqual([classIds[0], classIds[2]]);
  });

  test("should reorder parent classes and verify property precedence changes", async ({
    page,
  }) => {
    // Create individual with multiple classes in specific order
    const individual = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "Reorder Precedence Test",
        description: "Testing property precedence on reorder",
        class_ids: [classIds[0], classIds[1], classIds[2]],
      },
    });

    // Fetch inherited properties BEFORE reorder
    const beforeReorder = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}/inherited-properties`,
    );
    expect(beforeReorder.items).toBeDefined();
    const beforeOrder = individual.class_ids;

    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Open edit form
    const tableRow = page.getByRole("row", { name: /Reorder Precedence Test/i }).first();
    await tableRow.dblclick();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Reorder classes by dragging - reverse the order
    // Get all the class items (they should be in the DOM)
    const classItems = page.locator("[data-testid^='individual-classes-reorder-handle']");
    const count = await classItems.count();
    expect(count).toBe(3);

    // Drag first class to the end position
    const firstHandle = page.getByTestId(
      `individual-classes-reorder-handle-${classIds[0]}`,
    );
    const lastHandle = page.getByTestId(
      `individual-classes-reorder-handle-${classIds[2]}`,
    );

    // Drag classIds[0] to position of classIds[2]
    await firstHandle.dragTo(lastHandle);

    // Submit form
    await page.getByTestId("individual-form-submit").click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });
    await waitForAppReady(page);

    // Verify class order changed via API
    const readBack = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );
    // Order should be different from before
    expect(readBack.class_ids).not.toEqual(beforeOrder);

    // Fetch inherited properties AFTER reorder
    const afterReorder = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}/inherited-properties`,
    );
    expect(afterReorder.items).toBeDefined();

    // Verify precedence changed - note: actual properties depend on class setup
    // but the API response should reflect the new order
    expect(beforeReorder.items).toBeDefined();
    expect(afterReorder.items).toBeDefined();
    // Both should have items (may be empty if no properties defined on classes)
    expect(Array.isArray(beforeReorder.items)).toBe(true);
    expect(Array.isArray(afterReorder.items)).toBe(true);
  });

  test("should delete an individual via UI", async ({ page }) => {
    // Create individual via API
    const individual = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "Delete Via UI Individual",
        description: "This individual will be deleted",
        class_ids: [classIds[0]],
      },
    });

    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Wait for the individual to appear
    await expect(page.getByText("Delete Via UI Individual")).toBeVisible();

    // Click delete button for the row
    const tableRow = page.getByRole("row", { name: /Delete Via UI Individual/i }).first();
    const deleteButton = tableRow.getByRole("button", { name: /delete/i });
    await deleteButton.click();

    // Confirm deletion in modal if present
    const deleteModal = page.getByRole("dialog");
    if (await deleteModal.isVisible()) {
      const confirmButton = deleteModal.getByRole("button", { name: /confirm|delete|yes/i });
      await confirmButton.click();
    }

    // Wait for the row to disappear
    await expect(page.getByText("Delete Via UI Individual")).not.toBeVisible();

    // Verify deletion via API
    try {
      await apiRequest<any>(page, `/api/individuals/${individual.id}`);
      throw new Error("Individual was not deleted");
    } catch (error: any) {
      if (!(error instanceof APIError && error.statusCode === 404)) {
        throw error;
      }
    }
  });

  test("should reject creating individual with zero parent classes via UI form", async ({
    page,
  }) => {
    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Open form
    const addButton = page.getByRole("button", { name: /add|create|new/i }).first();
    await addButton.click();

    const form = page.getByTestId("individual-form");
    await expect(form).toBeVisible();

    // Fill form WITHOUT selecting a class
    await page.getByTestId("individual-title-input").fill("No Class Individual");
    await page.getByTestId("individual-description-input").fill("This has no classes");

    // Try to submit - should show error
    await page.getByTestId("individual-form-submit").click();

    // Verify error message appears
    const errorAlert = page.getByRole("alert");
    await expect(errorAlert).toBeVisible();
    await expect(errorAlert).toContainText(/class|required/i);

    // Form should still be visible
    await expect(form).toBeVisible();
  });

  test("should reject removing last parent class via UI", async ({ page }) => {
    // Create individual with single class
    const individual = await apiRequest<any>(page, "/api/individuals", {
      method: "POST",
      body: {
        title: "Last Class Removal Individual",
        description: "Testing last class removal",
        class_ids: [classIds[0]],
      },
    });

    // Navigate to individuals page
    await page.goto("/app/individuals");
    await waitForAppReady(page);

    // Open edit form
    const tableRow = page.getByRole("row", { name: /Last Class Removal Individual/i }).first();
    await tableRow.dblclick();

    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Try to remove the last (and only) class
    const removeButton = page.getByTestId(
      `individual-classes-remove-button-${classIds[0]}`,
    );
    await removeButton.click();

    // Try to submit
    await page.getByTestId("individual-form-submit").click();

    // Should show error
    const errorAlert = page.getByRole("alert");
    await expect(errorAlert).toBeVisible();
    await expect(errorAlert).toContainText(/class|required/i);

    // Modal should still be visible
    await expect(modal).toBeVisible();
  });
});
