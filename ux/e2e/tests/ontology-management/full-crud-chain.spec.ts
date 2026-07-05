import { test, expect } from "../../fixtures/app-test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createPropertyDefinition,
  createRelationship,
  clearTestData,
} from "../../fixtures/test-helpers";

/**
 * End-to-end ontology chain against the current UI:
 * taxonomy → scheme → classes → property → relationship, each verified in its
 * schema page, then a leaf class deleted via the row-actions → cascade-delete
 * flow. Entities are seeded through the API factories; the UI assertions confirm
 * they surface in the current `selectable-table` at the `/app/schema/*` routes.
 */
test.describe("Ontology Management Full CRUD Chain", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("creates the full ontology chain and deletes a leaf class", async ({ page }) => {
    const taxonomy = await createTaxonomy(page, {
      title: "Full Chain Taxonomy",
      description: "Comprehensive test of ontology CRUD operations",
    });
    const scheme = await createConceptScheme(page, taxonomy.id, { title: "Full Chain Scheme" });
    const parent = await createClass(page, scheme.id, { title: "Parent Class" });
    const child = await createClass(page, scheme.id, { title: "Child Class" });
    const property = await createPropertyDefinition(page, {
      identifier: "broader",
      title: "Broader",
      description: "Has a broader/parent concept",
    });
    await createRelationship(page, parent.id, child.id, property.id, property.identifier);

    // Taxonomy appears.
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByTestId("selectable-table").getByText("Full Chain Taxonomy"),
    ).toBeVisible({ timeout: 5000 });

    // Scheme appears.
    await page.goto("/app/schema/schemes");
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("selectable-table").getByText("Full Chain Scheme")).toBeVisible({
      timeout: 5000,
    });

    // Both classes appear.
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");
    const classesTable = page.getByTestId("selectable-table");
    await expect(classesTable.getByText("Parent Class")).toBeVisible({ timeout: 5000 });
    await expect(classesTable.getByText("Child Class")).toBeVisible();

    // Property appears.
    await page.goto("/app/schema/properties");
    await page.waitForLoadState("networkidle");
    await expect(
      page.getByTestId("selectable-table").getByText("broader", { exact: true }).first(),
    ).toBeVisible({ timeout: 5000 });

    // Relationships page renders the seeded relationship.
    await page.goto("/app/schema/relationships");
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("selectable-table")).toBeVisible();

    // Delete the leaf child class via the row-actions → cascade-delete flow.
    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");
    const childRow = page.getByRole("row", { name: new RegExp(child.id.slice(0, 8)) });
    await expect(childRow).toBeVisible();
    await childRow.getByRole("button", { name: "Row actions" }).click();
    await page.getByRole("menuitem", { name: "Delete" }).click();
    await page.getByTestId("cascade-delete-confirm").click();
    await page.waitForLoadState("networkidle");

    await expect(page.getByTestId("selectable-table").getByText("Child Class")).toHaveCount(0, {
      timeout: 5000,
    });
    // The parent remains.
    await expect(page.getByTestId("selectable-table").getByText("Parent Class")).toBeVisible();
  });
});
