import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createPropertyDefinition,
  createRelationship,
  clearTestData,
} from "../../fixtures/test-helpers";

test.describe("Ontology Management Full CRUD Chain", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should complete full CRUD chain: taxonomy → scheme → classes → property → relationship → delete → undo", async ({
    page,
  }) => {
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");

    // Test Case 1: Create a Taxonomy
    const taxonomy = await createTaxonomy(page, {
      title: "Test Taxonomy: Full CRUD Chain",
      description: "Comprehensive test of ontology CRUD operations",
    });

    expect(taxonomy.id).toBeDefined();
    expect(taxonomy.title).toBe("Test Taxonomy: Full CRUD Chain");
    expect(taxonomy.description).toBe("Comprehensive test of ontology CRUD operations");
    expect(taxonomy.version).toBe(1);

    // Verify taxonomy appears in the UI
    await page.goto("/app/taxonomies");
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("schema-table")).toContainText("Test Taxonomy: Full CRUD Chain");

    // Test Case 2: Create a Concept Scheme
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "Test Concept Scheme",
      description: "Scheme for testing class hierarchy",
    });

    expect(scheme.id).toBeDefined();
    expect(scheme.title).toBe("Test Concept Scheme");
    expect(scheme.taxonomy_id).toBe(taxonomy.id);
    expect(scheme.version).toBe(1);

    // Verify scheme appears in the UI
    await page.goto("/app/schemes");
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("schema-table")).toContainText("Test Concept Scheme");

    // Test Case 3: Create a Class in the Concept Scheme
    const class1 = await createClass(page, scheme.id, {
      title: "Parent Class",
      description: "A parent class for testing hierarchy",
    });

    expect(class1.id).toBeDefined();
    expect(class1.title).toBe("Parent Class");
    expect(class1.concept_scheme_id).toBe(scheme.id);
    expect(class1.version).toBe(1);

    // Navigate to scheme detail page to verify class appears
    await page.goto(`/app/schemes/${scheme.id}`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("schema-table")).toContainText("Parent Class");

    // Test Case 4: Create a Second Class
    const class2 = await createClass(page, scheme.id, {
      title: "Child Class",
      description: "A child class for testing relationships",
    });

    expect(class2.id).toBeDefined();
    expect(class2.title).toBe("Child Class");

    // Verify second class appears in the table
    await expect(page.getByTestId("schema-table")).toContainText("Child Class");

    // Create a PropertyDefinition
    const property = await createPropertyDefinition(page, {
      identifier: "broader",
      title: "Broader",
      description: "Has a broader/parent concept",
    });

    expect(property.id).toBeDefined();
    expect(property.identifier).toBe("broader");
    expect(property.title).toBe("Broader");
    expect(property.version).toBe(1);

    // Verify property appears in the UI
    await page.goto("/app/properties");
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("schema-table")).toContainText("Broader");

    // Click on the property row to open the drawer
    const propertyRows = page.locator('[data-testid^="schema-row-"]');
    const firstPropertyRow = propertyRows.first();
    await firstPropertyRow.click();
    await expect(page.getByTestId("property-drawer")).toBeVisible();

    // Verify property drawer appears with expected fields
    await expect(page.getByTestId("property-drawer")).toBeVisible();
    await expect(page.getByTestId("property-drawer-identifier")).toBeVisible();
    await expect(page.getByTestId("property-drawer-title-input")).toBeVisible();
    await expect(page.getByTestId("property-drawer-description-input")).toBeVisible();

    // Test Case 5: Create a Relationship Between Classes
    const relationship = await createRelationship(
      page,
      class1.id,
      class2.id,
      property.id,
    );

    expect(relationship.id).toBeDefined();
    expect(relationship.source_id).toBe(class1.id);
    expect(relationship.target_id).toBe(class2.id);
    expect(relationship.property_definition_id).toBe(property.id);

    // Verify relationship appears in the relationships page
    await page.goto("/app/relationships");
    await page.waitForLoadState("networkidle");
    const relationshipsTable = page.getByTestId("schema-table");
    // We can't easily verify the exact relationship without knowing the row ID,
    // but we can verify that the table contains expected content
    await expect(relationshipsTable).toBeVisible();

    // Test Case 6: Delete the First Class with Type-to-Confirm
    await page.goto(`/app/schemes/${scheme.id}`);
    await page.waitForLoadState("networkidle");

    // Find and click the actions button for class1
    // Use attribute selector to find the row with matching ID
    const classRowSelector = `[data-testid^="schema-row-"]`;
    const classRows = page.locator(classRowSelector);

    // Find the row containing "Parent Class" text
    const classRow = classRows.filter({ hasText: "Parent Class" }).first();
    await expect(classRow).toBeVisible();

    // Get the testid to extract the class ID for finding the actions button
    const classRowTestId = await classRow.getAttribute("data-testid");
    const classRowId = classRowTestId?.replace("schema-row-", "") || "";

    // Click the actions button using the extracted ID
    await classRow.hover();
    const actionsButton = page.locator(`[data-testid="class-row-actions-${classRowId}"]`);
    await actionsButton.click();

    // Click delete option from context menu
    await page.getByRole("button", { name: /delete/i }).click();

    // Verify type-to-confirm dialog appears
    await expect(page.getByTestId("type-confirm-dialog")).toBeVisible();

    // Type confirmation phrase
    const confirmInput = page.getByTestId("type-confirm-input");
    await confirmInput.fill("Delete");

    // Click confirm button
    const confirmButton = page.getByTestId("type-confirm-button");
    await expect(confirmButton).toBeEnabled();
    await confirmButton.click();

    // Verify class is removed from the visible table
    const schemaTable = page.getByTestId("schema-table");
    await expect(schemaTable).not.toContainText("Parent Class");

    // Test Case 7: Undo the Deletion Within 8 Seconds
    // Look for the toast notification with undo action
    const toastAction = page.locator('[data-testid^="toast-action-"]').first();
    await expect(toastAction).toBeVisible();

    // Click the undo action button
    await toastAction.click();

    // Wait for the toast to disappear
    await expect(toastAction).not.toBeVisible();

    // Test Case 8: Verify the Restored Class Appears in the Table
    // The restored class should have a new ID (UUID) but the same title and description
    const table = page.getByTestId("schema-table");

    // Wait for the table to update with the restored class
    await expect(table).toContainText("Parent Class", { timeout: 5000 });

    // Verify the restored class row exists (but with a potentially different ID)
    const restoredClassRows = page.locator(
      '[data-testid^="schema-row-"]',
    );
    const rowCount = await restoredClassRows.count();
    expect(rowCount).toBeGreaterThan(0);

    // Verify description is preserved
    await expect(table).toContainText("A parent class for testing hierarchy");

    // The restored class should have a different ID than the original
    // (we can verify this by checking that the new row ID is different)
    const newClassRow = page
      .locator('[data-testid^="schema-row-"]')
      .filter({ hasText: "Parent Class" })
      .first();
    const newClassId = await newClassRow.getAttribute("data-testid");

    // Extract ID from testid (format: schema-row-{id})
    const newId = newClassId?.replace("schema-row-", "");

    // Verify the new ID is not the same as the original
    expect(newId).toBeDefined();
    expect(newId).not.toBe(class1.id);

    // Verify no error messages appear
    const errorElements = page.locator('[role="alert"]');
    const errorCount = await errorElements.count();
    expect(errorCount).toBe(0);
  });
});
