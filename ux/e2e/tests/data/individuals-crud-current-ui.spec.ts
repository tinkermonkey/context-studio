import { test, expect } from "../../fixtures/app-test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createIndividual,
} from "../../fixtures/test-helpers";

/**
 * Individuals CRUD against the current UI (CreateDrawer + EntitySurface +
 * IndividualDrawer). Covers create-by-class-selection, the related-individual
 * navigation that was previously inert, and delete.
 */

async function makeClass(page: import("@playwright/test").Page, prefix: string) {
  const taxonomy = await createTaxonomy(page, { title: `${prefix} Taxonomy` });
  const scheme = await createConceptScheme(page, taxonomy.id, { title: `${prefix} Scheme` });
  return createClass(page, scheme.id, { title: `${prefix} Class` });
}

test.describe("Individuals CRUD — current UI", () => {
  test("create an individual by selecting a class", async ({ page }) => {
    const cls = await makeClass(page, "E2E Ind");

    await page.goto("/app/data/individuals");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("individual-add-button").click();
    await page.getByTestId("create-drawer-title-input").fill("E2E New Individual");
    // Target the class checkbox by its stable testid and wait for the async
    // class list to render it before checking.
    const classCheckbox = page.getByTestId(`create-drawer-class-${cls.id}`);
    await expect(classCheckbox).toBeVisible({ timeout: 15000 });
    await classCheckbox.check();
    await page.getByTestId("create-drawer-create-btn").click();

    await expect(page.getByTestId("selectable-table").getByText("E2E New Individual")).toBeVisible({
      timeout: 5000,
    });
  });

  test("navigate to a related individual from the drawer", async ({ page }) => {
    const cls = await makeClass(page, "E2E Shared");
    await createIndividual(page, { title: "E2E Individual A", class_ids: [cls.id] });
    const b = await createIndividual(page, { title: "E2E Individual B", class_ids: [cls.id] });

    await page.goto("/app/data/individuals");
    await page.waitForLoadState("networkidle");

    // Open A and enter edit mode (the Related Individuals panel lives there).
    await page.getByTestId("selectable-table").getByText("E2E Individual A").click();
    await page.getByTestId("inline-inspector-edit-button").click();

    // Click related individual B — previously a no-op; now switches the inspector.
    await page.getByTestId(`related-individual-name-${b.id}`).click();
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByTestId("schema-inspector-container").getByText("E2E Individual B").first(),
    ).toBeVisible({ timeout: 5000 });
  });

  test("delete an individual via the row menu", async ({ page }) => {
    const cls = await makeClass(page, "E2E Del Ind");
    await createIndividual(page, { title: "E2E Doomed Individual", class_ids: [cls.id] });

    await page.goto("/app/data/individuals");
    await page.waitForLoadState("networkidle");

    const row = page.getByRole("row", { name: /E2E Doomed Individual/ });
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "Row actions" }).click();
    await page.getByRole("menuitem", { name: "Delete" }).click();
    await page.getByTestId("cascade-delete-confirm").click();
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByTestId("selectable-table").getByText("E2E Doomed Individual"),
    ).toHaveCount(0, { timeout: 5000 });
  });
});
