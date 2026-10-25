import type { Page } from "@playwright/test";
import { test, expect } from "../../fixtures/app-test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  type ConceptScheme,
  type OntologyClass,
  type Taxonomy,
} from "../../fixtures/factories";

/**
 * Schema navigation (#1308): the Navigator beside the schema list pages lets a
 * user drill taxonomy → scheme → class, keeps its open rows across pages, and
 * filters by title (classes are searched on the server).
 */

interface Seed {
  taxonomy: Taxonomy;
  scheme: ConceptScheme;
  otherScheme: ConceptScheme;
  component: OntologyClass;
  gateway: OntologyClass;
}

async function seedModel(page: Page): Promise<Seed> {
  const taxonomy = await createTaxonomy(page, { title: "Enterprise Model" });
  const scheme = await createConceptScheme(page, taxonomy.id, { title: "Application Layer" });
  const otherScheme = await createConceptScheme(page, taxonomy.id, { title: "Technology Layer" });
  const component = await createClass(page, scheme.id, { title: "Application Component" });
  const gateway = await createClass(page, otherScheme.id, { title: "API Gateway" });
  return { taxonomy, scheme, otherScheme, component, gateway };
}

const heading = (page: Page, name: string) => page.getByRole("heading", { level: 1, name });
const node = (page: Page, id: string) => page.getByTestId(`hierarchy-node-${id}`);

test.describe("Schema navigation", () => {
  test("drill from taxonomy to scheme to class from a schema list page", async ({ page }) => {
    const seed = await seedModel(page);
    await page.goto("/app/schema/taxonomies");
    await expect(page.getByTestId("schema-navigator-layout")).toBeVisible();

    await node(page, seed.taxonomy.id).click();
    await expect(heading(page, "Enterprise Model")).toBeVisible();
    await expect(node(page, seed.taxonomy.id)).toHaveAttribute("aria-expanded", "true");

    await node(page, seed.scheme.id).click();
    await expect(heading(page, "Application Layer")).toBeVisible();

    await node(page, seed.component.id).click();
    await expect(page).toHaveURL(new RegExp(`/app/schema/classes/${seed.component.id}$`));
    await expect(heading(page, "Application Component")).toBeVisible();
    await expect(node(page, seed.component.id)).toHaveAttribute("aria-pressed", "true");
  });

  test("open rows stay open when moving to another schema page", async ({ page }) => {
    const seed = await seedModel(page);
    await page.goto(`/app/schema/classes/${seed.component.id}`);
    await expect(heading(page, "Application Component")).toBeVisible();

    // Open a second scheme without leaving the class page's path…
    await node(page, seed.otherScheme.id).click();
    await expect(heading(page, "Technology Layer")).toBeVisible();

    // …then go to a list page in-app (the "Schema" breadcrumb → taxonomies):
    // both schemes' classes are still shown. (Expansion lives in memory, so a
    // full reload starts fresh.)
    await page
      .getByRole("navigation", { name: "Breadcrumb" })
      .getByRole("button", { name: "Schema" })
      .click();
    await expect(page).toHaveURL(/\/app\/schema\/taxonomies$/);
    await expect(node(page, seed.component.id)).toBeVisible();
    await expect(node(page, seed.gateway.id)).toBeVisible();
  });

  test("the filter finds a class in a collapsed scheme", async ({ page }) => {
    const seed = await seedModel(page);
    await page.goto("/app/schema/schemes");
    await expect(node(page, seed.taxonomy.id)).toBeVisible();
    await expect(node(page, seed.gateway.id)).toHaveCount(0);

    await page.getByTestId("navigator-filter").fill("gateway");
    await expect(node(page, seed.gateway.id)).toBeVisible();
    await expect(node(page, seed.component.id)).toHaveCount(0);

    await node(page, seed.gateway.id).click();
    await expect(heading(page, "API Gateway")).toBeVisible();

    await page.getByTestId("navigator-filter").fill("no such thing");
    await expect(page.getByTestId("navigator-no-matches")).toHaveText(
      "Nothing matches “no such thing”.",
    );
  });
});
