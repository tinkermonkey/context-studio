import type { Page } from "@playwright/test";
import { test, expect } from "../../fixtures/app-test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createIndividual,
  type ConceptScheme,
  type Individual,
  type OntologyClass,
  type Taxonomy,
} from "../../fixtures/factories";

/**
 * Data navigation (#1309): the Navigator's Data mode shows individuals under
 * their classes a page at a time, counts individuals, keeps Data mode while
 * drilling down, and filters individuals by title.
 */

interface Seed {
  taxonomy: Taxonomy;
  scheme: ConceptScheme;
  component: OntologyClass;
  individuals: Individual[];
}

const INDIVIDUAL_COUNT = 12;

async function seedModel(page: Page): Promise<Seed> {
  const taxonomy = await createTaxonomy(page, { title: "Enterprise Model" });
  const scheme = await createConceptScheme(page, taxonomy.id, { title: "Application Layer" });
  const component = await createClass(page, scheme.id, { title: "Application Component" });
  const individuals: Individual[] = [];
  for (let i = 1; i <= INDIVIDUAL_COUNT; i++) {
    const n = String(i).padStart(2, "0");
    individuals.push(
      await createIndividual(page, { title: `Component ${n}`, class_ids: [component.id] }),
    );
  }
  return { taxonomy, scheme, component, individuals };
}

const heading = (page: Page, name: string) => page.getByRole("heading", { level: 1, name });
const node = (page: Page, id: string) => page.getByTestId(`hierarchy-node-${id}`);
const dataToggle = (page: Page) =>
  page.getByTestId("navigator-mode").getByRole("radio", { name: "Data" });

test.describe("Data navigation", () => {
  test("drill to a class's individuals from the individuals page", async ({ page }) => {
    const seed = await seedModel(page);
    await page.goto("/app/data/individuals");
    await expect(page.getByTestId("data-navigator-layout")).toBeVisible();
    await expect(dataToggle(page)).toHaveAttribute("aria-checked", "true");
    await expect(node(page, seed.taxonomy.id)).toContainText(`${INDIVIDUAL_COUNT} individuals`);

    // Drilling opens entity pages; the Navigator stays in Data mode.
    await node(page, seed.taxonomy.id).click();
    await expect(heading(page, "Enterprise Model")).toBeVisible();
    await node(page, seed.scheme.id).click();
    await expect(heading(page, "Application Layer")).toBeVisible();
    await expect(dataToggle(page)).toHaveAttribute("aria-checked", "true");
    await node(page, seed.component.id).click();
    await expect(heading(page, "Application Component")).toBeVisible();

    // The class shows its first page of individuals, then the rest on demand.
    await expect(node(page, seed.individuals[0].id)).toBeVisible();
    await expect(node(page, seed.individuals[11].id)).toHaveCount(0);
    const more = page.getByTestId(`hierarchy-more-${seed.component.id}`);
    await expect(more).toContainText("+ 2 more in Application Component");
    await more.click();
    await expect(node(page, seed.individuals[11].id)).toBeVisible();
    await expect(more).toHaveCount(0);

    await node(page, seed.individuals[11].id).click();
    await expect(heading(page, "Component 12")).toBeVisible();
    await expect(node(page, seed.individuals[11].id)).toHaveAttribute("aria-pressed", "true");
  });

  test("an individual past the first page is shown and highlighted on its page", async ({
    page,
  }) => {
    const seed = await seedModel(page);
    const last = seed.individuals[INDIVIDUAL_COUNT - 1];
    await page.goto(`/app/data/individuals/${last.id}`);
    await expect(heading(page, "Component 12")).toBeVisible();

    await expect(node(page, last.id)).toHaveAttribute("aria-pressed", "true");
    await expect(node(page, seed.component.id)).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByTestId(`hierarchy-more-${seed.component.id}`)).toBeVisible();
  });

  test("the filter finds individuals in Data mode", async ({ page }) => {
    const seed = await seedModel(page);
    await page.goto("/app/data/individuals");
    await expect(node(page, seed.taxonomy.id)).toBeVisible();

    await page.getByTestId("navigator-filter").fill("Component 07");

    await expect(node(page, seed.individuals[6].id)).toBeVisible();
    await expect(node(page, seed.individuals[0].id)).toHaveCount(0);
    // Counts are hidden while the tree shows matches.
    await expect(node(page, seed.taxonomy.id)).not.toContainText("individuals");
  });
});
