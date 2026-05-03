import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createIndividual,
  createTestHierarchy,
  clearTestData,
  waitForAppReady,
} from "../../fixtures/test-helpers";

/**
 * Entity Detail Page E2E Tests
 *
 * Each entity type has a dedicated detail page reachable by clicking a row
 * in its list view. These tests verify that navigating to a detail URL renders
 * the entity's data and the expected structural sections.
 *
 * Shared detail-page testids (taxonomy, class, concept scheme):
 *   node-detail-title, node-detail-id, node-detail-type,
 *   node-detail-definition-section, node-detail-definition,
 *   node-attributes-section, node-children-section
 *
 * Individual detail-page testids:
 *   individual-detail-id, individual-detail-title, individual-detail-description,
 *   individual-classes-section, inherited-properties-section
 */

test.describe("Entity Detail Pages", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test.describe("Taxonomy detail", () => {
    test("should render taxonomy detail page with entity data", async ({ page }) => {
      const taxonomy = await createTaxonomy(page, {
        title: "Detail Test Taxonomy",
        description: "For detail page testing",
      });

      await page.goto(`/app/taxonomies/${taxonomy.id}`);
      await waitForAppReady(page);

      await expect(page.getByTestId("node-detail-title")).toBeVisible();
      await expect(page.getByTestId("node-detail-title")).toContainText("Detail Test Taxonomy");
      await expect(page.getByTestId("node-detail-id")).toBeVisible();
      await expect(page.getByTestId("node-detail-type")).toBeVisible();
      await expect(page.getByTestId("node-detail-definition-section")).toBeVisible();
      await expect(page.getByTestId("node-attributes-section")).toBeVisible();
    });

    test("should navigate to taxonomy detail from list page", async ({ page }) => {
      const taxonomy = await createTaxonomy(page, { title: "Nav To Detail Taxonomy" });

      await page.goto("/app/taxonomies");
      await waitForAppReady(page);

      await page.getByTestId(`taxonomy-row-${taxonomy.id}`).getByRole("link").click();
      await waitForAppReady(page);

      expect(page.url()).toContain(`/app/taxonomies/${taxonomy.id}`);
      await expect(page.getByTestId("node-detail-title")).toContainText("Nav To Detail Taxonomy");
    });
  });

  test.describe("Concept scheme detail", () => {
    test("should render concept scheme detail page with entity data", async ({ page }) => {
      const taxonomy = await createTaxonomy(page);
      const scheme = await createConceptScheme(page, taxonomy.id, {
        title: "Detail Test Scheme",
        description: "For detail page testing",
      });

      await page.goto(`/app/concept-schemes/${scheme.id}`);
      await waitForAppReady(page);

      await expect(page.getByTestId("node-detail-title")).toBeVisible();
      await expect(page.getByTestId("node-detail-title")).toContainText("Detail Test Scheme");
      await expect(page.getByTestId("node-detail-id")).toBeVisible();
      await expect(page.getByTestId("node-detail-type")).toBeVisible();
      await expect(page.getByTestId("node-detail-definition-section")).toBeVisible();
      await expect(page.getByTestId("node-attributes-section")).toBeVisible();
    });

    test("should navigate to concept scheme detail from list page", async ({ page }) => {
      const taxonomy = await createTaxonomy(page);
      const scheme = await createConceptScheme(page, taxonomy.id, {
        title: "Nav To Detail Scheme",
      });

      await page.goto("/app/concept-schemes");
      await waitForAppReady(page);

      await page.getByTestId(`concept-scheme-row-${scheme.id}`).getByRole("link").click();
      await waitForAppReady(page);

      expect(page.url()).toContain(`/app/concept-schemes/${scheme.id}`);
      await expect(page.getByTestId("node-detail-title")).toContainText("Nav To Detail Scheme");
    });
  });

  test.describe("Class detail", () => {
    test("should render class detail page with entity data", async ({ page }) => {
      const hierarchy = await createTestHierarchy(page, 1);
      const cls = hierarchy.classes[0];

      await page.goto(`/app/classes/${cls.id}`);
      await waitForAppReady(page);

      await expect(page.getByTestId("node-detail-title")).toBeVisible();
      await expect(page.getByTestId("node-detail-id")).toBeVisible();
      await expect(page.getByTestId("node-detail-type")).toBeVisible();
      await expect(page.getByTestId("node-detail-definition-section")).toBeVisible();
      await expect(page.getByTestId("node-attributes-section")).toBeVisible();
    });

    test("should navigate to class detail from list page", async ({ page }) => {
      const hierarchy = await createTestHierarchy(page, 1, {
        classTitle: "Nav To Detail Class",
      });
      const cls = hierarchy.classes[0];

      await page.goto("/app/classes");
      await waitForAppReady(page);

      await page.getByTestId(`class-row-${cls.id}`).getByRole("link").click();
      await waitForAppReady(page);

      expect(page.url()).toContain(`/app/classes/${cls.id}`);
      await expect(page.getByTestId("node-detail-title")).toContainText("Nav To Detail Class");
    });
  });

  test.describe("Individual detail", () => {
    test("should render individual detail page with entity data and class membership", async ({
      page,
    }) => {
      const hierarchy = await createTestHierarchy(page, 1);
      const individual = await createIndividual(page, [hierarchy.classes[0].id], {
        title: "Detail Test Individual",
        description: "For detail page testing",
      });

      await page.goto(`/app/individuals/${individual.id}`);
      await waitForAppReady(page);

      await expect(page.getByTestId("individual-detail-title")).toBeVisible();
      await expect(page.getByTestId("individual-detail-title")).toContainText(
        "Detail Test Individual",
      );
      await expect(page.getByTestId("individual-detail-id")).toBeVisible();
      await expect(page.getByTestId("individual-detail-description")).toBeVisible();
      await expect(page.getByTestId("individual-classes-section")).toBeVisible();
      await expect(page.getByTestId("inherited-properties-section")).toBeVisible();
    });

    test("should display both parent classes in individual detail", async ({ page }) => {
      const hierarchy = await createTestHierarchy(page, 2, {
        classTitle: "multi-class-parent",
      });
      const individual = await createIndividual(
        page,
        [hierarchy.classes[0].id, hierarchy.classes[1].id],
        { title: "Multi-Class Individual" },
      );

      await page.goto(`/app/individuals/${individual.id}`);
      await waitForAppReady(page);

      const classesSection = page.getByTestId("individual-classes-section");
      await expect(classesSection).toBeVisible();

      // Both parent class titles must appear — asserting only length > 0 would
      // pass if the section rendered "Loading…" or any single character.
      await expect(classesSection).toContainText(hierarchy.classes[0].title);
      await expect(classesSection).toContainText(hierarchy.classes[1].title);
    });

    test("should navigate to individual detail from list page", async ({ page }) => {
      const hierarchy = await createTestHierarchy(page, 1);
      const individual = await createIndividual(page, [hierarchy.classes[0].id], {
        title: "Nav To Detail Individual",
      });

      await page.goto("/app/individuals");
      await waitForAppReady(page);

      await page.getByTestId(`individual-row-${individual.id}`).getByRole("link").click();
      await waitForAppReady(page);

      expect(page.url()).toContain(`/app/individuals/${individual.id}`);
      await expect(page.getByTestId("individual-detail-title")).toContainText(
        "Nav To Detail Individual",
      );
    });
  });
});
