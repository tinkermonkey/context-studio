import { test, expect } from "../../fixtures/app-test";
import { createTaxonomy, createConceptScheme, createClass } from "../../fixtures/test-helpers";

/**
 * Schema CRUD against the current UI (CreateDrawer + EntitySurface + InlineInspector).
 *
 * Covers the recent CRUD-workflow changes against the live, isolated test stack:
 *  - slug identifiers are generated AND persisted on create (not a generic x_<uuid>)
 *  - inline edits autosave and refresh the table
 *  - leaf entities delete via the row-actions menu + confirm dialog
 *  - non-empty parents are blocked by the backend with the specific reason shown
 *
 * Reliable-locator policy: create via the CreateDrawer, delete via the
 * row-actions menu → cascade-delete dialog, and use API factories for setup.
 */

/** Open the row-actions menu for the row whose accessible name matches `rowName`. */
async function deleteViaRowMenu(page: import("@playwright/test").Page, rowName: RegExp) {
  const row = page.getByRole("row", { name: rowName });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Row actions" }).click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await page.getByTestId("cascade-delete-confirm").click();
  await page.waitForLoadState("networkidle");
}

test.describe("Schema CRUD — current UI", () => {
  test("taxonomy: create persists a slug identifier", async ({ page }) => {
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("taxonomy-add-button").click();
    await page.getByTestId("create-drawer-title-input").fill("E2E Verify Taxonomy");
    await expect(page.getByTestId("create-drawer-identifier-input")).toHaveValue(
      "tax_e2e_verify_taxonomy",
    );
    await page.getByTestId("create-drawer-create-btn").click();

    await expect(
      page.getByTestId("selectable-table").getByText("tax_e2e_verify_taxonomy"),
    ).toBeVisible({ timeout: 5000 });
  });

  test("taxonomy: inline-edit the description and see it persist", async ({ page }) => {
    await createTaxonomy(page, { title: "E2E Edit Taxonomy" });
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("selectable-table").getByText("E2E Edit Taxonomy").click();
    await page.getByTestId("inline-inspector-edit-button").click();

    const desc = page.getByTestId("taxonomy-drawer-description-input");
    await desc.fill("Edited inline by E2E");
    await desc.blur();
    await page.waitForLoadState("networkidle");

    // The edit invalidates the list, so the table description cell updates.
    await expect(
      page.getByTestId("selectable-table").getByText("Edited inline by E2E"),
    ).toBeVisible({ timeout: 5000 });
  });

  test("taxonomy: delete an empty taxonomy via the row menu", async ({ page }) => {
    await createTaxonomy(page, { title: "E2E Delete Taxonomy" });
    await page.goto("/app/schema/taxonomies");
    await page.waitForLoadState("networkidle");

    await deleteViaRowMenu(page, /E2E Delete Taxonomy/);

    await expect(page.getByTestId("selectable-table").getByText("E2E Delete Taxonomy")).toHaveCount(
      0,
      { timeout: 5000 },
    );
  });

  test("property: create persists a slug identifier and deletes", async ({ page }) => {
    await page.goto("/app/schema/properties");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("property-add-button").click();
    await page.getByTestId("create-drawer-title-input").fill("E2E Predicate");
    await expect(page.getByTestId("create-drawer-identifier-input")).toHaveValue("e2e_predicate");
    await page.getByTestId("create-drawer-create-btn").click();

    const table = page.getByTestId("selectable-table");
    await expect(table.getByText("e2e_predicate")).toBeVisible({ timeout: 5000 });

    await deleteViaRowMenu(page, /e2e_predicate/);
    await expect(table.getByText("e2e_predicate")).toHaveCount(0, { timeout: 5000 });
  });

  test("scheme: blocks deleting a scheme that still has classes and surfaces the reason", async ({
    page,
  }) => {
    const taxonomy = await createTaxonomy(page, { title: "E2E Block Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, { title: "E2E Block Scheme" });
    await createClass(page, scheme.id, { title: "E2E Block Class" });

    await page.goto("/app/schema/schemes");
    await page.waitForLoadState("networkidle");

    await deleteViaRowMenu(page, /E2E Block Scheme/);

    await expect(page.getByText(/Cannot delete/i).first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId("selectable-table").getByText("E2E Block Scheme")).toBeVisible();
  });

  test("class: blocks deleting a class that still has subclasses and surfaces the reason", async ({
    page,
  }) => {
    const taxonomy = await createTaxonomy(page, { title: "E2E Class Block Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, {
      title: "E2E Class Block Scheme",
    });
    const parent = await createClass(page, scheme.id, { title: "E2E Parent Class" });
    await createClass(page, scheme.id, { title: "E2E Child Class", parent_class_id: parent.id });

    await page.goto("/app/schema/classes");
    await page.waitForLoadState("networkidle");

    // Locate the parent row by its id prefix (the classes table shows the UUID
    // prefix as the identifier). Matching by title would be ambiguous because
    // the child row references the parent's title in its Parent column.
    await deleteViaRowMenu(page, new RegExp(parent.id.slice(0, 8)));

    await expect(page.getByText(/Cannot delete/i).first()).toBeVisible({ timeout: 5000 });
    await expect(
      page.getByTestId("selectable-table").getByText("E2E Parent Class").first(),
    ).toBeVisible();
  });
});
