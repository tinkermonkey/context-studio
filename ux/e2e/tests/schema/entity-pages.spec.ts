import type { Page } from "@playwright/test";
import { test, expect } from "../../fixtures/app-test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createIndividual,
  createPropertyDefinition,
  createRelationship,
  type ConceptScheme,
  type Individual,
  type OntologyClass,
  type Taxonomy,
} from "../../fixtures/factories";

/**
 * Entity pages (#1307): global search lands on a taxonomy / scheme / class /
 * individual page, and the Navigator tree and in-page links move between them.
 */

interface Seed {
  taxonomy: Taxonomy;
  scheme: ConceptScheme;
  component: OntologyClass;
  service: OntologyClass;
  router: Individual;
  api: Individual;
}

async function seedModel(page: Page): Promise<Seed> {
  const taxonomy = await createTaxonomy(page, { title: "Enterprise Model" });
  const scheme = await createConceptScheme(page, taxonomy.id, { title: "Application Layer" });
  const component = await createClass(page, scheme.id, {
    title: "Application Component",
    description: "Modular, deployable part of a system",
  });
  const service = await createClass(page, scheme.id, {
    title: "Application Service",
    description: "Behavior exposed to the environment",
  });
  const realizes = await createPropertyDefinition(page, {
    identifier: "component_realizes_service",
    title: "Component realizes service",
    canonical_predicate: "realizes",
    domain_class_id: component.id,
    range_class_id: service.id,
  });
  const router = await createIndividual(page, {
    title: "LLM Provider Router",
    description: "Routes completion requests to a provider",
    class_ids: [component.id],
  });
  const api = await createIndividual(page, {
    title: "Pipeline API",
    description: "Pipeline service",
    class_ids: [service.id],
  });
  await createRelationship(page, router.id, api.id, realizes.id, "realizes");
  return { taxonomy, scheme, component, service, router, api };
}

const heading = (page: Page, name: string) => page.getByRole("heading", { level: 1, name });

test.describe("Entity pages", () => {
  test("a global search result opens the class page", async ({ page }) => {
    const seed = await seedModel(page);
    await page.goto("/app");
    await page.waitForLoadState("networkidle");

    await page.keyboard.press("Meta+k");
    await page.locator(".command-palette__input").fill("Application Component");
    const result = page
      .locator(".command-palette__item")
      .filter({ hasText: "Go to class · Application Component" });
    await result.click();

    await expect(page).toHaveURL(new RegExp(`/app/schema/classes/${seed.component.id}$`));
    await expect(page.getByTestId("class-page")).toBeVisible();
    await expect(heading(page, "Application Component")).toBeVisible();
    await expect(page.getByTestId("class-definition-text")).toHaveText(
      "Modular, deployable part of a system",
    );
    // The navigator opens to the class and highlights it.
    await expect(page.getByTestId(`hierarchy-node-${seed.component.id}`)).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  test("a global search result opens the individual page", async ({ page }) => {
    const seed = await seedModel(page);
    await page.goto("/app");
    await page.waitForLoadState("networkidle");

    await page.keyboard.press("Meta+k");
    await page.locator(".command-palette__input").fill("LLM Provider Router");
    await page
      .locator(".command-palette__item")
      .filter({ hasText: "Go to individual · LLM Provider Router" })
      .click();

    await expect(page).toHaveURL(new RegExp(`/app/data/individuals/${seed.router.id}$`));
    await expect(heading(page, "LLM Provider Router")).toBeVisible();
    const sentence = page.getByTestId("individual-relationships-panel");
    await expect(sentence.getByText("— realizes →")).toBeVisible();
    await expect(sentence.getByRole("link", { name: "Pipeline API" })).toBeVisible();
  });

  test("the navigator and page links move through the hierarchy", async ({ page }) => {
    const seed = await seedModel(page);
    await page.goto(`/app/schema/classes/${seed.component.id}`);
    await expect(heading(page, "Application Component")).toBeVisible();

    // Navigator: class → its scheme.
    await page.getByTestId(`hierarchy-node-${seed.scheme.id}`).click();
    await expect(page).toHaveURL(new RegExp(`/app/schema/schemes/${seed.scheme.id}$`));
    await expect(heading(page, "Application Layer")).toBeVisible();

    // Navigator: scheme → taxonomy.
    await page.getByTestId(`hierarchy-node-${seed.taxonomy.id}`).click();
    await expect(page).toHaveURL(new RegExp(`/app/schema/taxonomies/${seed.taxonomy.id}$`));
    await expect(heading(page, "Enterprise Model")).toBeVisible();

    // Taxonomy schemes table → scheme; classes table → class.
    await page.getByTestId(`taxonomy-scheme-link-${seed.scheme.id}`).click();
    await expect(heading(page, "Application Layer")).toBeVisible();
    await page.getByTestId(`scheme-class-link-${seed.service.id}`).click();
    await expect(heading(page, "Application Service")).toBeVisible();

    // Class → individual → related individual → its class.
    await page.getByTestId(`class-individual-link-${seed.api.id}`).click();
    await expect(heading(page, "Pipeline API")).toBeVisible();
    await page
      .getByTestId("individual-relationships-panel")
      .getByRole("link", { name: "LLM Provider Router" })
      .click();
    await expect(heading(page, "LLM Provider Router")).toBeVisible();
    await page.getByTestId(`individual-class-chip-${seed.component.id}`).click();
    await expect(heading(page, "Application Component")).toBeVisible();

    // Outgoing relationship types list the range class.
    await expect(
      page
        .getByTestId("class-relationship-types-panel")
        .getByRole("link", { name: "Application Service" }),
    ).toBeVisible();
  });

  test("breadcrumbs follow the hierarchy", async ({ page }) => {
    const seed = await seedModel(page);
    await page.goto(`/app/data/individuals/${seed.router.id}`);
    await expect(heading(page, "LLM Provider Router")).toBeVisible();

    const breadcrumbs = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(breadcrumbs.getByRole("button", { name: "Enterprise Model" })).toBeVisible();
    await breadcrumbs.getByRole("button", { name: "Application Layer" }).click();
    await expect(page).toHaveURL(new RegExp(`/app/schema/schemes/${seed.scheme.id}$`));
  });
});
