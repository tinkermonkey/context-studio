import { test, expect } from "../../fixtures/app-test";
import { apiRequest } from "../../fixtures/api-client";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createPropertyDefinition,
} from "../../fixtures/test-helpers";

/**
 * Relationship delete against the current UI (EntitySurface row menu).
 *
 * Create/edit go through the RelationshipBuilder widget (source/target/predicate
 * pickers); those flows need dedicated selector work and are not covered here.
 * The relationship is seeded via the API with the current contract
 * ({ source_id, target_id, relationship_type }).
 */
test.describe("Relationships CRUD — current UI", () => {
  test("delete a relationship via the row menu", async ({ page }) => {
    const taxonomy = await createTaxonomy(page, { title: "E2E Rel Taxonomy" });
    const scheme = await createConceptScheme(page, taxonomy.id, { title: "E2E Rel Scheme" });
    const source = await createClass(page, scheme.id, { title: "E2E Source Class" });
    const target = await createClass(page, scheme.id, { title: "E2E Target Class" });
    const property = await createPropertyDefinition(page, {
      identifier: "e2e_related_to",
      title: "E2E Related To",
    });
    await apiRequest(page, "/api/relationships", {
      method: "POST",
      body: {
        source_id: source.id,
        target_id: target.id,
        relationship_type: property.identifier,
      },
    });

    await page.goto("/app/schema/relationships");
    await page.waitForLoadState("networkidle");

    const row = page.getByRole("row", { name: /E2E Source Class/ });
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: "Row actions" }).click();
    await page.getByRole("menuitem", { name: "Delete" }).click();
    await page.getByTestId("cascade-delete-confirm").click();
    await page.waitForLoadState("networkidle");

    await expect(page.getByTestId("selectable-table").getByText("E2E Source Class")).toHaveCount(
      0,
      { timeout: 5000 },
    );
  });
});
